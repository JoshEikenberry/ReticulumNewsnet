from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class Store:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
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
