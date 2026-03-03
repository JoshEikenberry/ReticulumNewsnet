# Reticulum-Newsnet Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Usenet-inspired, fully P2P threaded discussion system on the Reticulum Network Stack.

**Architecture:** Library-core pattern. All logic lives in `newsnet/` package. Thin CLI and TUI frontends import the library. SQLite storage, announce-based peer discovery, recent-window article sync, mandatory cryptographic signing, local whitelist/blacklist filtering with strict discard-on-receipt.

**Tech Stack:** Python 3.11+, rns (Reticulum), msgpack, sqlite3 (stdlib), tomllib (stdlib), curses (stdlib), argparse (stdlib)

**Design doc:** `docs/plans/2026-03-03-reticulum-newsnet-design.md`

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `newsnet/__init__.py`
- Create: `newsnet/config.py`
- Create: `cli/__init__.py`
- Create: `cli/main.py`
- Create: `tui/__init__.py`
- Create: `tui/app.py`
- Create: `config.example.toml`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

**Step 1: Initialize git repo**

```bash
cd /home/eik/reticulumtalk
git init
```

**Step 2: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "reticulum-newsnet"
version = "0.1.0"
description = "Usenet-inspired P2P threaded discussions on the Reticulum Network"
requires-python = ">=3.11"
dependencies = [
    "rns>=0.7.0",
    "umsgpack>=0.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
]

[project.scripts]
newsnet = "cli.main:main"
```

**Step 3: Create config module with tests**

Write the failing test first in `tests/test_config.py`:

```python
import os
import tempfile
from pathlib import Path
from newsnet.config import NewsnetConfig


def test_default_config():
    config = NewsnetConfig()
    assert config.display_name == "anonymous"
    assert config.retention_hours == 168
    assert config.sync_interval_minutes == 15
    assert config.strict_filtering is True


