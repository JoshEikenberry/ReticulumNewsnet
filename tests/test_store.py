import os
import tempfile
import time
import json
from newsnet.store import Store


def make_store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = Store(path)
    return store, path


def make_article(**overrides):
    base = {
        "message_id": "abc123",
        "author_hash": "author_hash_1",
        "author_key": b"fake_public_key",
        "display_name": "Alice",
        "newsgroup": "test.general",
        "subject": "Hello World",
        "body": "This is a test article.",
        "references": json.dumps([]),
        "timestamp": time.time(),
        "signature": b"fake_signature",
        "received_at": time.time(),
    }
    base.update(overrides)
    return base


def test_store_and_retrieve_article():
    store, path = make_store()
    article = make_article()
    store.store_article(article)
    result = store.get_article("abc123")
    assert result is not None
    assert result["message_id"] == "abc123"
    assert result["author_hash"] == "author_hash_1"
    assert result["body"] == "This is a test article."
    os.unlink(path)


def test_list_articles_by_newsgroup():
    store, path = make_store()
    store.store_article(make_article(message_id="a1", newsgroup="test.one"))
    store.store_article(make_article(message_id="a2", newsgroup="test.two"))
    store.store_article(make_article(message_id="a3", newsgroup="test.one"))
    results = store.list_articles(newsgroup="test.one")
    assert len(results) == 2
    ids = {r["message_id"] for r in results}
    assert ids == {"a1", "a3"}
    os.unlink(path)


def test_list_newsgroups():
    store, path = make_store()
    store.store_article(make_article(message_id="a1", newsgroup="tech.linux"))
    store.store_article(make_article(message_id="a2", newsgroup="music.jazz"))
    store.store_article(make_article(message_id="a3", newsgroup="tech.linux"))
    groups = store.list_newsgroups()
    assert set(groups) == {"tech.linux", "music.jazz"}
    os.unlink(path)


def test_get_article_ids_since():
    store, path = make_store()
    now = time.time()
    store.store_article(make_article(message_id="old", timestamp=now - 7200))
    store.store_article(make_article(message_id="new", timestamp=now - 60))
    ids = store.get_article_ids_since(now - 3600)
    assert len(ids) == 1
    assert ids[0][0] == "new"
    os.unlink(path)


def test_retention_cleanup():
    store, path = make_store()
    now = time.time()
    store.store_article(make_article(message_id="keep", received_at=now))
    store.store_article(make_article(message_id="expire", received_at=now - 100000))
    store.add_tombstone("tomb1", now - 100000)
    store.cleanup(retention_seconds=3600)
    assert store.get_article("keep") is not None
    assert store.get_article("expire") is None
    assert not store.has_tombstone("tomb1")
    os.unlink(path)


def test_tombstones():
    store, path = make_store()
    assert not store.has_tombstone("msg1")
    store.add_tombstone("msg1")
    assert store.has_tombstone("msg1")
    os.unlink(path)


def test_duplicate_article_ignored():
    store, path = make_store()
    article = make_article()
    store.store_article(article)
    store.store_article(article)  # should not raise
    results = store.list_articles()
    assert len(results) == 1
    os.unlink(path)


def test_store_and_list_peers():
    store, path = make_store()
    now = time.time()
    store.upsert_peer("hash1", "Peer One", now)
    store.upsert_peer("hash2", "Peer Two", now)
    peers = store.list_peers()
    assert len(peers) == 2
    store.update_peer_synced("hash1", now + 60)
    peer = store.get_peer("hash1")
    assert peer["last_synced"] == now + 60
    os.unlink(path)


def test_store_and_list_filters():
    store, path = make_store()
    fid = store.add_filter("author", "blacklist", "bad_author_hash")
    filters = store.list_filters()
    assert len(filters) == 1
    assert filters[0]["pattern"] == "bad_author_hash"
    store.remove_filter(fid)
    assert len(store.list_filters()) == 0
    os.unlink(path)
