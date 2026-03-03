from unittest.mock import patch, MagicMock
from newsnet.config import NewsnetConfig
from newsnet.node import Node


@patch("newsnet.node.RNS")
@patch("newsnet.node.IdentityManager")
@patch("newsnet.node.Store")
def test_node_init(MockStore, MockIdMgr, MockRNS):
    mock_identity = MagicMock()
    mock_identity.hash = b"\x01" * 16
    MockIdMgr.return_value.get_or_create.return_value = mock_identity
    MockRNS.Destination.return_value = MagicMock()

    config = NewsnetConfig(display_name="TestNode")
    node = Node(config)
    node.start()

    MockRNS.Reticulum.assert_called_once()
    MockIdMgr.return_value.get_or_create.assert_called_once()
    MockRNS.Destination.assert_called_once()


@patch("newsnet.node.RNS")
@patch("newsnet.node.IdentityManager")
@patch("newsnet.node.Store")
def test_node_announce(MockStore, MockIdMgr, MockRNS):
    mock_identity = MagicMock()
    mock_identity.hash = b"\x01" * 16
    MockIdMgr.return_value.get_or_create.return_value = mock_identity
    mock_dest = MagicMock()
    MockRNS.Destination.return_value = mock_dest

    config = NewsnetConfig(display_name="TestNode")
    node = Node(config)
    node.start()
    node.announce()

    mock_dest.announce.assert_called_once()


@patch("newsnet.node.RNS")
@patch("newsnet.node.IdentityManager")
@patch("newsnet.node.Store")
def test_node_post_article(MockStore, MockIdMgr, MockRNS):
    mock_identity = MagicMock()
    mock_identity.hash = b"\x01" * 16
    mock_identity.sign.return_value = b"sig"
    mock_identity.get_public_key.return_value = b"pubkey"
    MockIdMgr.return_value.get_or_create.return_value = mock_identity
    MockIdMgr.return_value.identity = mock_identity

    config = NewsnetConfig(display_name="TestNode")
    node = Node(config)
    node.start()
    article = node.post("test.general", "Hello", "Hello world!", [])

    assert article.newsgroup == "test.general"
    assert article.body == "Hello world!"
    MockStore.return_value.store_article.assert_called_once()
