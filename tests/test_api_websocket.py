"""Tests for WebSocket hub broadcast behavior."""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.websocket import WebSocketHub


@pytest.mark.asyncio
async def test_hub_broadcasts_to_connected_client():
    hub = WebSocketHub()
    ws = AsyncMock()
    await hub.connect(ws)
    await hub.broadcast({"type": "test_event", "value": 42})
    ws.send_text.assert_called_once()
    import json
    sent = json.loads(ws.send_text.call_args[0][0])
    assert sent["type"] == "test_event"
    assert sent["value"] == 42


@pytest.mark.asyncio
async def test_hub_removes_dead_clients_on_broadcast():
    hub = WebSocketHub()
    dead_ws = AsyncMock()
    dead_ws.send_text.side_effect = RuntimeError("connection closed")
    await hub.connect(dead_ws)
    # Should not raise, should remove the dead client
    await hub.broadcast({"type": "ping"})
    assert len(hub._clients) == 0


@pytest.mark.asyncio
async def test_hub_disconnect_removes_client():
    hub = WebSocketHub()
    ws = AsyncMock()
    await hub.connect(ws)
    assert len(hub._clients) == 1
    await hub.disconnect(ws)
    assert len(hub._clients) == 0
