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
