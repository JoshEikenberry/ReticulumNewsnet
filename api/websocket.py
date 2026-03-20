from __future__ import annotations

import asyncio
import json
import logging

from fastapi import WebSocket

log = logging.getLogger(__name__)


class WebSocketHub:
    """Broadcast events to all connected WebSocket clients."""

    def __init__(self):
        self._clients: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._clients.append(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            try:
                self._clients.remove(ws)
            except ValueError:
                pass

    async def broadcast(self, event: dict):
        data = json.dumps(event)
        async with self._lock:
            dead: list[WebSocket] = []
            for ws in self._clients:
                try:
                    await ws.send_text(data)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._clients.remove(ws)

    def broadcast_sync(self, event: dict):
        """Fire-and-forget broadcast from a sync (non-async) thread."""
        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(self.broadcast(event), loop)
        except RuntimeError:
            log.debug("No running event loop for WebSocket broadcast")
