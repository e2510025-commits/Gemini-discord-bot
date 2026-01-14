"""StreamManager: proxy audio streams via yt-dlp and share to multiple clients to save bandwidth."""
import asyncio
import logging
from typing import Dict, List
import aiohttp
import yt_dlp

logger = logging.getLogger(__name__)

YTDL_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)

class StreamSession:
    def __init__(self, stream_url: str):
        self.stream_url = stream_url
        self.queues: List[asyncio.Queue] = []
        self.task: asyncio.Task | None = None
        self.active = False

    def subscribe(self):
        q = asyncio.Queue(maxsize=10)
        self.queues.append(q)
        if not self.task:
            self.task = asyncio.create_task(self._run())
        return q

    def unsubscribe(self, q: asyncio.Queue):
        try:
            self.queues.remove(q)
        except Exception:
            pass

    async def _run(self):
        self.active = True
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.stream_url) as resp:
                    async for chunk in resp.content.iter_chunked(1024*8):
                        if not chunk:
                            break
                        for q in list(self.queues):
                            try:
                                q.put_nowait(chunk)
                            except asyncio.QueueFull:
                                # drop
                                pass
        except Exception as e:
            logger.exception('Stream session failed: %s', e)
        finally:
            self.active = False
            for q in list(self.queues):
                try:
                    q.put_nowait(None)
                except Exception:
                    pass


class StreamManager:
    def __init__(self):
        self.sessions: Dict[int, StreamSession] = {}

    async def get_stream_url(self, track_url: str) -> str | None:
        loop = asyncio.get_running_loop()
        try:
            info = await loop.run_in_executor(None, lambda: ytdl.extract_info(track_url, download=False))
            if not info:
                return None
            # pick best audio direct URL
            return info.get('url') or info.get('formats', [])[0].get('url')
        except Exception as e:
            logger.exception('failed to get stream url: %s', e)
            return None

    async def subscribe_track(self, track_id: int, track_url: str):
        if track_id in self.sessions:
            return self.sessions[track_id].subscribe()
        stream_url = await self.get_stream_url(track_url)
        if not stream_url:
            raise RuntimeError('no stream url')
        s = StreamSession(stream_url)
        self.sessions[track_id] = s
        return s.subscribe()

    def unsubscribe_track(self, track_id: int, q: asyncio.Queue):
        s = self.sessions.get(track_id)
        if s:
            s.unsubscribe(q)
            if not s.queues:
                if s.task:
                    s.task.cancel()
                del self.sessions[track_id]


# singleton
stream_manager = StreamManager()