def test_config_from_toml():
    toml_content = """
display_name = "testuser"
retention_hours = 24
sync_interval_minutes = 5
strict_filtering = false
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(toml_content)
        f.flush()
        config = NewsnetConfig.from_file(f.name)

    os.unlink(f.name)
    assert config.display_name == "testuser"
    assert config.retention_hours == 24
    assert config.sync_interval_minutes == 5
    assert config.strict_filtering is False


def test_retention_hours_clamped():
    config = NewsnetConfig(retention_hours=0)
    assert config.retention_hours == 1
    config = NewsnetConfig(retention_hours=9999)
    assert config.retention_hours == 720


def test_config_dir():
    config = NewsnetConfig()
    assert config.config_dir == Path.home() / ".config" / "reticulum-newsnet"
    assert config.db_path == config.config_dir / "newsnet.db"
    assert config.identity_path == config.config_dir / "identity"
```

**Step 4: Run tests to verify they fail**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_config.py -v`
Expected: FAIL (module not found)

**Step 5: Implement config.py**

```python
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class NewsnetConfig:
    display_name: str = "anonymous"
    retention_hours: int = 168
    sync_interval_minutes: int = 15
    strict_filtering: bool = True

    def __post_init__(self):
        self.retention_hours = max(1, min(720, self.retention_hours))

    @property
    def config_dir(self) -> Path:
        return Path.home() / ".config" / "reticulum-newsnet"

    @property
    def db_path(self) -> Path:
        return self.config_dir / "newsnet.db"

    @property
    def identity_path(self) -> Path:
        return self.config_dir / "identity"

    @property
    def config_file_path(self) -> Path:
        return self.config_dir / "config.toml"

    @classmethod
    def from_file(cls, path: str | Path) -> NewsnetConfig:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def ensure_dirs(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
```

**Step 6: Create package __init__ files**

`newsnet/__init__.py`:
```python
"""Reticulum-newsnet: P2P threaded discussions on the Reticulum Network."""
```

`cli/__init__.py`, `tui/__init__.py`, `tests/__init__.py`: empty files.

`tui/app.py`:
```python
"""TUI frontend for reticulum-newsnet. To be implemented."""
```

`cli/main.py`:
```python
"""CLI frontend for reticulum-newsnet."""


def main():
    print("reticulum-newsnet: not yet implemented")


if __name__ == "__main__":
    main()
```

**Step 7: Create config.example.toml**

```toml
# Reticulum-Newsnet Configuration

# Your display name shown to other users
display_name = "your_name_here"

# How long to keep articles, in hours (1-720, default: 168 = 7 days)
# This controls both local retention and sync window
retention_hours = 168

# How often to sync with known peers, in minutes (default: 15)
sync_interval_minutes = 15

# When true, discard filtered articles on receipt (never store or forward)
# When false, store everything and filter only on display
strict_filtering = true
```

**Step 8: Run tests to verify they pass**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_config.py -v`
Expected: All 4 tests PASS

**Step 9: Commit**

```bash
git add pyproject.toml newsnet/ cli/ tui/ tests/ config.example.toml docs/
git commit -m "feat: project scaffolding with config module"
```

---

### Task 2: SQLite Store

**Files:**
- Create: `newsnet/store.py`
- Create: `tests/test_store.py`

**Step 1: Write failing tests**

`tests/test_store.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_store.py -v`
Expected: FAIL (module not found)

**Step 3: Implement store.py**

```python
from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class Store:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                message_id   TEXT PRIMARY KEY,
                author_hash  TEXT NOT NULL,
                author_key   BLOB NOT NULL,
                display_name TEXT NOT NULL,
                newsgroup    TEXT NOT NULL,
                subject      TEXT NOT NULL,
                body         TEXT NOT NULL,
                "references" TEXT,
                timestamp    REAL NOT NULL,
                signature    BLOB NOT NULL,
                received_at  REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_articles_newsgroup ON articles(newsgroup);
            CREATE INDEX IF NOT EXISTS idx_articles_timestamp ON articles(timestamp);
            CREATE INDEX IF NOT EXISTS idx_articles_received_at ON articles(received_at);

            CREATE TABLE IF NOT EXISTS peers (
                destination_hash TEXT PRIMARY KEY,
                display_name     TEXT,
                first_seen       REAL NOT NULL,
                last_seen        REAL NOT NULL,
                last_synced      REAL
            );

            CREATE TABLE IF NOT EXISTS filters (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                filter_type TEXT NOT NULL,
                filter_mode TEXT NOT NULL,
                pattern     TEXT NOT NULL,
                created_at  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tombstones (
                message_id TEXT PRIMARY KEY,
                created_at REAL NOT NULL
            );
        """)
        self._conn.commit()

    def store_article(self, article: dict):
        try:
            self._conn.execute(
                """INSERT INTO articles
                   (message_id, author_hash, author_key, display_name,
                    newsgroup, subject, body, "references", timestamp,
                    signature, received_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    article["message_id"],
                    article["author_hash"],
                    article["author_key"],
                    article["display_name"],
                    article["newsgroup"],
                    article["subject"],
                    article["body"],
                    article["references"],
                    article["timestamp"],
                    article["signature"],
                    article["received_at"],
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            pass  # duplicate, ignore

    def get_article(self, message_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM articles WHERE message_id = ?", (message_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_articles(self, newsgroup: str | None = None) -> list[dict]:
        if newsgroup:
            rows = self._conn.execute(
                "SELECT * FROM articles WHERE newsgroup = ? ORDER BY timestamp DESC",
                (newsgroup,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM articles ORDER BY timestamp DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def list_newsgroups(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT newsgroup FROM articles ORDER BY newsgroup"
        ).fetchall()
        return [r["newsgroup"] for r in rows]

    def get_article_ids_since(self, since_timestamp: float) -> list[tuple[str, float]]:
        rows = self._conn.execute(
            "SELECT message_id, timestamp FROM articles WHERE timestamp >= ?",
            (since_timestamp,),
        ).fetchall()
        return [(r["message_id"], r["timestamp"]) for r in rows]

    def cleanup(self, retention_seconds: float):
        cutoff = time.time() - retention_seconds
        self._conn.execute("DELETE FROM articles WHERE received_at < ?", (cutoff,))
        self._conn.execute("DELETE FROM tombstones WHERE created_at < ?", (cutoff,))
        self._conn.commit()

    def add_tombstone(self, message_id: str, created_at: float | None = None):
        ts = created_at if created_at is not None else time.time()
        try:
            self._conn.execute(
                "INSERT INTO tombstones (message_id, created_at) VALUES (?, ?)",
                (message_id, ts),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            pass

    def has_tombstone(self, message_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM tombstones WHERE message_id = ?", (message_id,)
        ).fetchone()
        return row is not None

    def upsert_peer(self, destination_hash: str, display_name: str | None, seen_at: float):
        self._conn.execute(
            """INSERT INTO peers (destination_hash, display_name, first_seen, last_seen)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(destination_hash) DO UPDATE SET
                   display_name = excluded.display_name,
                   last_seen = excluded.last_seen""",
            (destination_hash, display_name, seen_at, seen_at),
        )
        self._conn.commit()

    def update_peer_synced(self, destination_hash: str, synced_at: float):
        self._conn.execute(
            "UPDATE peers SET last_synced = ? WHERE destination_hash = ?",
            (synced_at, destination_hash),
        )
        self._conn.commit()

    def get_peer(self, destination_hash: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM peers WHERE destination_hash = ?", (destination_hash,)
        ).fetchone()
        return dict(row) if row else None

    def list_peers(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM peers ORDER BY last_seen DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def add_filter(self, filter_type: str, filter_mode: str, pattern: str) -> int:
        cursor = self._conn.execute(
            """INSERT INTO filters (filter_type, filter_mode, pattern, created_at)
               VALUES (?, ?, ?, ?)""",
            (filter_type, filter_mode, pattern, time.time()),
        )
        self._conn.commit()
        return cursor.lastrowid

    def remove_filter(self, filter_id: int):
        self._conn.execute("DELETE FROM filters WHERE id = ?", (filter_id,))
        self._conn.commit()

    def list_filters(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM filters ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self._conn.close()
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_store.py -v`
Expected: All 10 tests PASS

**Step 5: Commit**

```bash
git add newsnet/store.py tests/test_store.py
git commit -m "feat: SQLite store with articles, peers, filters, tombstones"
```

---

### Task 3: Article Model

**Files:**
- Create: `newsnet/article.py`
- Create: `tests/test_article.py`

**Step 1: Write failing tests**

`tests/test_article.py`:

```python
import json
import hashlib
import time
import umsgpack
from unittest.mock import MagicMock
from newsnet.article import Article


def make_mock_identity():
    identity = MagicMock()
    identity.hash = b"\x01" * 16
    identity.get_public_key.return_value = b"mock_public_key_32bytes_padding!!"
    identity.sign.side_effect = lambda data: b"mock_signature_" + data[:16]
    identity.validate.return_value = True
    return identity


def test_create_article():
    identity = make_mock_identity()
    article = Article.create(
        identity=identity,
        display_name="Alice",
        newsgroup="test.general",
        subject="Hello",
        body="Hello, world!",
        references=[],
    )
    assert article.newsgroup == "test.general"
    assert article.subject == "Hello"
    assert article.body == "Hello, world!"
    assert article.display_name == "Alice"
    assert article.author_hash == identity.hash.hex()
    assert article.signature is not None
    assert article.message_id is not None


def test_message_id_is_deterministic():
    identity = make_mock_identity()
    ts = 1700000000.0
    a1 = Article.create(identity, "Alice", "test.group", "Subj", "Body", [], timestamp=ts)
    a2 = Article.create(identity, "Alice", "test.group", "Subj", "Body", [], timestamp=ts)
    assert a1.message_id == a2.message_id


def test_message_id_changes_with_content():
    identity = make_mock_identity()
    ts = 1700000000.0
    a1 = Article.create(identity, "Alice", "test.group", "Subj", "Body A", [], timestamp=ts)
    a2 = Article.create(identity, "Alice", "test.group", "Subj", "Body B", [], timestamp=ts)
    assert a1.message_id != a2.message_id


def test_serialize_deserialize():
    identity = make_mock_identity()
    article = Article.create(identity, "Alice", "test.general", "Hello", "World", [])
    data = article.serialize()
    restored = Article.deserialize(data)
    assert restored.message_id == article.message_id
    assert restored.body == article.body
    assert restored.author_key == article.author_key
    assert restored.signature == article.signature


def test_verify_valid_article():
    identity = make_mock_identity()
    article = Article.create(identity, "Alice", "test.general", "Hello", "World", [])
    assert article.verify(identity) is True


def test_verify_tampered_article():
    identity = make_mock_identity()
    article = Article.create(identity, "Alice", "test.general", "Hello", "World", [])
    article.body = "Tampered!"
    assert article.verify(identity) is False


def test_to_dict():
    identity = make_mock_identity()
    article = Article.create(identity, "Alice", "test.general", "Hello", "World", [])
    d = article.to_store_dict()
    assert d["message_id"] == article.message_id
    assert d["newsgroup"] == "test.general"
    assert d["body"] == "World"
    assert isinstance(d["references"], str)  # JSON string
    assert isinstance(d["received_at"], float)


def test_unicode_body():
    identity = make_mock_identity()
    body = "Hei verden! \U0001f30d \u00e6\u00f8\u00e5 \u4e16\u754c \u0417\u0434\u0440\u0430\u0432\u0441\u0442\u0432\u0443\u0439"
    article = Article.create(identity, "Alice", "test.unicode", "Unicode", body, [])
    data = article.serialize()
    restored = Article.deserialize(data)
    assert restored.body == body
```

**Step 2: Run tests to verify they fail**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_article.py -v`
Expected: FAIL (module not found)

**Step 3: Implement article.py**

```python
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field

import umsgpack


@dataclass
class Article:
    message_id: str
    author_hash: str
    author_key: bytes
    display_name: str
    newsgroup: str
    subject: str
    body: str
    references: list[str]
    timestamp: float
    signature: bytes

    @staticmethod
    def compute_message_id(
        newsgroup: str, subject: str, body: str, author_hash: str, timestamp: float
    ) -> str:
        canonical = (
            newsgroup + "\n" + subject + "\n" + body + "\n"
            + author_hash + "\n" + str(timestamp)
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def create(
        cls,
        identity,
        display_name: str,
        newsgroup: str,
        subject: str,
        body: str,
        references: list[str],
        timestamp: float | None = None,
    ) -> Article:
        ts = timestamp if timestamp is not None else time.time()
        author_hash = identity.hash.hex()
        message_id = cls.compute_message_id(newsgroup, subject, body, author_hash, ts)
        signature = identity.sign(message_id.encode("utf-8"))
        return cls(
            message_id=message_id,
            author_hash=author_hash,
            author_key=identity.get_public_key(),
            display_name=display_name,
            newsgroup=newsgroup,
            subject=subject,
            body=body,
            references=references,
            timestamp=ts,
            signature=signature,
        )

    def verify(self, identity) -> bool:
        expected_id = self.compute_message_id(
            self.newsgroup, self.subject, self.body, self.author_hash, self.timestamp
        )
        if expected_id != self.message_id:
            return False
        return identity.validate(self.signature, self.message_id.encode("utf-8"))

    def serialize(self) -> bytes:
        return umsgpack.packb({
            "message_id": self.message_id,
            "author_hash": self.author_hash,
            "author_key": self.author_key,
            "display_name": self.display_name,
            "newsgroup": self.newsgroup,
            "subject": self.subject,
            "body": self.body,
            "references": self.references,
            "timestamp": self.timestamp,
            "signature": self.signature,
        })

    @classmethod
    def deserialize(cls, data: bytes) -> Article:
        d = umsgpack.unpackb(data)
        return cls(
            message_id=d["message_id"],
            author_hash=d["author_hash"],
            author_key=d["author_key"],
            display_name=d["display_name"],
            newsgroup=d["newsgroup"],
            subject=d["subject"],
            body=d["body"],
            references=d["references"],
            timestamp=d["timestamp"],
            signature=d["signature"],
        )

    def to_store_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "author_hash": self.author_hash,
            "author_key": self.author_key,
            "display_name": self.display_name,
            "newsgroup": self.newsgroup,
            "subject": self.subject,
            "body": self.body,
            "references": json.dumps(self.references),
            "timestamp": self.timestamp,
            "signature": self.signature,
            "received_at": time.time(),
        }
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_article.py -v`
Expected: All 8 tests PASS

**Step 5: Commit**

```bash
git add newsnet/article.py tests/test_article.py
git commit -m "feat: article model with signing, verification, serialization"
```

---

### Task 4: Filter Engine

**Files:**
- Create: `newsnet/filters.py`
- Create: `tests/test_filters.py`

**Step 1: Write failing tests**

`tests/test_filters.py`:

```python
from newsnet.filters import FilterEngine


def make_article_dict(**overrides):
    base = {
        "author_hash": "author_aaa",
        "newsgroup": "test.general",
        "subject": "Test Subject",
        "body": "Test body content",
    }
    base.update(overrides)
    return base


def test_no_filters_passes_everything():
    engine = FilterEngine([])
    article = make_article_dict()
    assert engine.should_keep(article) is True


def test_author_blacklist():
    filters = [{"filter_type": "author", "filter_mode": "blacklist", "pattern": "bad_author"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(author_hash="bad_author")) is False
    assert engine.should_keep(make_article_dict(author_hash="good_author")) is True


def test_author_whitelist():
    filters = [{"filter_type": "author", "filter_mode": "whitelist", "pattern": "friend1"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(author_hash="friend1")) is True
    assert engine.should_keep(make_article_dict(author_hash="stranger")) is False


def test_newsgroup_blacklist():
    filters = [{"filter_type": "newsgroup", "filter_mode": "blacklist", "pattern": "spam.ads"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(newsgroup="spam.ads")) is False
    assert engine.should_keep(make_article_dict(newsgroup="tech.linux")) is True


def test_newsgroup_blacklist_glob():
    filters = [{"filter_type": "newsgroup", "filter_mode": "blacklist", "pattern": "spam.*"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(newsgroup="spam.ads")) is False
    assert engine.should_keep(make_article_dict(newsgroup="spam.scam.pills")) is False
    assert engine.should_keep(make_article_dict(newsgroup="tech.linux")) is True


def test_newsgroup_whitelist_glob():
    filters = [{"filter_type": "newsgroup", "filter_mode": "whitelist", "pattern": "tech.*"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(newsgroup="tech.linux")) is True
    assert engine.should_keep(make_article_dict(newsgroup="music.jazz")) is False


def test_word_blacklist_in_body():
    filters = [{"filter_type": "word", "filter_mode": "blacklist", "pattern": "viagra"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(body="Buy cheap viagra now!")) is False
    assert engine.should_keep(make_article_dict(body="A normal post")) is True


def test_word_blacklist_in_subject():
    filters = [{"filter_type": "word", "filter_mode": "blacklist", "pattern": "viagra"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(subject="Viagra deals")) is False


def test_word_blacklist_case_insensitive():
    filters = [{"filter_type": "word", "filter_mode": "blacklist", "pattern": "SPAM"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(body="This is spam")) is False
    assert engine.should_keep(make_article_dict(body="This is Spam")) is False


def test_word_whitelist():
    filters = [{"filter_type": "word", "filter_mode": "whitelist", "pattern": "python"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(body="I love python")) is True
    assert engine.should_keep(make_article_dict(body="I love javascript")) is False


def test_whitelist_priority_over_blacklist():
    filters = [
        {"filter_type": "author", "filter_mode": "whitelist", "pattern": "friend1"},
        {"filter_type": "author", "filter_mode": "blacklist", "pattern": "friend1"},
    ]
    engine = FilterEngine(filters)
    # Whitelist exists, so only whitelisted authors pass. friend1 is whitelisted.
    assert engine.should_keep(make_article_dict(author_hash="friend1")) is True


def test_combined_filters():
    filters = [
        {"filter_type": "newsgroup", "filter_mode": "whitelist", "pattern": "tech.*"},
        {"filter_type": "word", "filter_mode": "blacklist", "pattern": "spam"},
    ]
    engine = FilterEngine(filters)
    # In tech group, no spam word -> keep
    assert engine.should_keep(make_article_dict(newsgroup="tech.linux", body="Good stuff")) is True
    # In tech group, has spam word -> discard
    assert engine.should_keep(make_article_dict(newsgroup="tech.linux", body="Buy spam")) is False
    # Not in tech group -> discard (whitelist fails)
    assert engine.should_keep(make_article_dict(newsgroup="music.jazz", body="Good stuff")) is False
```

**Step 2: Run tests to verify they fail**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_filters.py -v`
Expected: FAIL (module not found)

**Step 3: Implement filters.py**

```python
from __future__ import annotations

import fnmatch


class FilterEngine:
    def __init__(self, filters: list[dict]):
        self._filters = filters

    def should_keep(self, article: dict) -> bool:
        if not self._check_type("author", article.get("author_hash", "")):
            return False
        if not self._check_type("newsgroup", article.get("newsgroup", "")):
            return False
        if not self._check_type_word(article):
            return False
        return True

    def _check_type(self, filter_type: str, value: str) -> bool:
        whitelists = [
            f["pattern"] for f in self._filters
            if f["filter_type"] == filter_type and f["filter_mode"] == "whitelist"
        ]
        blacklists = [
            f["pattern"] for f in self._filters
            if f["filter_type"] == filter_type and f["filter_mode"] == "blacklist"
        ]
        if whitelists:
            if not any(fnmatch.fnmatch(value, p) for p in whitelists):
                return False
        if blacklists:
            if any(fnmatch.fnmatch(value, p) for p in blacklists):
                return False
        return True

    def _check_type_word(self, article: dict) -> bool:
        text = (article.get("subject", "") + " " + article.get("body", "")).lower()
        whitelists = [
            f["pattern"].lower() for f in self._filters
            if f["filter_type"] == "word" and f["filter_mode"] == "whitelist"
        ]
        blacklists = [
            f["pattern"].lower() for f in self._filters
            if f["filter_type"] == "word" and f["filter_mode"] == "blacklist"
        ]
        if whitelists:
            if not any(w in text for w in whitelists):
                return False
        if blacklists:
            if any(w in text for w in blacklists):
                return False
        return True
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_filters.py -v`
Expected: All 12 tests PASS

**Step 5: Commit**

```bash
git add newsnet/filters.py tests/test_filters.py
git commit -m "feat: filter engine with whitelist/blacklist for authors, newsgroups, words"
```

---

### Task 5: Identity Management

**Files:**
- Create: `newsnet/identity.py`
- Create: `tests/test_identity.py`

This task requires the `rns` package. Tests will use mocks for the Reticulum
Identity class so they can run without a live Reticulum instance.

**Step 1: Write failing tests**

`tests/test_identity.py`:

```python
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from newsnet.identity import IdentityManager


def test_create_new_identity(tmp_path):
    identity_path = tmp_path / "identity"
    with patch("newsnet.identity.RNS") as mock_rns:
        mock_identity = MagicMock()
        mock_identity.hash = b"\x01" * 16
        mock_identity.get_public_key.return_value = b"pubkey"
        mock_rns.Identity.return_value = mock_identity
        mock_rns.Identity.from_file.return_value = None

        mgr = IdentityManager(str(identity_path))
        identity = mgr.get_or_create()

        assert identity is mock_identity
        mock_identity.to_file.assert_called_once_with(str(identity_path))


def test_load_existing_identity(tmp_path):
    identity_path = tmp_path / "identity"
    identity_path.touch()
    with patch("newsnet.identity.RNS") as mock_rns:
        mock_identity = MagicMock()
        mock_identity.hash = b"\x02" * 16
        mock_rns.Identity.from_file.return_value = mock_identity

        mgr = IdentityManager(str(identity_path))
        identity = mgr.get_or_create()

        assert identity is mock_identity
        mock_rns.Identity.from_file.assert_called_once_with(str(identity_path))


def test_identity_hash_hex(tmp_path):
    identity_path = tmp_path / "identity"
    with patch("newsnet.identity.RNS") as mock_rns:
        mock_identity = MagicMock()
        mock_identity.hash = bytes.fromhex("abcdef0123456789abcdef0123456789")
        mock_rns.Identity.return_value = mock_identity
        mock_rns.Identity.from_file.return_value = None

        mgr = IdentityManager(str(identity_path))
        mgr.get_or_create()
        assert mgr.hash_hex == "abcdef0123456789abcdef0123456789"
```

**Step 2: Run tests to verify they fail**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_identity.py -v`
Expected: FAIL (module not found)

**Step 3: Implement identity.py**

```python
from __future__ import annotations

from pathlib import Path

import RNS


class IdentityManager:
    def __init__(self, identity_path: str | Path):
        self._path = str(identity_path)
        self._identity = None

    def get_or_create(self) -> RNS.Identity:
        if self._identity is not None:
            return self._identity

        if Path(self._path).exists():
            self._identity = RNS.Identity.from_file(self._path)

        if self._identity is None:
            self._identity = RNS.Identity()
            self._identity.to_file(self._path)

        return self._identity

    @property
    def identity(self) -> RNS.Identity:
        if self._identity is None:
            return self.get_or_create()
        return self._identity

    @property
    def hash_hex(self) -> str:
        return self.identity.hash.hex()
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_identity.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add newsnet/identity.py tests/test_identity.py
git commit -m "feat: identity manager for creating and loading Reticulum identities"
```

---

### Task 6: Sync Engine - Message Types

**Files:**
- Create: `newsnet/sync.py`
- Create: `tests/test_sync.py`

This is the first part of the sync engine: the custom Reticulum Channel message
types used during sync. The actual peer discovery and sync orchestration come
in Task 7.

**Step 1: Write failing tests**

`tests/test_sync.py`:

```python
import umsgpack
from newsnet.sync import ArticleIDListMessage, ArticleRequestMessage, ArticleDataMessage


def test_article_id_list_roundtrip():
    ids = [("abc123", 1700000000.0), ("def456", 1700000001.0)]
    msg = ArticleIDListMessage(ids)
    packed = msg.pack()
    restored = ArticleIDListMessage()
    restored.unpack(packed)
    assert restored.article_ids == ids


def test_article_request_roundtrip():
    ids = ["abc123", "def456", "ghi789"]
    msg = ArticleRequestMessage(ids)
    packed = msg.pack()
    restored = ArticleRequestMessage()
    restored.unpack(packed)
    assert restored.requested_ids == ids


def test_article_data_roundtrip():
    articles = [b"serialized_article_1", b"serialized_article_2"]
    msg = ArticleDataMessage(articles)
    packed = msg.pack()
    restored = ArticleDataMessage()
    restored.unpack(packed)
    assert restored.articles == articles


def test_empty_id_list():
    msg = ArticleIDListMessage([])
    packed = msg.pack()
    restored = ArticleIDListMessage()
    restored.unpack(packed)
    assert restored.article_ids == []


def test_empty_request():
    msg = ArticleRequestMessage([])
    packed = msg.pack()
    restored = ArticleRequestMessage()
    restored.unpack(packed)
    assert restored.requested_ids == []
```

**Step 2: Run tests to verify they fail**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_sync.py -v`
Expected: FAIL (module not found)

**Step 3: Implement sync message types in sync.py**

```python
from __future__ import annotations

import umsgpack


class ArticleIDListMessage:
    """Carries a list of (message_id, timestamp) tuples during sync."""
    MSGTYPE = 0x0101

    def __init__(self, article_ids: list[tuple[str, float]] | None = None):
        self.article_ids = article_ids or []

    def pack(self) -> bytes:
        return umsgpack.packb(self.article_ids)

    def unpack(self, raw: bytes):
        self.article_ids = umsgpack.unpackb(raw)


class ArticleRequestMessage:
    """Requests specific articles by message_id."""
    MSGTYPE = 0x0102

    def __init__(self, requested_ids: list[str] | None = None):
        self.requested_ids = requested_ids or []

    def pack(self) -> bytes:
        return umsgpack.packb(self.requested_ids)

    def unpack(self, raw: bytes):
        self.requested_ids = umsgpack.unpackb(raw)


class ArticleDataMessage:
    """Carries serialized article data."""
    MSGTYPE = 0x0103

    def __init__(self, articles: list[bytes] | None = None):
        self.articles = articles or []

    def pack(self) -> bytes:
        return umsgpack.packb(self.articles)

    def unpack(self, raw: bytes):
        self.articles = umsgpack.unpackb(raw)
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_sync.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add newsnet/sync.py tests/test_sync.py
git commit -m "feat: sync protocol message types for article exchange"
```

---

### Task 7: Sync Engine - Peer Discovery and Orchestration

**Files:**
- Modify: `newsnet/sync.py`
- Create: `tests/test_sync_engine.py`

This adds the `SyncEngine` class that handles announce-based peer discovery,
periodic sync scheduling, and the full sync handshake. Tests use mocks for
Reticulum primitives.

**Step 1: Write failing tests**

`tests/test_sync_engine.py`:

```python
import time
from unittest.mock import MagicMock, patch, call
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
    # Never synced -> should sync
    assert engine.should_sync_peer({"last_synced": None}) is True
    # Synced long ago -> should sync
    assert engine.should_sync_peer({"last_synced": time.time() - 3600}) is True
    # Synced recently -> should not sync
    assert engine.should_sync_peer({"last_synced": time.time() - 60}) is False
```

**Step 2: Run tests to verify they fail**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_sync_engine.py -v`
Expected: FAIL (SyncEngine not found)

**Step 3: Add SyncEngine to sync.py**

Append to `newsnet/sync.py`:

```python
import time

from newsnet.article import Article
from newsnet.filters import FilterEngine
from newsnet.store import Store


class SyncEngine:
    def __init__(
        self,
        store: Store,
        identity,
        retention_hours: int,
        sync_interval_minutes: int,
    ):
        self.store = store
        self.identity = identity
        self.retention_hours = retention_hours
        self.sync_interval_minutes = sync_interval_minutes

    @property
    def retention_seconds(self) -> float:
        return self.retention_hours * 3600

    @property
    def sync_interval_seconds(self) -> float:
        return self.sync_interval_minutes * 60

    def get_local_article_ids(self) -> list[tuple[str, float]]:
        since = time.time() - self.retention_seconds
        return self.store.get_article_ids_since(since)

    def compute_missing_ids(
        self, local_ids: set[tuple[str, float]], remote_ids: list[tuple[str, float]]
    ) -> list[str]:
        local_msg_ids = {mid for mid, _ in local_ids}
        missing = []
        for mid, _ in remote_ids:
            if mid not in local_msg_ids and not self.store.has_tombstone(mid):
                missing.append(mid)
        return missing

    def should_sync_peer(self, peer: dict) -> bool:
        if peer.get("last_synced") is None:
            return True
        elapsed = time.time() - peer["last_synced"]
        return elapsed >= self.sync_interval_seconds

    def process_received_article(self, article_data: bytes) -> bool:
        """Deserialize, verify, filter, and store an article.

        Returns True if the article was stored, False if discarded.
        """
        try:
            article = Article.deserialize(article_data)
        except Exception:
            return False

        # Verify signature
        from RNS import Identity as RNSIdentity
        author_identity = RNSIdentity(create_keys=False)
        author_identity.load_public_key(article.author_key)
        if not article.verify(author_identity):
            return False

        # Apply filters
        filters = self.store.list_filters()
        engine = FilterEngine(filters)
        article_dict = article.to_store_dict()
        if not engine.should_keep(article_dict):
            self.store.add_tombstone(article.message_id)
            return False

        # Store
        self.store.store_article(article_dict)
        return True
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_sync_engine.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add newsnet/sync.py tests/test_sync_engine.py
git commit -m "feat: sync engine with peer scheduling and article ID diffing"
```

---

### Task 8: Node Orchestrator

**Files:**
- Create: `newsnet/node.py`
- Create: `tests/test_node.py`

The Node class wires everything together: starts Reticulum, creates the
destination, registers announce handler, and manages the sync loop.

**Step 1: Write failing tests**

`tests/test_node.py`:

```python
from unittest.mock import patch, MagicMock, call
from newsnet.config import NewsnetConfig
from newsnet.node import Node


@patch("newsnet.node.RNS")
@patch("newsnet.node.IdentityManager")
@patch("newsnet.node.Store")
def test_node_init(MockStore, MockIdMgr, MockRNS):
    mock_identity = MagicMock()
    mock_identity.hash = b"\x01" * 16
    MockIdMgr.return_value.get_or_create.return_value = mock_identity
    MockRNS.Destination.return_value = MagicMock()

    config = NewsnetConfig(display_name="TestNode")
    node = Node(config)
    node.start()

    MockRNS.Reticulum.assert_called_once()
    MockIdMgr.return_value.get_or_create.assert_called_once()
    MockRNS.Destination.assert_called_once()


@patch("newsnet.node.RNS")
@patch("newsnet.node.IdentityManager")
@patch("newsnet.node.Store")
def test_node_announce(MockStore, MockIdMgr, MockRNS):
    mock_identity = MagicMock()
    mock_identity.hash = b"\x01" * 16
    MockIdMgr.return_value.get_or_create.return_value = mock_identity
    mock_dest = MagicMock()
    MockRNS.Destination.return_value = mock_dest

    config = NewsnetConfig(display_name="TestNode")
    node = Node(config)
    node.start()
    node.announce()

    mock_dest.announce.assert_called_once()


@patch("newsnet.node.RNS")
@patch("newsnet.node.IdentityManager")
@patch("newsnet.node.Store")
def test_node_post_article(MockStore, MockIdMgr, MockRNS):
    mock_identity = MagicMock()
    mock_identity.hash = b"\x01" * 16
    mock_identity.sign.return_value = b"sig"
    mock_identity.get_public_key.return_value = b"pubkey"
    MockIdMgr.return_value.get_or_create.return_value = mock_identity
    MockIdMgr.return_value.identity = mock_identity

    config = NewsnetConfig(display_name="TestNode")
    node = Node(config)
    node.start()
    article = node.post("test.general", "Hello", "Hello world!", [])

    assert article.newsgroup == "test.general"
    assert article.body == "Hello world!"
    MockStore.return_value.store_article.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_node.py -v`
Expected: FAIL (module not found)

**Step 3: Implement node.py**

```python
from __future__ import annotations

import time

import RNS

from newsnet.article import Article
from newsnet.config import NewsnetConfig
from newsnet.filters import FilterEngine
from newsnet.identity import IdentityManager
from newsnet.store import Store
from newsnet.sync import SyncEngine


class AnnounceHandler:
    def __init__(self, aspect_filter: str, callback):
        self.aspect_filter = aspect_filter
        self._callback = callback

    def received_announce(self, destination_hash, announced_identity, app_data):
        self._callback(destination_hash, announced_identity, app_data)


class Node:
    def __init__(self, config: NewsnetConfig):
        self.config = config
        self._reticulum = None
        self._identity_mgr = IdentityManager(str(config.identity_path))
        self._store = Store(str(config.db_path))
        self._destination = None
        self._sync_engine = None

    @property
    def store(self) -> Store:
        return self._store

    @property
    def sync_engine(self) -> SyncEngine:
        return self._sync_engine

    def start(self):
        self.config.ensure_dirs()
        self._reticulum = RNS.Reticulum()
        identity = self._identity_mgr.get_or_create()

        self._destination = RNS.Destination(
            identity,
            RNS.Destination.IN,
            RNS.Destination.SINGLE,
            "newsnet",
            "peer",
        )
        self._destination.set_link_established_callback(self._on_link_established)

        self._sync_engine = SyncEngine(
            store=self._store,
            identity=identity,
            retention_hours=self.config.retention_hours,
            sync_interval_minutes=self.config.sync_interval_minutes,
        )

        handler = AnnounceHandler("newsnet.peer", self._on_announce)
        RNS.Transport.register_announce_handler(handler)

    def announce(self):
        app_data = self.config.display_name.encode("utf-8")
        self._destination.announce(app_data=app_data)

    def post(
        self,
        newsgroup: str,
        subject: str,
        body: str,
        references: list[str],
    ) -> Article:
        identity = self._identity_mgr.identity
        article = Article.create(
            identity=identity,
            display_name=self.config.display_name,
            newsgroup=newsgroup,
            subject=subject,
            body=body,
            references=references,
        )
        self._store.store_article(article.to_store_dict())
        return article

    def _on_announce(self, destination_hash, announced_identity, app_data):
        display_name = app_data.decode("utf-8") if app_data else None
        dest_hex = destination_hash.hex() if isinstance(destination_hash, bytes) else str(destination_hash)
        self._store.upsert_peer(dest_hex, display_name, time.time())

    def _on_link_established(self, link):
        link.set_link_closed_callback(self._on_link_closed)

    def _on_link_closed(self, link):
        pass

    def cleanup(self):
        retention_seconds = self.config.retention_hours * 3600
        self._store.cleanup(retention_seconds)

    def shutdown(self):
        self._store.close()
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_node.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add newsnet/node.py tests/test_node.py
git commit -m "feat: node orchestrator with Reticulum integration and announce handling"
```

---

### Task 9: CLI Frontend

**Files:**
- Modify: `cli/main.py`
- Create: `tests/test_cli.py`

**Step 1: Write failing tests**

`tests/test_cli.py`:

```python
import sys
from unittest.mock import patch, MagicMock
from io import StringIO
from cli.main import build_parser


def test_parser_post():
    parser = build_parser()
    args = parser.parse_args(["post", "test.general", "--subject", "Hello"])
    assert args.command == "post"
    assert args.newsgroup == "test.general"
    assert args.subject == "Hello"


def test_parser_list():
    parser = build_parser()
    args = parser.parse_args(["list", "test.general"])
    assert args.command == "list"
    assert args.newsgroup == "test.general"


def test_parser_list_all():
    parser = build_parser()
    args = parser.parse_args(["list"])
    assert args.command == "list"
    assert args.newsgroup is None


def test_parser_read():
    parser = build_parser()
    args = parser.parse_args(["read", "abc123"])
    assert args.command == "read"
    assert args.message_id == "abc123"


def test_parser_groups():
    parser = build_parser()
    args = parser.parse_args(["groups"])
    assert args.command == "groups"


def test_parser_peers():
    parser = build_parser()
    args = parser.parse_args(["peers"])
    assert args.command == "peers"


def test_parser_identity():
    parser = build_parser()
    args = parser.parse_args(["identity"])
    assert args.command == "identity"


def test_parser_sync():
    parser = build_parser()
    args = parser.parse_args(["sync"])
    assert args.command == "sync"


def test_parser_filter_add_blacklist():
    parser = build_parser()
    args = parser.parse_args(["filter", "add", "--blacklist", "--author", "bad_hash"])
    assert args.filter_command == "add"
    assert args.blacklist is True
    assert args.author == "bad_hash"


def test_parser_filter_add_whitelist_group():
    parser = build_parser()
    args = parser.parse_args(["filter", "add", "--whitelist", "--group", "tech.*"])
    assert args.filter_command == "add"
    assert args.whitelist is True
    assert args.group == "tech.*"


def test_parser_filter_list():
    parser = build_parser()
    args = parser.parse_args(["filter", "list"])
    assert args.filter_command == "list"


def test_parser_filter_remove():
    parser = build_parser()
    args = parser.parse_args(["filter", "remove", "5"])
    assert args.filter_command == "remove"
    assert args.filter_id == 5
```

**Step 2: Run tests to verify they fail**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_cli.py -v`
Expected: FAIL (build_parser not found)

**Step 3: Implement cli/main.py**

```python
from __future__ import annotations

import argparse
import sys
import time
import json
from datetime import datetime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="newsnet",
        description="Reticulum-Newsnet: P2P threaded discussions",
    )
    sub = parser.add_subparsers(dest="command")

    # post
    post_p = sub.add_parser("post", help="Post an article")
    post_p.add_argument("newsgroup", help="Newsgroup to post to")
    post_p.add_argument("--subject", "-s", required=True, help="Article subject")

    # read
    read_p = sub.add_parser("read", help="Read an article")
    read_p.add_argument("message_id", help="Message ID to read")

    # list
    list_p = sub.add_parser("list", help="List articles")
    list_p.add_argument("newsgroup", nargs="?", default=None, help="Filter by newsgroup")

    # groups
    sub.add_parser("groups", help="List known newsgroups")

    # sync
    sub.add_parser("sync", help="Trigger sync with all peers")

    # peers
    sub.add_parser("peers", help="List known peers")

    # identity
    sub.add_parser("identity", help="Show your identity")

    # tui
    sub.add_parser("tui", help="Launch interactive TUI")

    # filter
    filter_p = sub.add_parser("filter", help="Manage filters")
    filter_sub = filter_p.add_subparsers(dest="filter_command")

    filter_add = filter_sub.add_parser("add", help="Add a filter")
    filter_add.add_argument("--blacklist", action="store_true")
    filter_add.add_argument("--whitelist", action="store_true")
    filter_add.add_argument("--author", default=None, help="Author identity hash")
    filter_add.add_argument("--group", default=None, help="Newsgroup pattern")
    filter_add.add_argument("--word", default=None, help="Word to filter")

    filter_sub.add_parser("list", help="List filters")

    filter_rm = filter_sub.add_parser("remove", help="Remove a filter")
    filter_rm.add_argument("filter_id", type=int, help="Filter ID to remove")

    return parser


def cmd_post(node, args):
    print("Enter article body (Ctrl+D to finish):")
    body = sys.stdin.read()
    article = node.post(args.newsgroup, args.subject, body.rstrip("\n"), [])
    print(f"Posted: {article.message_id}")


def cmd_read(node, args):
    article = node.store.get_article(args.message_id)
    if article is None:
        print(f"Article not found: {args.message_id}")
        return
    ts = datetime.fromtimestamp(article["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
    print(f"Newsgroup: {article['newsgroup']}")
    print(f"From:      {article['display_name']} ({article['author_hash'][:16]}...)")
    print(f"Date:      {ts}")
    print(f"Subject:   {article['subject']}")
    print(f"ID:        {article['message_id']}")
    refs = json.loads(article["references"]) if article["references"] else []
    if refs:
        print(f"Refs:      {', '.join(refs)}")
    print()
    print(article["body"])


def cmd_list(node, args):
    articles = node.store.list_articles(newsgroup=args.newsgroup)
    if not articles:
        print("No articles found.")
        return
    for a in articles:
        ts = datetime.fromtimestamp(a["timestamp"]).strftime("%Y-%m-%d %H:%M")
        print(f"  {a['message_id'][:12]}  {ts}  {a['newsgroup']:20s}  {a['display_name']:12s}  {a['subject']}")


def cmd_groups(node, args):
    groups = node.store.list_newsgroups()
    if not groups:
        print("No newsgroups found.")
        return
    for g in groups:
        print(f"  {g}")


def cmd_peers(node, args):
    peers = node.store.list_peers()
    if not peers:
        print("No peers found.")
        return
    for p in peers:
        last = datetime.fromtimestamp(p["last_seen"]).strftime("%Y-%m-%d %H:%M") if p["last_seen"] else "never"
        synced = datetime.fromtimestamp(p["last_synced"]).strftime("%Y-%m-%d %H:%M") if p["last_synced"] else "never"
        name = p["display_name"] or "(unknown)"
        print(f"  {p['destination_hash'][:16]}  {name:16s}  seen: {last}  synced: {synced}")


def cmd_identity(node, args):
    print(f"Identity: {node._identity_mgr.hash_hex}")
    print(f"Display:  {node.config.display_name}")


def cmd_filter(node, args):
    if args.filter_command == "add":
        mode = "whitelist" if args.whitelist else "blacklist"
        if args.author:
            ftype, pattern = "author", args.author
        elif args.group:
            ftype, pattern = "newsgroup", args.group
        elif args.word:
            ftype, pattern = "word", args.word
        else:
            print("Specify --author, --group, or --word")
            return
        fid = node.store.add_filter(ftype, mode, pattern)
        print(f"Filter added (id={fid}): {mode} {ftype} '{pattern}'")

    elif args.filter_command == "list":
        filters = node.store.list_filters()
        if not filters:
            print("No filters configured.")
            return
        for f in filters:
            print(f"  [{f['id']}] {f['filter_mode']:10s} {f['filter_type']:10s} {f['pattern']}")

    elif args.filter_command == "remove":
        node.store.remove_filter(args.filter_id)
        print(f"Filter {args.filter_id} removed.")


COMMANDS = {
    "post": cmd_post,
    "read": cmd_read,
    "list": cmd_list,
    "groups": cmd_groups,
    "peers": cmd_peers,
    "identity": cmd_identity,
    "filter": cmd_filter,
    "sync": lambda node, args: print("Sync triggered (not yet implemented)"),
    "tui": lambda node, args: print("TUI not yet implemented"),
}


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    from newsnet.config import NewsnetConfig
    from newsnet.node import Node

    config_path = NewsnetConfig().config_file_path
    if config_path.exists():
        config = NewsnetConfig.from_file(config_path)
    else:
        config = NewsnetConfig()

    node = Node(config)
    node.start()

    try:
        COMMANDS[args.command](node, args)
    finally:
        node.shutdown()


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/test_cli.py -v`
Expected: All 12 tests PASS

**Step 5: Commit**

```bash
git add cli/main.py tests/test_cli.py
git commit -m "feat: CLI frontend with all commands"
```

---

### Task 10: Integration Wiring and First Run

**Files:**
- Modify: `newsnet/__init__.py` (add version)
- Create: `.gitignore`

**Step 1: Create .gitignore**

```
__pycache__/
*.pyc
*.egg-info/
dist/
build/
.venv/
*.db
```

**Step 2: Update newsnet/__init__.py**

```python
"""Reticulum-newsnet: P2P threaded discussions on the Reticulum Network."""

__version__ = "0.1.0"
```

**Step 3: Run full test suite**

Run: `cd /home/eik/reticulumtalk && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 4: Install in development mode and verify CLI**

```bash
cd /home/eik/reticulumtalk
pip install -e ".[dev]"
newsnet --help
```

Expected: Help output showing all subcommands.

**Step 5: Commit**

```bash
git add .gitignore newsnet/__init__.py
git commit -m "feat: gitignore and version, project ready for first run"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | Project scaffolding + config | 4 |
| 2 | SQLite store | 10 |
| 3 | Article model | 8 |
| 4 | Filter engine | 12 |
| 5 | Identity management | 3 |
| 6 | Sync message types | 5 |
| 7 | Sync engine orchestration | 4 |
| 8 | Node orchestrator | 3 |
| 9 | CLI frontend | 12 |
| 10 | Integration wiring | full suite |

**Total: 10 tasks, ~61 tests**

Tasks 1-5 are independent of Reticulum and can be developed and tested without
a live Reticulum instance. Tasks 6-8 introduce Reticulum integration but use
mocks for testing. Task 9 is the CLI layer. Task 10 wires everything together.

The TUI (curses interface) is intentionally deferred to a follow-up plan, as it
needs its own design pass for layout, keybindings, and interaction patterns.
