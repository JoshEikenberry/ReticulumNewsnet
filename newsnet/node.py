from __future__ import annotations

import logging
import threading
import time

import RNS

from newsnet.article import Article
from newsnet.config import NewsnetConfig
from newsnet.filters import FilterEngine
from newsnet.identity import IdentityManager
from newsnet.store import Store
from newsnet.sync import SyncEngine, SyncSession

log = logging.getLogger(__name__)


class AnnounceHandler:
    def __init__(self, aspect_filter: str, callback):
        self.aspect_filter = aspect_filter
        self._callback = callback

    def received_announce(self, destination_hash, announced_identity, app_data):
        self._callback(destination_hash, announced_identity, app_data)


class Node:
    def __init__(self, config: NewsnetConfig):
        self.config = config
        config.ensure_dirs()
        self._reticulum = None
        self._identity_mgr = IdentityManager(str(config.identity_path))
        self._store = Store(str(config.db_path))
        self._destination = None
        self._sync_engine = None

        self._sessions_lock = threading.Lock()
        self._sessions: dict = {}  # link -> SyncSession
        self._running = False
        self._sync_thread = None

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
        # Trigger immediate sync with newly discovered peer
        threading.Thread(target=self.sync_with_peer, args=(dest_hex,), daemon=True).start()

    def _on_link_established(self, link):
        """Incoming link from a peer wanting to sync."""
        link.set_link_closed_callback(self._on_link_closed)
        session = SyncSession(
            link=link,
            sync_engine=self._sync_engine,
            is_initiator=False,
            on_complete=self._on_session_complete,
        )
        with self._sessions_lock:
            self._sessions[link] = session
        session.start()

    def _on_link_closed(self, link):
        with self._sessions_lock:
            self._sessions.pop(link, None)

    def _outgoing_link_established(self, link):
        """Callback when our outgoing link to a peer is ready."""
        link.set_link_closed_callback(self._on_link_closed)
        session = SyncSession(
            link=link,
            sync_engine=self._sync_engine,
            is_initiator=True,
            on_complete=self._on_session_complete,
        )
        with self._sessions_lock:
            self._sessions[link] = session
        session.start()

    def _on_session_complete(self, session: SyncSession):
        """Called when a sync session finishes."""
        link = session.link
        with self._sessions_lock:
            self._sessions.pop(link, None)
        # Try to find peer hash from link destination and update last_synced
        try:
            dest_hash = link.destination.hash.hex()
            self._store.update_peer_synced(dest_hash, time.time())
        except Exception:
            pass

    def sync_with_peer(self, dest_hash: str):
        """Initiate sync with a specific peer by destination hash."""
        dest_bytes = bytes.fromhex(dest_hash)

        if not RNS.Transport.has_path(dest_bytes):
            RNS.Transport.request_path(dest_bytes)
            # Wait briefly for path resolution
            timeout = 10
            while not RNS.Transport.has_path(dest_bytes) and timeout > 0:
                time.sleep(0.5)
                timeout -= 0.5
            if not RNS.Transport.has_path(dest_bytes):
                log.warning(f"No path to peer {dest_hash[:16]}")
                return

        identity = RNS.Identity.recall(dest_bytes)
        if identity is None:
            log.warning(f"Cannot recall identity for {dest_hash[:16]}")
            return

        destination = RNS.Destination(
            identity,
            RNS.Destination.OUT,
            RNS.Destination.SINGLE,
            "newsnet",
            "peer",
        )
        link = RNS.Link(destination, established_callback=self._outgoing_link_established)

    def sync_all_peers(self):
        """Sync with all eligible peers."""
        peers = self._store.list_peers()
        synced = 0
        for peer in peers:
            if self._sync_engine.should_sync_peer(peer):
                self.sync_with_peer(peer["destination_hash"])
                synced += 1
        return synced

    def start_sync_loop(self):
        """Start periodic sync in a daemon thread."""
        self._running = True
        self._sync_thread = threading.Thread(target=self._periodic_sync_loop, daemon=True)
        self._sync_thread.start()

    def _periodic_sync_loop(self):
        while self._running:
            try:
                self.sync_all_peers()
            except Exception:
                log.exception("Error in periodic sync")
            # Sleep in small increments so shutdown is responsive
            interval = self._sync_engine.sync_interval_seconds
            elapsed = 0.0
            while elapsed < interval and self._running:
                time.sleep(1.0)
                elapsed += 1.0

    def cleanup(self):
        retention_seconds = self.config.retention_hours * 3600
        self._store.cleanup(retention_seconds)

    def shutdown(self):
        self._running = False
        if self._sync_thread is not None:
            self._sync_thread.join(timeout=5)
        self._store.close()
