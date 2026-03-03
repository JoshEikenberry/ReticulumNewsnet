import time
from unittest.mock import MagicMock
from newsnet.sync import SyncEngine


def make_mock_store():
    store = MagicMock()
    store.get_article_ids_since.return_value = [("local1", 1700000000.0)]
    store.has_tombstone.return_value = False
    store.get_article.return_value = {
        "message_id": "local1",
        "author_hash": "auth1",
        "author_key": b"key",
        "display_name": "Alice",
        "newsgroup": "test.general",
        "subject": "Hi",
        "body": "Hello",
        "references": "[]",
        "timestamp": 1700000000.0,
        "signature": b"sig",
        "received_at": 1700000000.0,
    }
    store.list_filters.return_value = []
    return store


def test_sync_engine_init():
    store = make_mock_store()
    engine = SyncEngine(
        store=store,
        identity=MagicMock(),
        retention_hours=168,
        sync_interval_minutes=15,
    )
    assert engine.retention_hours == 168
    assert engine.sync_interval_minutes == 15


def test_compute_missing_ids():
    store = make_mock_store()
    engine = SyncEngine(
        store=store,
        identity=MagicMock(),
        retention_hours=168,
        sync_interval_minutes=15,
    )
    local_ids = {("local1", 1.0), ("shared", 2.0)}
    remote_ids = [("shared", 2.0), ("remote1", 3.0), ("remote2", 4.0)]
    missing = engine.compute_missing_ids(local_ids, remote_ids)
    assert set(missing) == {"remote1", "remote2"}


def test_compute_missing_ids_excludes_tombstones():
    store = make_mock_store()
    store.has_tombstone.side_effect = lambda mid: mid == "remote1"
    engine = SyncEngine(
        store=store,
        identity=MagicMock(),
        retention_hours=168,
        sync_interval_minutes=15,
    )
    local_ids = set()
    remote_ids = [("remote1", 1.0), ("remote2", 2.0)]
    missing = engine.compute_missing_ids(local_ids, remote_ids)
    assert missing == ["remote2"]


def test_should_sync_peer():
    store = make_mock_store()
    engine = SyncEngine(
        store=store,
        identity=MagicMock(),
        retention_hours=168,
        sync_interval_minutes=15,
    )
    assert engine.should_sync_peer({"last_synced": None}) is True
    assert engine.should_sync_peer({"last_synced": time.time() - 3600}) is True
    assert engine.should_sync_peer({"last_synced": time.time() - 60}) is False
