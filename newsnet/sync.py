from __future__ import annotations

import logging
import threading
import time

import RNS
import RNS.Channel
import umsgpack

from newsnet.article import Article
from newsnet.filters import FilterEngine, TextFilterStore
from newsnet.store import Store

log = logging.getLogger(__name__)

# Maximum number of article IDs per channel message chunk
ID_CHUNK_SIZE = 40


class ArticleIDListMessage(RNS.Channel.MessageBase):
    """Carries a list of (message_id, timestamp) tuples during sync."""
    MSGTYPE = 0x0101

    def __init__(self, article_ids: list[tuple[str, float]] | None = None, is_final: bool = True):
        self.article_ids = article_ids or []
        self.is_final = is_final

    def pack(self) -> bytes:
        return umsgpack.packb({"ids": self.article_ids, "final": self.is_final})

    def unpack(self, raw: bytes):
        data = umsgpack.unpackb(raw)
        self.article_ids = [(mid, ts) for mid, ts in data["ids"]]
        self.is_final = data["final"]


class ArticleRequestMessage(RNS.Channel.MessageBase):
    """Requests specific articles by message_id."""
    MSGTYPE = 0x0102

    def __init__(self, requested_ids: list[str] | None = None):
        self.requested_ids = requested_ids or []

    def pack(self) -> bytes:
        return umsgpack.packb(self.requested_ids)

    def unpack(self, raw: bytes):
        self.requested_ids = umsgpack.unpackb(raw)


class ArticleDataMessage(RNS.Channel.MessageBase):
    """Carries serialized article data (small articles via channel)."""
    MSGTYPE = 0x0103

    def __init__(self, articles: list[bytes] | None = None):
        self.articles = articles or []

    def pack(self) -> bytes:
        return umsgpack.packb(self.articles)

    def unpack(self, raw: bytes):
        self.articles = umsgpack.unpackb(raw)


class SyncCompleteMessage(RNS.Channel.MessageBase):
    """Signals that one side has finished sending articles."""
    MSGTYPE = 0x0104

    def pack(self) -> bytes:
        return b""

    def unpack(self, raw: bytes):
        pass


class SyncEngine:
    def __init__(
        self,
        store: Store,
        identity,
        retention_hours: int,
        sync_interval_minutes: int,
        filter_store: TextFilterStore | None = None,
    ):
        self.store = store
        self.identity = identity
        self.retention_hours = retention_hours
        self.sync_interval_minutes = sync_interval_minutes
        self.filter_store = filter_store

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

    def process_received_article(
        self,
        article_data: bytes,
        requested_ids: set[str] | None = None,
    ) -> bool:
        try:
            article = Article.deserialize(article_data)
        except Exception:
            return False

        # Pull guarantee: reject articles that were not requested in this session
        if requested_ids is not None and article.message_id not in requested_ids:
            log.warning(
                f"Rejecting unrequested article {article.message_id[:16]} — "
                "pull model violation"
            )
            return False

        # Verify signature
        from RNS import Identity as RNSIdentity
        author_identity = RNSIdentity(create_keys=False)
        author_identity.load_public_key(article.author_key)
        if not article.verify(author_identity):
            return False

        # Apply filters
        filters = self.filter_store.list_filters() if self.filter_store else []
        engine = FilterEngine(filters)
        article_dict = article.to_store_dict()
        if not engine.should_keep(article_dict):
            self.store.add_tombstone(article.message_id)
            return False

        self.store.store_article(article_dict)
        return True


