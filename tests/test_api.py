"""REST API endpoint tests using FastAPI TestClient."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from newsnet.config import NewsnetConfig
from api.app import create_app
from api.websocket import WebSocketHub


TOKEN = "test-token-xyz"


def _make_client(node_mock=None) -> TestClient:
    """Create a test client with the app in READY state and lifespan disabled.
    This is the standard helper for all tests that need a working API."""
    config = NewsnetConfig(api_token=TOKEN, display_name="testuser")
    hub = WebSocketHub()
    node = node_mock or MagicMock()
    node.config = config
    app = create_app(
        config=config, node=node, hub=hub,
        startup_state="ready", _lifespan_enabled=False,
    )
    return TestClient(app, raise_server_exceptions=True)


def test_unauthenticated_request_returns_401():
    client = _make_client()
    r = client.get("/api/groups")
    assert r.status_code == 401


def test_authenticated_request_passes():
    node = MagicMock()
    node.config = NewsnetConfig(api_token=TOKEN)
    node.store.list_newsgroups.return_value = []
    client = _make_client(node)
    r = client.get("/api/groups", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200


def test_starting_state_returns_503():
    """503 guard fires when startup_state="starting" and lifespan is disabled
    (so it can't flip to "ready" before the request is processed)."""
    config = NewsnetConfig(api_token=TOKEN)
    hub = WebSocketHub()
    node = MagicMock()
    node.config = config
    app = create_app(
        config=config, node=node, hub=hub,
        startup_state="starting", _lifespan_enabled=False,
    )
    client = TestClient(app, raise_server_exceptions=True)
    r = client.get("/api/groups", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 503
    assert r.json()["error"] == "starting up"
