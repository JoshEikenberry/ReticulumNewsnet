import umsgpack
from newsnet.sync import (
    ArticleIDListMessage,
    ArticleRequestMessage,
    ArticleDataMessage,
    SyncCompleteMessage,
)


def test_article_id_list_roundtrip():
    ids = [("abc123", 1700000000.0), ("def456", 1700000001.0)]
    msg = ArticleIDListMessage(ids, is_final=True)
    packed = msg.pack()
    restored = ArticleIDListMessage()
    restored.unpack(packed)
    assert restored.article_ids == ids
    assert restored.is_final is True


def test_article_id_list_chunked():
    ids = [("abc123", 1700000000.0)]
    msg = ArticleIDListMessage(ids, is_final=False)
    packed = msg.pack()
    restored = ArticleIDListMessage()
    restored.unpack(packed)
    assert restored.article_ids == ids
    assert restored.is_final is False


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
    msg = ArticleIDListMessage([], is_final=True)
    packed = msg.pack()
    restored = ArticleIDListMessage()
    restored.unpack(packed)
    assert restored.article_ids == []
    assert restored.is_final is True


def test_empty_request():
    msg = ArticleRequestMessage([])
    packed = msg.pack()
    restored = ArticleRequestMessage()
    restored.unpack(packed)
    assert restored.requested_ids == []


def test_sync_complete_roundtrip():
    msg = SyncCompleteMessage()
    packed = msg.pack()
    assert packed == b""
    restored = SyncCompleteMessage()
    restored.unpack(packed)
    # No data to check, just ensure it doesn't error


def test_message_types_are_unique():
    types = [
        ArticleIDListMessage.MSGTYPE,
        ArticleRequestMessage.MSGTYPE,
        ArticleDataMessage.MSGTYPE,
        SyncCompleteMessage.MSGTYPE,
    ]
    assert len(types) == len(set(types))
