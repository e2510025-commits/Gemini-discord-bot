"""Small FastAPI app to expose endpoints for the web dashboard to control bot settings and stream events."""
import os
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from shared.models import AIChannel, UsageLog, Base, ChatLog
from bot.events import broadcaster

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

app = FastAPI()

# Allow CORS for local dev (adjust origins in production)
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Socket.IO ASGI app
from bot.socketio_server import app as socketio_asgi, sio
app.mount('/ws', socketio_asgi)
class ChannelPayload(BaseModel):
    guild_id: int
    channel_id: int
    name: str | None = None


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.post("/api/channels")
async def add_channel(payload: ChannelPayload):
    async with AsyncSessionLocal() as session:
        q = await session.execute(AIChannel.__table__.select().where(AIChannel.channel_id == payload.channel_id))
        existing = q.scalar_one_or_none()
        if existing:
            raise HTTPException(400, "Channel already registered")
        ch = AIChannel(guild_id=payload.guild_id, channel_id=payload.channel_id, name=payload.name)
        session.add(ch)
        await session.commit()
    return {"ok": True}


@app.delete("/api/channels/{channel_id}")
async def remove_channel(channel_id: int):
    async with AsyncSessionLocal() as session:
        q = await session.execute(AIChannel.__table__.select().where(AIChannel.channel_id == channel_id))
        existing = q.scalar_one_or_none()
        if not existing:
            raise HTTPException(404, "Not found")
        await session.execute(AIChannel.__table__.delete().where(AIChannel.channel_id == channel_id))
        await session.commit()

    # publish event so web clients can remove UI
    try:
        broadcaster.publish({"type": "channel:deleted", "payload": {"channel_id": channel_id}})
    except Exception:
        pass

    return {"ok": True}


@app.get("/api/channels")
async def list_channels():
    async with AsyncSessionLocal() as session:
        q = await session.execute(AIChannel.__table__.select())
        rows = q.fetchall()
        items = []
        for row in rows:
            r = row._mapping
            items.append({
                "id": r["id"],
                "guild_id": r["guild_id"],
                "channel_id": r["channel_id"],
                "name": r["name"],
                "type": r["type"],
                "owner_id": r.get("owner_id"),
                "owner_name": r.get("owner_name"),
                "owner_avatar": r.get("owner_avatar"),
            })
    # group by type for convenience
    public = [i for i in items if i["type"] == "public"]
    private = [i for i in items if i["type"] == "private"]
    return {"public": public, "private": private}


@app.get("/api/stats")
async def stats():
    async with AsyncSessionLocal() as session:
        q = await session.execute(UsageLog.__table__.select())
        rows = q.fetchall()
        total_tokens = sum(r[0] for r in [(row.tokens,) for row in rows]) if rows else 0
        total_msgs = sum(r[0] for r in [(row.message_count,) for row in rows]) if rows else 0
    return {"tokens": total_tokens, "messages": total_msgs}


@app.get('/api/monitor')
async def monitor():
    # Summarize token usage and quota
    quota_name = 'free_tokens'
    async with AsyncSessionLocal() as session:
        q = await session.execute(UsageLog.__table__.select())
        rows = q.fetchall()
        total_tokens = sum(r[0] for r in [(row.tokens,) for row in rows]) if rows else 0
        qx = await session.execute(Quota.__table__.select().where(Quota.name == quota_name))
        qrow = qx.scalar_one_or_none()
        quota = qrow.limit if qrow else None
    # basic system metrics (best-effort)
    try:
        import psutil, time
        mem = psutil.virtual_memory().used
        uptime = time.time() - psutil.boot_time()
    except Exception:
        mem = None
        uptime = None
    return {"tokens_used": float(total_tokens), "quota": quota, "memory": mem, "uptime": int(uptime) if uptime else None}


@app.get("/api/chatlogs")
async def chatlogs(limit: int = 100):
    """Return the latest chat logs (most recent first)"""
    async with AsyncSessionLocal() as session:
        q = await session.execute(
            ChatLog.__table__.select().order_by(ChatLog.created_at.desc()).limit(limit)
        )
        rows = q.fetchall()
        # Build serializable dicts
        items = []
        for row in rows:
            r = row._mapping
            items.append({
                "id": r["id"],
                "guild_id": r["guild_id"],
                "channel_id": r["channel_id"],
                "channel_name": r.get("channel_name"),
                "user_id": r["user_id"],
                "user_name": r["user_name"],
                "user_avatar": r["user_avatar"],
                "user_message": r["user_message"],
                "bot_response": r["bot_response"],
                "tokens": float(r["tokens"] or 0.0),
                "latency_ms": float(r["latency_ms"] or 0.0),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            })
    return {"items": items}


