"""Simple in-process broadcaster used for SSE push from bot to web clients."""
import asyncio
from typing import Set, Any


class Broadcaster:
    def __init__(self):
        self._queues: Set[asyncio.Queue] = set()
        self._handlers: Set[callable] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._queues.discard(q)
        except Exception:
            pass

    def register_handler(self, fn: callable) -> None:
        self._handlers.add(fn)

    def unregister_handler(self, fn: callable) -> None:
        try:
            self._handlers.discard(fn)
        except Exception:
            pass

    def publish(self, data: Any) -> None:
        # push into queues for SSE
        for q in list(self._queues):
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass
        # call registered handlers (non-blocking)
        loop = asyncio.get_event_loop()
        for h in list(self._handlers):
            try:
                loop.call_soon_threadsafe(asyncio.create_task, h(data))
            except Exception:
                try:
                    loop.call_soon_threadsafe(h, data)
                except Exception:
                    pass


# singleton
broadcaster = Broadcaster()
