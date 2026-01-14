"""Socket.IO server for real-time bidirectional sync between web clients and bot."""
import asyncio
import os
import logging
import socketio

logger = logging.getLogger(__name__)

# Async server
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = socketio.ASGIApp(sio)

# Simple connect/disconnect handlers
@sio.event
async def connect(sid, environ):
    logger.info(f"Socket connected: {sid}")

@sio.event
async def disconnect(sid):
    logger.info(f"Socket disconnected: {sid}")

# Client control events: web -> server
@sio.event
async def music_control(sid, data):
    """Data: {action: 'play'|'pause'|'skip'|'stop', guild_id, extra...} """
    logger.info(f"music_control from {sid}: {data}")
    # Broadcast to all clients and also publish to in-process broadcaster via import to avoid circular imports
    try:
        from bot.events import broadcaster
        broadcaster.publish({'type': 'music:control', 'payload': data})
    except Exception as e:
        logger.exception("Failed to publish music control: %s", e)
    await sio.emit('music_control', data)

# Server-side emit helper
async def emit(event: str, data):
    try:
        await sio.emit(event, data)
    except Exception as e:
        logger.exception("emit failed: %s", e)