class SyncSession:
    """Manages one sync exchange over a link."""

    def __init__(self, link, sync_engine: SyncEngine, is_initiator: bool, on_complete=None):
        self.link = link
        self.sync_engine = sync_engine
        self.is_initiator = is_initiator
        self.on_complete = on_complete

        self._lock = threading.Lock()
        self._remote_ids: list[tuple[str, float]] = []
        self._remote_ids_complete = False
        self._local_complete = False
        self._remote_complete = False
        self._pending_resources = 0
        self._requested_ids: set[str] = set()

        channel = link.get_channel()
        channel.register_message_type(ArticleIDListMessage)
        channel.register_message_type(ArticleRequestMessage)
        channel.register_message_type(ArticleDataMessage)
        channel.register_message_type(SyncCompleteMessage)
        channel.add_message_handler(self._on_message)

        link.set_resource_strategy(RNS.Link.ACCEPT_ALL)
        link.set_resource_concluded_callback(self._resource_concluded)

    def start(self):
        """Send our article ID list in chunks."""
        local_ids = self.sync_engine.get_local_article_ids()
        channel = self.link.get_channel()

        if not local_ids:
            msg = ArticleIDListMessage([], is_final=True)
            channel.send(msg)
            return

        for i in range(0, len(local_ids), ID_CHUNK_SIZE):
            chunk = local_ids[i:i + ID_CHUNK_SIZE]
            is_final = (i + ID_CHUNK_SIZE) >= len(local_ids)
            msg = ArticleIDListMessage(chunk, is_final=is_final)
            channel.send(msg)

    def _on_message(self, message):
        if isinstance(message, ArticleIDListMessage):
            self._on_id_list(message)
            return True
        elif isinstance(message, ArticleRequestMessage):
            self._on_request(message)
            return True
        elif isinstance(message, SyncCompleteMessage):
            self._on_sync_complete()
            return True
        elif isinstance(message, ArticleDataMessage):
            self._on_article_data(message)
            return True
        return False

    def _on_id_list(self, message: ArticleIDListMessage):
        with self._lock:
            self._remote_ids.extend(message.article_ids)
            if not message.is_final:
                return

            self._remote_ids_complete = True
            local_ids = set(self.sync_engine.get_local_article_ids())
            missing = self.sync_engine.compute_missing_ids(local_ids, self._remote_ids)

        if missing:
            channel = self.link.get_channel()
            req = ArticleRequestMessage(missing)
            channel.send(req)
            with self._lock:
                self._requested_ids.update(missing)
        else:
            self._mark_local_complete()

    def _on_request(self, message: ArticleRequestMessage):
        store = self.sync_engine.store
        for mid in message.requested_ids:
            article_dict = store.get_article(mid)
            if article_dict is None:
                continue
            article = Article.from_store_dict(article_dict)
            data = article.serialize()
            # Send via RNS.Resource for large payloads
            RNS.Resource(data, self.link, callback=self._resource_sent)
            with self._lock:
                self._pending_resources += 1

        # If no articles were sent, mark complete immediately
        with self._lock:
            if self._pending_resources == 0:
                self._mark_local_complete_unlocked()

    def _resource_sent(self, resource):
        with self._lock:
            self._pending_resources -= 1
            if self._pending_resources <= 0:
                self._mark_local_complete_unlocked()

    def _on_article_data(self, message: ArticleDataMessage):
        """Handle small articles sent via channel. Only process if we requested them."""
        with self._lock:
            rids = set(self._requested_ids)
        for article_data in message.articles:
            self.sync_engine.process_received_article(article_data, requested_ids=rids)

    def _resource_concluded(self, resource):
        if resource.status == RNS.Resource.COMPLETE:
            data = resource.data.read()
            with self._lock:
                rids = set(self._requested_ids)
            self.sync_engine.process_received_article(data, requested_ids=rids)

    def _on_sync_complete(self):
        with self._lock:
            self._remote_complete = True
            both_done = self._local_complete and self._remote_complete
        if both_done:
            self._finish()

    def _mark_local_complete(self):
        with self._lock:
            self._mark_local_complete_unlocked()

    def _mark_local_complete_unlocked(self):
        self._local_complete = True
        channel = self.link.get_channel()
        channel.send(SyncCompleteMessage())
        both_done = self._local_complete and self._remote_complete
        if both_done:
            threading.Thread(target=self._finish, daemon=True).start()

    def _finish(self):
        if self.on_complete:
            self.on_complete(self)
        if self.is_initiator:
            try:
                self.link.teardown()
            except Exception:
                pass
