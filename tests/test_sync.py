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
