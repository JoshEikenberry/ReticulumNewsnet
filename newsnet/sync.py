from __future__ import annotations

import time

import umsgpack

from newsnet.article import Article
from newsnet.filters import FilterEngine
from newsnet.store import Store


class ArticleIDListMessage:
    """Carries a list of (message_id, timestamp) tuples during sync."""
    MSGTYPE = 0x0101

    def __init__(self, article_ids: list[tuple[str, float]] | None = None):
        self.article_ids = article_ids or []

    def pack(self) -> bytes:
        return umsgpack.packb(self.article_ids)

    def unpack(self, raw: bytes):
        data = umsgpack.unpackb(raw)
        self.article_ids = [(mid, ts) for mid, ts in data]


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

        self.store.store_article(article_dict)
        return True
