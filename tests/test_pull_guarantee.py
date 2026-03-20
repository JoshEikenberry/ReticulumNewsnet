"""Assert no article is stored unless the local node requested it."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from newsnet.sync import (
    ArticleDataMessage,
    ArticleRequestMessage,
    SyncEngine,
    SyncSession,
)


def _make_mock_link():
    """Build a minimal MagicMock that satisfies SyncSession.__init__."""
    channel = MagicMock()
    link = MagicMock()
    link.get_channel.return_value = channel
    return link, channel


def _make_sync_engine(store=None):
    engine = MagicMock(spec=SyncEngine)
    engine.store = store or MagicMock()
    engine.get_local_article_ids.return_value = []
    return engine


@patch("newsnet.sync.RNS")
def test_article_data_not_stored_without_request(MockRNS):
    """ArticleDataMessage received before any ArticleRequestMessage → no store write."""
    link, channel = _make_mock_link()
    engine = _make_sync_engine()

    session = SyncSession(link=link, sync_engine=engine, is_initiator=False)

    msg = ArticleDataMessage(articles=[b"fake-article-data"])
    session._on_article_data(msg)

    engine.process_received_article.assert_not_called()


@patch("newsnet.sync.RNS")
def test_article_data_stored_after_request(MockRNS):
    """ArticleDataMessage with IDs that were previously requested → store write attempted."""
    link, channel = _make_mock_link()
    engine = _make_sync_engine()
    engine.process_received_article.return_value = True

    session = SyncSession(link=link, sync_engine=engine, is_initiator=False)
    session._requested_ids.add("known-id-abc")

    # Simulate receiving an article. process_received_article must be called.
    # We pass a dummy bytes; the engine mock will accept it.
    msg = ArticleDataMessage(articles=[b"data-for-known-id"])
    # We need the article to deserialize to message_id="known-id-abc"
    # Patch Article.deserialize to return a mock article with that ID
    mock_article = MagicMock()
    mock_article.message_id = "known-id-abc"

    with patch("newsnet.sync.Article") as MockArticle:
        MockArticle.deserialize.return_value = mock_article
        session._on_article_data(msg)

    engine.process_received_article.assert_called_once_with(
        b"data-for-known-id", requested_ids={"known-id-abc"}
    )


@patch("newsnet.sync.RNS")
def test_requested_ids_populated_on_id_list(MockRNS):
    """When local node sends ArticleRequestMessage, IDs are added to _requested_ids."""
    link, channel = _make_mock_link()
    engine = _make_sync_engine()
    engine.compute_missing_ids.return_value = ["id-1", "id-2"]

    session = SyncSession(link=link, sync_engine=engine, is_initiator=True)

    # Simulate receiving peer's final ID list
    from newsnet.sync import ArticleIDListMessage
    msg = ArticleIDListMessage([("remote-id-x", 1.0)], is_final=True)

    with patch.object(engine, "get_local_article_ids", return_value=[]):
        with patch.object(engine, "compute_missing_ids", return_value=["id-1", "id-2"]):
            session._on_id_list(msg)

    assert "id-1" in session._requested_ids
    assert "id-2" in session._requested_ids
