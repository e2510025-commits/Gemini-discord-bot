"""Cog implementing AI commands, mode switching, auto-response, and logging"""
import os
import logging
import asyncio
from collections import defaultdict, deque
from typing import Dict, Deque

import discord
from discord.ext import commands
from discord import app_commands

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from shared.models import AIChannel, Mode, UsageLog, Base, ChatLog
from bot.gemini_client import chat
from bot.events import broadcaster
import time
from datetime import datetime

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Per-user in-memory conversation history
histories: Dict[int, Deque[str]] = defaultdict(lambda: deque(maxlen=8))

MODE_INSTRUCTIONS = {
    "standard": "You are a helpful assistant.",
    "creative": "You are a creative AI assistant who gives vivid imaginative answers.",
    "coder": "You are an expert code assistant. Provide concise accurate code answers.",
}


class AICommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._ready_task = bot.loop.create_task(self._init_db())

    async def _init_db(self):
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("DB initialized")

    @app_commands.command(name="mode", description="Set AI mode for the guild")
    @app_commands.describe(mode="Mode: standard, creative, coder")
    async def mode(self, interaction: discord.Interaction, mode: str):
        mode = mode.lower()
        if mode not in MODE_INSTRUCTIONS:
            await interaction.response.send_message("Unknown mode. Choose standard/creative/coder", ephemeral=True)
            return
        async with AsyncSessionLocal() as session:
            q = await session.execute(
                Mode.__table__.select().where(Mode.guild_id == interaction.guild_id)
            )
            res = q.scalar_one_or_none()
            if res:
                res.mode = mode
            else:
                res = Mode(guild_id=interaction.guild_id, mode=mode)
                session.add(res)
            await session.commit()
        await interaction.response.send_message(f"Mode set to {mode}")

    @app_commands.command(name="setup-public-chat", description="Create a public AI chat channel in the guild")
    async def setup_public_chat(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("This command must be used in a guild.", ephemeral=True)
            return

        # Create or find category
        category = discord.utils.get(guild.categories, name="AI-CHAT")
        if not category:
            category = await guild.create_category("AI-CHAT", reason="Creating AI chat category")

        # Create channel with public permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        channel = await guild.create_text_channel("gemini-public", category=category, overwrites=overwrites, reason="Create public AI chat channel")

        # Save to DB
        async with AsyncSessionLocal() as session:
            q = await session.execute(AIChannel.__table__.select().where(AIChannel.channel_id == channel.id))
            existing = q.scalar_one_or_none()
            if existing:
                await interaction.followup.send("Channel already registered", ephemeral=True)
                return
            ch = AIChannel(guild_id=guild.id, channel_id=channel.id, name=channel.name, type="public")
            session.add(ch)
            await session.commit()

        # Notify channel and user
        embed = discord.Embed(title="準備完了！", description="公開AIチャネルが作成されました。ここでAIと会話できます。", color=0xff66aa)
        embed.set_footer(text="Gemini Bot")
        try:
            await channel.send(embed=embed)
        except Exception:
            pass
        await interaction.followup.send(f"公開チャネル {channel.mention} を作成しました。", ephemeral=True)

        # Publish event
        broadcaster.publish({"type":"channel:created","payload":{"id":channel.id,"name":channel.name,"type":"public","guild_id":guild.id}})

    @app_commands.command(name="setup-private-chat", description="Create a private AI chat channel for you")
    async def setup_private_chat(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        member = interaction.user
        if not guild or not isinstance(member, discord.Member):
            await interaction.followup.send("This command must be used in a guild.", ephemeral=True)
            return

        # Create or find category
        category = discord.utils.get(guild.categories, name="AI-CHAT")
        if not category:
            category = await guild.create_category("AI-CHAT", reason="Creating AI chat category")

        # Build channel name
        safe_name = f"chat-with-{member.display_name.lower().replace(' ', '-')[:20]}"

        # Prepare permission overwrites
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        # allow administrators
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(safe_name, category=category, overwrites=overwrites, reason=f"Private AI channel for {member}")

        # Save to DB
        async with AsyncSessionLocal() as session:
            q = await session.execute(AIChannel.__table__.select().where(AIChannel.channel_id == channel.id))
            existing = q.scalar_one_or_none()
            if existing:
                await interaction.followup.send("Channel already registered", ephemeral=True)
                return
            ch = AIChannel(guild_id=guild.id, channel_id=channel.id, name=channel.name, type="private", owner_id=member.id, owner_name=str(member), owner_avatar=str(member.display_avatar.url) if member.display_avatar else None)
            session.add(ch)
            await session.commit()

        # Notify channel and user
        embed = discord.Embed(title="準備完了！", description=f"{member.mention} のプライベートチャネルを作成しました。", color=0xff66aa)
        embed.set_footer(text="Gemini Bot")
        try:
            await channel.send(embed=embed)
        except Exception:
            pass
        await interaction.followup.send(f"プライベートチャネル {channel.mention} を作成しました。", ephemeral=True)

        # Publish event
        broadcaster.publish({"type":"channel:created","payload":{"id":channel.id,"name":channel.name,"type":"private","guild_id":guild.id,"owner_id":member.id,"owner_name":str(member)}})

    @app_commands.command(name="stats", description="Show usage stats (approx.)")
    async def stats(self, interaction: discord.Interaction):
        async with AsyncSessionLocal() as session:
            q = await session.execute(
                UsageLog.__table__.select().where(UsageLog.guild_id == interaction.guild_id)
            )
            rows = q.fetchall()
            total_tokens = sum(r[0] for r in [ (row.tokens,) for row in rows ]) if rows else 0
            total_msgs = sum(r[0] for r in [ (row.message_count,) for row in rows ]) if rows else 0
        await interaction.response.send_message(f"Tokens: {total_tokens:.0f}, Messages: {total_msgs}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bot messages
        if message.author.bot:
            return

        # Quick local regex replies to common phrases to avoid API calls
        content_low = (message.content or "").strip()
        if not content_low:
            return
        import re
        greetings = re.compile(r"^(hi|hello|こんにちは|おはよう|こんばんは)\b", re.I)
        farewells = re.compile(r"\b(bye|さようなら|おやすみ)\b", re.I)
        if greetings.search(content_low):
            try:
                await message.channel.send(f"こんにちは、{message.author.display_name} さん！")
            except Exception:
                pass
            return
        if farewells.search(content_low):
            try:
                await message.channel.send("またね！")
            except Exception:
                pass
            return

        # Check if channel is an AI channel
        async with AsyncSessionLocal() as session:
            q = await session.execute(AIChannel.__table__.select().where(AIChannel.channel_id == message.channel.id))
            channel_row = q.scalar_one_or_none()
            if not channel_row:
                return

        # Before calling Gemini, validate quota / system state
        async with AsyncSessionLocal() as session:
            qstate = await session.execute(SystemState.__table__.select().where(SystemState.key == 'ai_paused'))
            paused = qstate.scalar_one_or_none()
            if paused and paused.value == '1':
                try:
                    await message.channel.send('現在、無料枠上限に達しているためAIは休止中です。')
                except Exception:
                    pass
                return

        # Build prompt from recent history and optionally use summary
        user_hist = histories[message.author.id]
        user_hist.append(f"User: {message.content}")
        # If history grows, summarize to save tokens
        if len(user_hist) >= 6:
            text_to_summarize = '\n'.join(list(user_hist))
            sresp = await summarize_context(text_to_summarize)
            # store summary in DB
            async with AsyncSessionLocal() as session:
                qsum = await session.execute(ConversationSummary.__table__.select().where(ConversationSummary.user_id == message.author.id))
                sumrow = qsum.scalar_one_or_none()
                if sumrow:
                    sumrow.summary = sresp.get('summary')
                    sumrow.updated_at = datetime.utcnow()
                else:
                    sumrow = ConversationSummary(user_id=message.author.id, guild_id=message.guild.id, summary=sresp.get('summary'))
                    session.add(sumrow)
                await session.commit()
            # reduce history to summary only
            user_hist.clear()
            user_hist.append(f"Summary: {sresp.get('summary')}")

        prompt = "\n".join(list(user_hist))

        # Get current mode for guild
        async with AsyncSessionLocal() as session:
            q = await session.execute(Mode.__table__.select().where(Mode.guild_id == message.guild.id))
            mode_row = q.scalar_one_or_none()
            mode = mode_row.mode if mode_row else "standard"
        system_instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["standard"])

        # Use cheaper model for standard mode to save cost
        model_to_use = DEFAULT_CHEAP_MODEL if mode == 'standard' else DEFAULT_HIGH_MODEL

        # Call Gemini asynchronously and measure latency
        start = time.perf_counter()
        resp = await chat(prompt, system=system_instruction, model=model_to_use)
        end = time.perf_counter()
        latency_ms = (end - start) * 1000.0
        text = resp.get("text") or ""
        tokens = resp.get("tokens", 0.0)

        # Append assistant reply to history
        user_hist.append(f"Assistant: {text}")

        # Approximate byte sizes for network stats
        rx_size = len(message.content.encode("utf-8")) if message.content else 0
        tx_size = len(text.encode("utf-8")) if text else 0

        # Record usage and chat log
        async with AsyncSessionLocal() as session:
            log = UsageLog(guild_id=message.guild.id, user_id=message.author.id, tokens=tokens, message_count=1)
            session.add(log)

            # Safe avatar URL extraction
            try:
                avatar_url = str(message.author.display_avatar.url)
            except Exception:
                avatar_url = None

            chat_row = ChatLog(
                guild_id=message.guild.id,
                channel_id=message.channel.id,
                channel_name=message.channel.name if hasattr(message.channel, 'name') else None,
                user_id=message.author.id,
                user_name=str(message.author),
                user_avatar=avatar_url,
                user_message=message.content,
                bot_response=text,
                tokens=tokens,
                latency_ms=latency_ms,
            )
            session.add(chat_row)
            await session.commit()

            # Publish events for web clients
            try:
                # publish chat event
                broadcaster.publish({
                    "type": "chat",
                    "payload": {
                        "id": chat_row.id,
                        "guild_id": chat_row.guild_id,
                        "channel_id": chat_row.channel_id,
                        "channel_name": chat_row.name if hasattr(chat_row, 'name') else None,
                        "user_id": chat_row.user_id,
                        "user_name": chat_row.user_name,
                        "user_avatar": chat_row.user_avatar,
                        "user_message": chat_row.user_message,
                        "bot_response": chat_row.bot_response,
                        "tokens": float(chat_row.tokens or 0.0),
                        "latency_ms": float(chat_row.latency_ms or 0.0),
                        "created_at": chat_row.created_at.isoformat() if chat_row.created_at else datetime.utcnow().isoformat(),
                    },
                })

                # publish network event
                broadcaster.publish({
                    "type": "network",
                    "payload": {
                        "rx": rx_size,
                        "tx": tx_size,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                })

                # publish music events if channel is a music channel
                try:
                    async with AsyncSessionLocal() as session:
                        q = await session.execute(MusicChannel.__table__.select().where(MusicChannel.channel_id == message.channel.id))
                        mrow = q.scalar_one_or_none()
                        if mrow:
                            broadcaster.publish({'type': 'music:chat', 'payload': {'guild_id': message.guild.id, 'channel_id': message.channel.id}})
                except Exception:
                    pass
            except Exception as e:
                logger.exception("Publish event failed: %s", e)

        # Send reply
        try:
            await message.channel.send(text)
        except Exception as e:
            logger.exception("Failed to send reply: %s", e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AICommands(bot))
