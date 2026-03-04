from unittest.mock import MagicMock, patch, call
import threading

from newsnet.sync import (
    SyncSession,
    SyncEngine,
    ArticleIDListMessage,
    ArticleRequestMessage,
    SyncCompleteMessage,
    ID_CHUNK_SIZE,
)


def make_mock_link():
    link = MagicMock()
    channel = MagicMock()
    link.get_channel.return_value = channel
    return link, channel


def make_mock_sync_engine(local_ids=None, missing_ids=None):
    engine = MagicMock(spec=SyncEngine)
    engine.get_local_article_ids.return_value = local_ids or []
    engine.compute_missing_ids.return_value = missing_ids or []
    engine.store = MagicMock()
    return engine


@patch("newsnet.sync.RNS")
def test_start_sends_id_list(MockRNS):
    link, channel = make_mock_link()
    engine = make_mock_sync_engine(local_ids=[("id1", 1.0), ("id2", 2.0)])

    session = SyncSession(link, engine, is_initiator=True)
    session.start()

    assert channel.send.call_count == 1
    sent_msg = channel.send.call_args[0][0]
    assert isinstance(sent_msg, ArticleIDListMessage)
    assert sent_msg.article_ids == [("id1", 1.0), ("id2", 2.0)]
    assert sent_msg.is_final is True


@patch("newsnet.sync.RNS")
def test_start_chunks_large_id_list(MockRNS):
    link, channel = make_mock_link()
    ids = [(f"id{i}", float(i)) for i in range(ID_CHUNK_SIZE + 5)]
    engine = make_mock_sync_engine(local_ids=ids)

    session = SyncSession(link, engine, is_initiator=True)
    session.start()

    assert channel.send.call_count == 2
    first_msg = channel.send.call_args_list[0][0][0]
    assert len(first_msg.article_ids) == ID_CHUNK_SIZE
    assert first_msg.is_final is False

    second_msg = channel.send.call_args_list[1][0][0]
    assert len(second_msg.article_ids) == 5
    assert second_msg.is_final is True


@patch("newsnet.sync.RNS")
def test_start_empty_ids(MockRNS):
    link, channel = make_mock_link()
    engine = make_mock_sync_engine(local_ids=[])

    session = SyncSession(link, engine, is_initiator=True)
    session.start()

    assert channel.send.call_count == 1
    sent_msg = channel.send.call_args[0][0]
    assert isinstance(sent_msg, ArticleIDListMessage)
    assert sent_msg.article_ids == []
    assert sent_msg.is_final is True


@patch("newsnet.sync.RNS")
def test_receiving_ids_triggers_request(MockRNS):
    link, channel = make_mock_link()
    engine = make_mock_sync_engine(
        local_ids=[("local1", 1.0)],
        missing_ids=["remote1", "remote2"],
    )

    session = SyncSession(link, engine, is_initiator=False)

    # Simulate receiving an ID list message
    msg = ArticleIDListMessage([("remote1", 1.0), ("remote2", 2.0)], is_final=True)
    session._on_message(msg)

    # Should have sent an ArticleRequestMessage
    calls = channel.send.call_args_list
    req_calls = [c for c in calls if isinstance(c[0][0], ArticleRequestMessage)]
    assert len(req_calls) == 1
    assert req_calls[0][0][0].requested_ids == ["remote1", "remote2"]


@patch("newsnet.sync.RNS")
def test_receiving_ids_no_missing_sends_complete(MockRNS):
    link, channel = make_mock_link()
    engine = make_mock_sync_engine(
        local_ids=[("id1", 1.0)],
        missing_ids=[],
    )

    session = SyncSession(link, engine, is_initiator=False)

    msg = ArticleIDListMessage([("id1", 1.0)], is_final=True)
    session._on_message(msg)

    # Should send SyncCompleteMessage (no request needed)
    complete_calls = [c for c in channel.send.call_args_list
                      if isinstance(c[0][0], SyncCompleteMessage)]
    assert len(complete_calls) == 1


@patch("newsnet.sync.RNS")
def test_receiving_request_sends_articles(MockRNS):
    link, channel = make_mock_link()
    engine = make_mock_sync_engine()
    engine.store.get_article.return_value = {
        "message_id": "id1",
        "author_hash": "ah",
        "author_key": b"key",
        "display_name": "Alice",
        "newsgroup": "test",
        "subject": "Hi",
        "body": "Hello",
        "references": "[]",
        "timestamp": 1.0,
        "signature": b"sig",
    }

    session = SyncSession(link, engine, is_initiator=True)

    msg = ArticleRequestMessage(["id1"])
    session._on_message(msg)

    MockRNS.Resource.assert_called_once()


@patch("newsnet.sync.RNS")
def test_completion_callback_fires(MockRNS):
    link, channel = make_mock_link()
    engine = make_mock_sync_engine(local_ids=[], missing_ids=[])
    completed = threading.Event()

    def on_complete(session):
        completed.set()

    session = SyncSession(link, engine, is_initiator=False, on_complete=on_complete)

    # Receive empty ID list -> marks local complete (nothing to request)
    id_msg = ArticleIDListMessage([], is_final=True)
    session._on_message(id_msg)

    # Receive sync complete from remote
    complete_msg = SyncCompleteMessage()
    session._on_message(complete_msg)

    assert completed.wait(timeout=2)
