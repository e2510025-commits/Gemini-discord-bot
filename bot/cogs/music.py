"""Music cog: basic playback using yt-dlp + FFmpegPCMAudio and AI-based recommendations"""
import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import yt_dlp

from shared.models import MusicChannel, MusicTrack, MusicPlayback, Base
from bot.events import broadcaster
from bot.gemini_client import chat
from bot.socketio_server import sio

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot.db")
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# In-memory per guild queue
queues: Dict[int, List[MusicTrack]] = {}
players: Dict[int, discord.VoiceClient] = {}

YTDL_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)

@dataclass
class TrackInfo:
    title: str
    url: str
    stream_url: Optional[str] = None
    duration: Optional[float] = None
    thumbnail: Optional[str] = None


async def extract_info(query: str) -> Optional[TrackInfo]:
    loop = asyncio.get_running_loop()
    try:
        # support direct URLs and 'ytsearch:' queries
        if query.startswith('http'):
            info = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
        else:
            # search
            info = await loop.run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch:{query}", download=False))
            if isinstance(info, dict) and 'entries' in info:
                info = info['entries'][0]
        if not info:
            return None
        stream_url = info.get('url')
        return TrackInfo(title=info.get('title') or query, url=info.get('webpage_url') or query, stream_url=stream_url, duration=info.get('duration'), thumbnail=info.get('thumbnail'))
    except Exception as e:
        logger.exception('yt-dlp failed: %s', e)
        return None


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # register handler for controls coming from socket.io / web
        try:
            broadcaster.register_handler(self._on_broadcast)
        except Exception:
            pass

    async def _on_broadcast(self, data):
        # handle music:control events
        try:
            if not isinstance(data, dict):
                return
            if data.get('type') != 'music:control':
                return
            payload = data.get('payload', {})
            action = payload.get('action')
            guild_id = payload.get('guild_id')
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return
            if action == 'skip':
                vc = discord.utils.get(self.bot.voice_clients, guild=guild)
                if vc and vc.is_playing():
                    vc.stop()
            elif action == 'stop':
                queues[guild.id] = []
                vc = discord.utils.get(self.bot.voice_clients, guild=guild)
                if vc:
                    await vc.disconnect()
            elif action == 'play':
                query = payload.get('query')
                if not query:
                    return
                info = await extract_info(query)
                if not info:
                    return
                async with AsyncSessionLocal() as session:
                    t = MusicTrack(guild_id=guild.id, requested_by=None, title=info.title, url=info.url, stream_url=info.stream_url, duration=info.duration, thumbnail=info.thumbnail)
                    session.add(t)
                    await session.commit()
                    await session.refresh(t)
                queues.setdefault(guild.id, [])
                queues[guild.id].append(t)
                qpayload = {'guild_id': guild.id, 'queue': [{'id': x.id, 'title': x.title} for x in queues[guild.id]]}
                broadcaster.publish({'type': 'music:queue_update', 'payload': qpayload})
                try:
                    asyncio.create_task(sio.emit('music:queue_update', qpayload))
                except Exception:
                    pass
                # start if not playing
                async with AsyncSessionLocal() as session:
                    q2 = await session.execute(MusicPlayback.__table__.select().where(MusicPlayback.guild_id == guild.id))
                    cur = q2.scalar_one_or_none()
                if not cur:
                    await self.play_next(guild)
        except Exception:
            logger.exception('Broadcast handler failed')
    async def join_or_create_music_channel(self, guild: discord.Guild, user: discord.Member):
        # attempt to find existing music channel
        existing = discord.utils.get(guild.voice_channels, name='🎵｜Music-Space')
        if existing:
            return existing
        # create voice channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=True, view_channel=True),
        }
        # create channel
        channel = await guild.create_voice_channel('🎵｜Music-Space', overwrites=overwrites, reason='Music channel auto-created')
        # persist
        async with AsyncSessionLocal() as session:
            mc = MusicChannel(guild_id=guild.id, channel_id=channel.id, owner_id=user.id)
            session.add(mc)
            await session.commit()
        broadcaster.publish({'type': 'music:channel_created', 'payload': {'guild_id': guild.id, 'channel_id': channel.id}})
        return channel

    async def ensure_voice(self, interaction: discord.Interaction):
        # ensure bot is connected to a voice channel in this guild
        if interaction.user is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message('You must be in a guild and in a voice channel, or request creation.', ephemeral=True)
            return None
        # if user in VC, join that; otherwise create music channel and join
        if interaction.user.voice and interaction.user.voice.channel:
            vc = interaction.user.voice.channel
        else:
            vc = await self.join_or_create_music_channel(interaction.guild, interaction.user)
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if voice_client and voice_client.channel.id == vc.id:
            return voice_client
        try:
            voice_client = await vc.connect()
        except Exception as e:
            logger.exception('Failed to connect voice: %s', e)
            return None
        return voice_client

    async def play_next(self, guild: discord.Guild):
        q = queues.get(guild.id, [])
        if not q:
            # schedule cleanup and mark playback stopped
            async with AsyncSessionLocal() as session:
                await session.execute(MusicPlayback.__table__.delete().where(MusicPlayback.guild_id == guild.id))
                await session.commit()
            # disconnect voice
            vc = discord.utils.get(self.bot.voice_clients, guild=guild)
            if vc:
                await vc.disconnect()
            # schedule channel cleanup (delete created music channels after 5m)
            async def cleanup():
                await asyncio.sleep(300)
                async with AsyncSessionLocal() as session:
                    q2 = await session.execute(MusicChannel.__table__.select().where(MusicChannel.guild_id == guild.id))
                    row = q2.scalar_one_or_none()
                    if row:
                        try:
                            ch = guild.get_channel(row.channel_id)
                            if ch and isinstance(ch, discord.VoiceChannel) and len(ch.members) == 0:
                                await ch.delete(reason='cleanup empty music channel')
                                await session.execute(MusicChannel.__table__.delete().where(MusicChannel.guild_id == guild.id))
                                await session.commit()
                                broadcaster.publish({'type': 'music:channel_deleted', 'payload': {'guild_id': guild.id, 'channel_id': row.channel_id}})
                        except Exception:
                            pass
            asyncio.create_task(cleanup())
            return
        track = q.pop(0)
        # update DB playback
        started_at = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            # set current track
            await session.execute(MusicPlayback.__table__.delete().where(MusicPlayback.guild_id == guild.id))
            mp = MusicPlayback(guild_id=guild.id, current_track_id=track.id, is_playing=1, started_at=started_at)
            session.add(mp)
            await session.commit()
        # publish event
        payload = {'guild_id': guild.id, 'track': {'id': track.id, 'title': track.title, 'thumbnail': track.thumbnail, 'duration': track.duration}, 'started_at': started_at.isoformat()}
        broadcaster.publish({'type': 'music:play', 'payload': payload})
        # emit to socket.io clients (non-blocking)
        try:
            asyncio.create_task(sio.emit('music:play', payload))
        except Exception:
            pass

        # actual playback
        vc = discord.utils.get(self.bot.voice_clients, guild=guild)
        if not vc:
            # nothing to play
            return
        # create ffmpeg source
        source = discord.FFmpegPCMAudio(track.stream_url or track.url, options='-vn')
        def after_play(err):
            if err:
                logger.exception('Playback error: %s', err)
            # play next
            asyncio.run_coroutine_threadsafe(self.play_next(guild), self.bot.loop)
        try:
            vc.play(source, after=after_play)
        except Exception as e:
            logger.exception('Play failed: %s', e)
            # continue to next
            await self.play_next(guild)

    @app_commands.command(name='play', description='Play a song by name or URL')
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        vc = await self.ensure_voice(interaction)
        if not vc:
            await interaction.followup.send('Could not connect to voice.', ephemeral=True)
            return
        info = await extract_info(query)
        if not info:
            await interaction.followup.send('曲が見つかりませんでした。', ephemeral=True)
            return
        # persist track
        async with AsyncSessionLocal() as session:
            t = MusicTrack(guild_id=interaction.guild.id, requested_by=interaction.user.id, title=info.title, url=info.url, stream_url=info.stream_url, duration=info.duration, thumbnail=info.thumbnail)
            session.add(t)
            await session.commit()
            await session.refresh(t)
        queues.setdefault(interaction.guild.id, [])
        queues[interaction.guild.id].append(t)
        qpayload = {'guild_id': interaction.guild.id, 'queue': [{'id': x.id, 'title': x.title} for x in queues[interaction.guild.id]]}
        broadcaster.publish({'type': 'music:queue_update', 'payload': qpayload})
        try:
            asyncio.create_task(sio.emit('music:queue_update', qpayload))
        except Exception:
            pass
        await interaction.followup.send(f'キューに追加しました: {t.title}')
        # if nothing playing, start
        # check playback
        async with AsyncSessionLocal() as session:
            q = await session.execute(MusicPlayback.__table__.select().where(MusicPlayback.guild_id == interaction.guild.id))
            cur = q.scalar_one_or_none()
        if not cur:
            await self.play_next(interaction.guild)

    @app_commands.command(name='skip', description='Skip current track')
    async def skip(self, interaction: discord.Interaction):
        vc = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message('Skipped')
        else:
            await interaction.response.send_message('No track playing', ephemeral=True)

    @app_commands.command(name='stop', description='Stop playback and clear queue')
    async def stop(self, interaction: discord.Interaction):
        vc = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        queues[interaction.guild.id] = []
        async with AsyncSessionLocal() as session:
            await session.execute(MusicPlayback.__table__.delete().where(MusicPlayback.guild_id == interaction.guild.id))
            await session.commit()
        if vc:
            await vc.disconnect()
        await interaction.response.send_message('Stopped and cleared queue')

    @app_commands.command(name='queue', description='Show current queue')
    async def queue_cmd(self, interaction: discord.Interaction):
        q = queues.get(interaction.guild.id, [])
        if not q:
            await interaction.response.send_message('キューは空です', ephemeral=True)
            return
        text = '\n'.join([f"{i+1}. {t.title}" for i, t in enumerate(q[:10])])
        await interaction.response.send_message(f'キュー:\n{text}', ephemeral=True)

    @app_commands.command(name='recommend', description='Recommend and play a song based on context')
    async def recommend(self, interaction: discord.Interaction, prompt: Optional[str] = None):
        await interaction.response.defer()
        # Build prompt from recent chat history if available
        hist = []
        # try to fetch last few ChatLog messages
        async with AsyncSessionLocal() as session:
            q = await session.execute(MusicTrack.__table__.select().where(MusicTrack.guild_id == interaction.guild.id).order_by(MusicTrack.created_at.desc()).limit(5))
            recent = q.fetchall()
            # ignore for now
        # Ask Gemini to suggest a search keyword
        ai_prompt = f"ユーザーが求める音楽を一言の検索語に変換してください。入力: {prompt or 'リラックスできる曲'}。出力は日本語の検索キーワードのみ。"
        resp = await chat(ai_prompt, system='You are a music search assistant.')
        suggestion = (resp.get('text') or '').strip().split('\n')[0]
        if not suggestion:
            suggestion = prompt or 'リラックスできる曲'
        info = await extract_info(suggestion)
        if not info:
            await interaction.followup.send('おすすめ曲が見つかりませんでした。', ephemeral=True)
            return
        # persist and queue
        async with AsyncSessionLocal() as session:
            t = MusicTrack(guild_id=interaction.guild.id, requested_by=interaction.user.id, title=info.title, url=info.url, stream_url=info.stream_url, duration=info.duration, thumbnail=info.thumbnail, reason=suggestion)
            session.add(t)
            await session.commit()
            await session.refresh(t)
        queues.setdefault(interaction.guild.id, [])
        queues[interaction.guild.id].append(t)
        qpayload = {'guild_id': interaction.guild.id, 'queue': [{'id': x.id, 'title': x.title} for x in queues[interaction.guild.id]]}
        broadcaster.publish({'type': 'music:queue_update', 'payload': qpayload})
        try:
            asyncio.create_task(sio.emit('music:queue_update', qpayload))
        except Exception:
            pass
        await interaction.followup.send(f'おすすめをキューに追加しました: {t.title} （検索語: {suggestion}）')
        # start if not playing
        async with AsyncSessionLocal() as session:
            q2 = await session.execute(MusicPlayback.__table__.select().where(MusicPlayback.guild_id == interaction.guild.id))
            cur = q2.scalar_one_or_none()
        if not cur:
            await self.play_next(interaction.guild)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # simple trigger phrases to auto-create music channel and start
        if message.author.bot:
            return
        content = message.content.lower()
        triggers = ['音楽流して', 'リラックスできる曲', '曲を流して', 'プレイリスト', '音楽かけて']
        if any(t in content for t in triggers):
            # create or join voice channel and call recommend
            guild = message.guild
            if not guild:
                return
            channel = await self.join_or_create_music_channel(guild, message.author)
            # call gemini to extract a suggestion
            ai_prompt = f"ユーザーの発言から最適な検索ワードを一つにしてください: {message.content}"
            resp = await chat(ai_prompt, system='You are a music search assistant.')
            suggestion = (resp.get('text') or '').strip().split('\n')[0]
            if not suggestion:
                suggestion = message.content
            info = await extract_info(suggestion)
            if not info:
                try:
                    await message.channel.send('曲が見つかりませんでした。')
                except Exception:
                    pass
                return
            # persist
            async with AsyncSessionLocal() as session:
                t = MusicTrack(guild_id=guild.id, requested_by=message.author.id, title=info.title, url=info.url, stream_url=info.stream_url, duration=info.duration, thumbnail=info.thumbnail, reason=suggestion)
                session.add(t)
                await session.commit()
                await session.refresh(t)
            queues.setdefault(guild.id, [])
            queues[guild.id].append(t)
            qpayload = {'guild_id': guild.id, 'queue': [{'id': x.id, 'title': x.title} for x in queues[guild.id]]}
            broadcaster.publish({'type': 'music:queue_update', 'payload': qpayload})
            try:
                asyncio.create_task(sio.emit('music:queue_update', qpayload))
            except Exception:
                pass
            try:
                await message.channel.send(f'自動選曲: {t.title} をキューに追加しました。')
            except Exception:
                pass
            # attempt to connect and play
            vc = discord.utils.get(self.bot.voice_clients, guild=guild)
            if not vc:
                # connect to created channel
                try:
                    await (await self.join_or_create_music_channel(guild, message.author))
                except Exception:
                    pass
            # if nothing playing, start
            async with AsyncSessionLocal() as session:
                q2 = await session.execute(MusicPlayback.__table__.select().where(MusicPlayback.guild_id == guild.id))
                cur = q2.scalar_one_or_none()
            if not cur:
                # schedule play
                asyncio.create_task(self.play_next(guild))


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
