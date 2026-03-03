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