@app.get("/api/stream")
async def stream():
    """Server Sent Events stream. Clients receive newline-delimited JSON payloads as SSE data."""
    async def event_generator():
        q = broadcaster.subscribe()
        try:
            while True:
                data = await q.get()
                yield f"data: {json.dumps(data)}\n\n"
        finally:
            broadcaster.unsubscribe(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get('/api/music/stream')
async def music_stream(track_id: int, proxy: int = 0):
    """If proxy=1, stream audio through the server (shared broadcast). Otherwise redirect to original URL if possible."""
    async with AsyncSessionLocal() as session:
        q = await session.execute(MusicTrack.__table__.select().where(MusicTrack.id == track_id))
        tr = q.scalar_one_or_none()
        if not tr:
            raise HTTPException(404, 'not found')
        if proxy:
            from bot.streaming import stream_manager
            try:
                qsub = await stream_manager.subscribe_track(tr.id, tr.url)
            except Exception:
                raise HTTPException(500, 'stream failed')

            async def stream_generator():
                try:
                    while True:
                        chunk = await qsub.get()
                        if chunk is None:
                            break
                        yield chunk
                finally:
                    stream_manager.unsubscribe_track(tr.id, qsub)

            return StreamingResponse(stream_generator(), media_type='audio/mpeg')
        else:
            # redirect to best available
            if tr.stream_url:
                from fastapi.responses import RedirectResponse
                return RedirectResponse(tr.stream_url)
            return {'url': tr.url}


# Music control endpoints
@app.get('/api/music/state')
async def music_state(guild_id: int):
    async with AsyncSessionLocal() as session:
        q = await session.execute(MusicPlayback.__table__.select().where(MusicPlayback.guild_id == guild_id))
        playback = q.scalar_one_or_none()
        cur = None
        queue = []
        if playback and playback.current_track_id:
            q2 = await session.execute(MusicTrack.__table__.select().where(MusicTrack.id == playback.current_track_id))
            tr = q2.scalar_one_or_none()
            if tr:
                cur = {
                    'id': tr.id,
                    'title': tr.title,
                    'thumbnail': tr.thumbnail,
                    'duration': tr.duration,
                }
        q3 = await session.execute(MusicTrack.__table__.select().where(MusicTrack.guild_id == guild_id).order_by(MusicTrack.created_at.asc()).limit(50))
        rows = q3.fetchall()
        for r in rows:
            rm = r._mapping
            queue.append({'id': rm['id'], 'title': rm['title']})
    return {'current': cur, 'queue': queue}


class MusicCommandPayload(BaseModel):
    guild_id: int
    query: str | None = None


@app.post('/api/music/play')
async def api_music_play(payload: MusicCommandPayload):
    # queue a track via web
    info = await extract_info(payload.query or 'リラックスできる曲')
    if not info:
        raise HTTPException(404, 'not found')
    async with AsyncSessionLocal() as session:
        t = MusicTrack(guild_id=payload.guild_id, requested_by=None, title=info.title, url=info.url, stream_url=info.stream_url, duration=info.duration, thumbnail=info.thumbnail)
        session.add(t)
        await session.commit()
        await session.refresh(t)
    broadcaster.publish({'type': 'music:queue_update', 'payload': {'guild_id': payload.guild_id, 'queue': [{'id': x.id, 'title': x.title} for x in queues.get(payload.guild_id, [])]}})
    return {'ok': True, 'track': {'id': t.id, 'title': t.title}}


@app.post('/api/music/skip')
async def api_music_skip(payload: MusicCommandPayload):
    vc = None
    for v in list(broadcaster._queues)[:1]:
        pass
    # Best-effort: stop current playback via voice client
    # Note: For safety, bot process should own VoiceClient; here we simply publish an event that UI can use to request a skip via a bot command.
    broadcaster.publish({'type': 'music:control', 'payload': {'action': 'skip', 'guild_id': payload.guild_id}})
    return {'ok': True}


