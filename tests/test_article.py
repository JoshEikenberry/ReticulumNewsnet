import json
import hashlib
import time
import umsgpack
from unittest.mock import MagicMock
from newsnet.article import Article


def make_mock_identity():
    identity = MagicMock()
    identity.hash = b"\x01" * 16
    identity.get_public_key.return_value = b"mock_public_key_32bytes_padding!!"
    identity.sign.side_effect = lambda data: b"mock_signature_" + data[:16]
    identity.validate.return_value = True
    return identity


def test_create_article():
    identity = make_mock_identity()
    article = Article.create(
        identity=identity,
        display_name="Alice",
        newsgroup="test.general",
        subject="Hello",
        body="Hello, world!",
        references=[],
    )
    assert article.newsgroup == "test.general"
    assert article.subject == "Hello"
    assert article.body == "Hello, world!"
    assert article.display_name == "Alice"
    assert article.author_hash == identity.hash.hex()
    assert article.signature is not None
    assert article.message_id is not None


def test_message_id_is_deterministic():
    identity = make_mock_identity()
    ts = 1700000000.0
    a1 = Article.create(identity, "Alice", "test.group", "Subj", "Body", [], timestamp=ts)
    a2 = Article.create(identity, "Alice", "test.group", "Subj", "Body", [], timestamp=ts)
    assert a1.message_id == a2.message_id


def test_message_id_changes_with_content():
    identity = make_mock_identity()
    ts = 1700000000.0
    a1 = Article.create(identity, "Alice", "test.group", "Subj", "Body A", [], timestamp=ts)
    a2 = Article.create(identity, "Alice", "test.group", "Subj", "Body B", [], timestamp=ts)
    assert a1.message_id != a2.message_id


def test_serialize_deserialize():
    identity = make_mock_identity()
    article = Article.create(identity, "Alice", "test.general", "Hello", "World", [])
    data = article.serialize()
    restored = Article.deserialize(data)
    assert restored.message_id == article.message_id
    assert restored.body == article.body
    assert restored.author_key == article.author_key
    assert restored.signature == article.signature


def test_verify_valid_article():
    identity = make_mock_identity()
    article = Article.create(identity, "Alice", "test.general", "Hello", "World", [])
    assert article.verify(identity) is True


def test_verify_tampered_article():
    identity = make_mock_identity()
    article = Article.create(identity, "Alice", "test.general", "Hello", "World", [])
    article.body = "Tampered!"
    assert article.verify(identity) is False


def test_to_dict():
    identity = make_mock_identity()
    article = Article.create(identity, "Alice", "test.general", "Hello", "World", [])
    d = article.to_store_dict()
    assert d["message_id"] == article.message_id
    assert d["newsgroup"] == "test.general"
    assert d["body"] == "World"
    assert isinstance(d["references"], str)  # JSON string
    assert isinstance(d["received_at"], float)


def test_from_store_dict_roundtrip():
    identity = make_mock_identity()
    article = Article.create(identity, "Alice", "test.general", "Hello", "World", ["ref1", "ref2"])
    store_dict = article.to_store_dict()
    restored = Article.from_store_dict(store_dict)
    assert restored.message_id == article.message_id
    assert restored.author_hash == article.author_hash
    assert restored.author_key == article.author_key
    assert restored.display_name == article.display_name
    assert restored.newsgroup == article.newsgroup
    assert restored.subject == article.subject
    assert restored.body == article.body
    assert restored.references == ["ref1", "ref2"]
    assert restored.timestamp == article.timestamp
    assert restored.signature == article.signature


def test_from_store_dict_empty_references():
    identity = make_mock_identity()
    article = Article.create(identity, "Alice", "test.general", "Hello", "World", [])
    store_dict = article.to_store_dict()
    restored = Article.from_store_dict(store_dict)
    assert restored.references == []


def test_unicode_body():
    identity = make_mock_identity()
    body = "Hei verden! \U0001f30d \u00e6\u00f8\u00e5 \u4e16\u754c \u0417\u0434\u0440\u0430\u0432\u0441\u0442\u0432\u0443\u0439"
    article = Article.create(identity, "Alice", "test.unicode", "Unicode", body, [])
    data = article.serialize()
    restored = Article.deserialize(data)
    assert restored.body == body
