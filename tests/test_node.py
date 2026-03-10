from unittest.mock import patch, MagicMock, call
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


@patch("newsnet.node.RNS")
@patch("newsnet.node.IdentityManager")
@patch("newsnet.node.Store")
def test_sync_all_peers_no_peers(MockStore, MockIdMgr, MockRNS):
    mock_identity = MagicMock()
    mock_identity.hash = b"\x01" * 16
    MockIdMgr.return_value.get_or_create.return_value = mock_identity
    MockRNS.Destination.return_value = MagicMock()
    MockStore.return_value.list_peers.return_value = []

    config = NewsnetConfig(display_name="TestNode")
    node = Node(config)
    node.start()
    count = node.sync_all_peers()
    assert count == 0


@patch("newsnet.node.RNS")
@patch("newsnet.node.IdentityManager")
@patch("newsnet.node.Store")
def test_sync_all_peers_calls_sync(MockStore, MockIdMgr, MockRNS):
    mock_identity = MagicMock()
    mock_identity.hash = b"\x01" * 16
    MockIdMgr.return_value.get_or_create.return_value = mock_identity
    MockRNS.Destination.return_value = MagicMock()
    MockRNS.Transport.has_path.return_value = True
    MockRNS.Identity.recall.return_value = MagicMock()

    peer = {
        "destination_hash": "aa" * 16,
        "display_name": "Peer1",
        "last_synced": None,
    }
    MockStore.return_value.list_peers.return_value = [peer]

    config = NewsnetConfig(display_name="TestNode")
    node = Node(config)
    node.start()
    count = node.sync_all_peers()
    assert count == 1
    MockRNS.Link.assert_called_once()


@patch("newsnet.node.threading")
@patch("newsnet.node.RNS")
@patch("newsnet.node.IdentityManager")
@patch("newsnet.node.Store")
def test_on_announce_triggers_sync(MockStore, MockIdMgr, MockRNS, MockThreading):
    mock_identity = MagicMock()
    mock_identity.hash = b"\x01" * 16
    MockIdMgr.return_value.get_or_create.return_value = mock_identity
    MockRNS.Destination.return_value = MagicMock()

    config = NewsnetConfig(display_name="TestNode")
    node = Node(config)
    node.start()

    # Simulate announce
    dest_hash = b"\xaa" * 16
    node._on_announce(dest_hash, MagicMock(), b"PeerName")

    MockStore.return_value.upsert_peer.assert_called_once()
    # Should have spawned a thread to sync
    MockThreading.Thread.assert_called()


@patch("newsnet.node.RNS")
@patch("newsnet.node.IdentityManager")
@patch("newsnet.node.Store")
def test_shutdown_stops_sync_loop(MockStore, MockIdMgr, MockRNS):
    mock_identity = MagicMock()
    mock_identity.hash = b"\x01" * 16
    MockIdMgr.return_value.get_or_create.return_value = mock_identity
    MockRNS.Destination.return_value = MagicMock()

    config = NewsnetConfig(display_name="TestNode")
    node = Node(config)
    node.start()
    node.shutdown()

    assert node._running is False
    MockStore.return_value.close.assert_called_once()


@patch("newsnet.node.PeerManager")
@patch("newsnet.node.RNS")
@patch("newsnet.node.IdentityManager")
@patch("newsnet.node.Store")
def test_node_start_connects_peers(MockStore, MockIdMgr, MockRNS, MockPM):
    mock_identity = MagicMock()
    mock_identity.hash = b"\x01" * 16
    MockIdMgr.return_value.get_or_create.return_value = mock_identity
    MockRNS.Destination.return_value = MagicMock()

    config = NewsnetConfig(display_name="TestNode")
    node = Node(config)
    node.start()

    MockPM.return_value.connect_all.assert_called_once()


@patch("newsnet.node.PeerManager")
@patch("newsnet.node.RNS")
@patch("newsnet.node.IdentityManager")
@patch("newsnet.node.Store")
def test_node_shutdown_disconnects_peers(MockStore, MockIdMgr, MockRNS, MockPM):
    mock_identity = MagicMock()
    mock_identity.hash = b"\x01" * 16
    MockIdMgr.return_value.get_or_create.return_value = mock_identity
    MockRNS.Destination.return_value = MagicMock()

    config = NewsnetConfig(display_name="TestNode")
    node = Node(config)
    node.start()
    node.shutdown()

    MockPM.return_value.disconnect_all.assert_called_once()


@patch("newsnet.node.PeerManager")
@patch("newsnet.node.RNS")
@patch("newsnet.node.IdentityManager")
@patch("newsnet.node.Store")
def test_node_add_peer(MockStore, MockIdMgr, MockRNS, MockPM):
    mock_identity = MagicMock()
    mock_identity.hash = b"\x01" * 16
    MockIdMgr.return_value.get_or_create.return_value = mock_identity
    MockRNS.Destination.return_value = MagicMock()
    MockPM.return_value.add.return_value = "hub.example.com:4242"

    config = NewsnetConfig(display_name="TestNode")
    node = Node(config)
    node.start()
    result = node.add_tcp_peer("hub.example.com:4242")

    assert result == "hub.example.com:4242"
    MockPM.return_value.add.assert_called_once_with("hub.example.com:4242")
    MockPM.return_value.connect.assert_called_once_with("hub.example.com:4242")
