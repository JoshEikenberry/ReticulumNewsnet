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
    hub = WebSocketHub()
    node = node_mock or MagicMock()
    # Use the node's config if it has one with the right token, else create one
    if node_mock is not None and hasattr(node_mock, 'config') and node_mock.config is not None:
        config = node_mock.config
    else:
        config = NewsnetConfig(api_token=TOKEN, display_name="testuser")
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


def test_get_identity():
    node = MagicMock()
    node.config = NewsnetConfig(api_token=TOKEN, display_name="alice")
    node._identity_mgr = MagicMock()
    node._identity_mgr.identity = MagicMock()
    node._identity_mgr.identity.hash = b"\xa3\xf9\xd2\xc1" + b"\x00" * 12
    node._identity_mgr.identity.get_public_key.return_value = b"\x00" * 32
    client = _make_client(node)
    r = client.get("/api/identity", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    data = r.json()
    assert data["display_name"] == "alice"
    assert "identity_hash" in data


def test_get_config():
    client = _make_client()
    r = client.get("/api/config", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    data = r.json()
    assert "display_name" in data
    assert "retention_hours" in data


def test_patch_config_immediate_field():
    node = MagicMock()
    node.config = NewsnetConfig(api_token=TOKEN, display_name="old")
    node.config.config_dir_override = "/tmp/test-newsnet-cfg"
    client = _make_client(node)
    r = client.patch(
        "/api/config",
        json={"display_name": "new"},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert r.status_code == 200
    assert r.json().get("restart_required") is False


def test_patch_config_invalid_retention():
    client = _make_client()
    r = client.patch(
        "/api/config",
        json={"retention_hours": 9999},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert r.status_code == 422


def test_patch_config_restart_required_field():
    node = MagicMock()
    node.config = NewsnetConfig(api_token=TOKEN)
    node.config.config_dir_override = "/tmp/test-newsnet-cfg2"
    client = _make_client(node)
    r = client.patch(
        "/api/config",
        json={"api_port": 9999},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert r.status_code == 200
    assert r.json()["restart_required"] is True


def test_list_groups():
    node = MagicMock()
    node.config = NewsnetConfig(api_token=TOKEN)
    node.store.list_newsgroups.return_value = ["tech.linux", "net.mesh"]
    client = _make_client(node)
    r = client.get("/api/groups", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    assert r.json() == ["tech.linux", "net.mesh"]


def test_list_articles_by_group():
    node = MagicMock()
    node.config = NewsnetConfig(api_token=TOKEN)
    node.store.list_articles.return_value = [
        {"message_id": "abc", "newsgroup": "tech.linux", "subject": "Hello",
         "body": "World", "author_hash": "x", "display_name": "alice",
         "timestamp": 1.0, "references": "[]", "received_at": 1.0}
    ]
    client = _make_client(node)
    r = client.get("/api/articles?group=tech.linux", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["message_id"] == "abc"


def test_get_single_article():
    node = MagicMock()
    node.config = NewsnetConfig(api_token=TOKEN)
    node.store.get_article.return_value = {
        "message_id": "abc123", "newsgroup": "tech.linux", "subject": "Hi",
        "body": "Body", "author_hash": "x", "display_name": "bob",
        "timestamp": 1.0, "references": "[]", "received_at": 1.0
    }
    node.store.list_articles.return_value = []
    client = _make_client(node)
    r = client.get("/api/articles/abc123", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    assert r.json()["message_id"] == "abc123"


def test_get_article_not_found():
    node = MagicMock()
    node.config = NewsnetConfig(api_token=TOKEN)
    node.store.get_article.return_value = None
    client = _make_client(node)
    r = client.get("/api/articles/nonexistent", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 404


def test_post_article():
    node = MagicMock()
    node.config = NewsnetConfig(api_token=TOKEN)
    mock_article = MagicMock()
    mock_article.message_id = "new-id-xyz"
    node.post.return_value = mock_article
    client = _make_client(node)
    r = client.post(
        "/api/articles",
        json={"newsgroup": "tech.linux", "subject": "Test", "body": "Hello", "references": []},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert r.status_code == 201
    assert r.json()["message_id"] == "new-id-xyz"


def test_list_peers():
    node = MagicMock()
    node.config = NewsnetConfig(api_token=TOKEN)
    node.store.list_peers.return_value = [
        {"destination_hash": "abc", "display_name": "bob", "first_seen": 1.0, "last_seen": 2.0, "last_synced": 2.0}
    ]
    node.list_tcp_peers.return_value = [{"address": "1.2.3.4:4965", "connected": True, "fail_count": 0}]
    client = _make_client(node)
    r = client.get("/api/peers", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    data = r.json()
    assert "rns_peers" in data
    assert "tcp_peers" in data


def test_add_tcp_peer():
    node = MagicMock()
    node.config = NewsnetConfig(api_token=TOKEN)
    node.add_tcp_peer.return_value = "1.2.3.4:4965"
    client = _make_client(node)
    r = client.post(
        "/api/peers",
        json={"address": "1.2.3.4:4965"},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert r.status_code == 201


def test_trigger_sync():
    node = MagicMock()
    node.config = NewsnetConfig(api_token=TOKEN)
    node.sync_all_peers.return_value = 2
    client = _make_client(node)
    r = client.post("/api/sync", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    assert r.json()["synced_peers"] == 2


def test_list_filters():
    node = MagicMock()
    node.config = NewsnetConfig(api_token=TOKEN)
    node.filter_store.list_filters.return_value = [
        {"type": "word", "mode": "blacklist", "pattern": "spam"}
    ]
    client = _make_client(node)
    r = client.get("/api/filters", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    assert len(r.json()) == 1


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
