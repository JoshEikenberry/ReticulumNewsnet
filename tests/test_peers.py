# tests/test_peers.py
import pytest
from unittest.mock import patch, MagicMock
from newsnet.peers import PeerManager


@pytest.fixture
def pm(tmp_path):
    return PeerManager(tmp_path)


def test_list_empty(pm):
    """No peers.txt file returns empty list."""
    assert pm.list_peers() == []


def test_add_and_list(pm):
    pm.add("hub.example.com:4242")
    assert pm.list_peers() == ["hub.example.com:4242"]


def test_add_default_port(pm):
    pm.add("hub.example.com")
    assert pm.list_peers() == ["hub.example.com:4965"]


def test_add_ipv6(pm):
    pm.add("[2001:db8::1]:4242")
    assert pm.list_peers() == ["[2001:db8::1]:4242"]


def test_add_ipv6_default_port(pm):
    pm.add("[2001:db8::1]")
    assert pm.list_peers() == ["[2001:db8::1]:4965"]


def test_add_duplicate_ignored(pm):
    pm.add("hub.example.com:4242")
    pm.add("hub.example.com:4242")
    assert pm.list_peers() == ["hub.example.com:4242"]


def test_remove(pm):
    pm.add("hub.example.com:4242")
    pm.add("other.host:1234")
    pm.remove("hub.example.com:4242")
    assert pm.list_peers() == ["other.host:1234"]


def test_remove_nonexistent(pm):
    pm.remove("nope:1234")  # should not raise


def test_comments_and_blanks_preserved(tmp_path):
    peers_file = tmp_path / "peers.txt"
    peers_file.write_text("# My hubs\nhub.example.com:4242\n\n# Another\nother:1234\n")
    pm = PeerManager(tmp_path)
    assert pm.list_peers() == ["hub.example.com:4242", "other:1234"]


def test_parse_address_valid():
    assert PeerManager.parse_address("host:1234") == ("host", 1234)
    assert PeerManager.parse_address("host") == ("host", 4965)
    assert PeerManager.parse_address("[::1]:4242") == ("::1", 4242)
    assert PeerManager.parse_address("[::1]") == ("::1", 4965)


def test_parse_address_invalid():
    with pytest.raises(ValueError):
        PeerManager.parse_address("")
    with pytest.raises(ValueError):
        PeerManager.parse_address("host:notaport")
    with pytest.raises(ValueError):
        PeerManager.parse_address("host:99999")


@patch("newsnet.peers.TCPClientInterface", create=True)
def test_connect_creates_interface(MockTCP, tmp_path):
    pm = PeerManager(tmp_path)
    pm.connect("hub.example.com:4242")
    MockTCP.assert_called_once()
    assert "hub.example.com:4242" in pm.connections()


@patch("newsnet.peers.TCPClientInterface", create=True)
def test_disconnect_tears_down(MockTCP, tmp_path):
    mock_iface = MagicMock()
    MockTCP.return_value = mock_iface
    pm = PeerManager(tmp_path)
    pm.connect("hub.example.com:4242")
    pm.disconnect("hub.example.com:4242")
    mock_iface.detach.assert_called_once()
    assert "hub.example.com:4242" not in pm.connections()


@patch("newsnet.peers.TCPClientInterface", create=True)
def test_connect_failure_logs_warning(MockTCP, tmp_path, caplog):
    MockTCP.side_effect = Exception("Connection refused")
    pm = PeerManager(tmp_path)
    pm.connect("bad.host:1234")  # should not raise
    assert "bad.host:1234" not in pm.connections()


@patch("newsnet.peers.TCPClientInterface", create=True)
def test_connect_all_on_startup(MockTCP, tmp_path):
    peers_file = tmp_path / "peers.txt"
    peers_file.write_text("hub1.com:4242\nhub2.com:4242\n")
    pm = PeerManager(tmp_path)
    pm.connect_all()
    assert MockTCP.call_count == 2


@patch("newsnet.peers.TCPClientInterface", create=True)
def test_disconnect_all(MockTCP, tmp_path):
    mock_iface = MagicMock()
    MockTCP.return_value = mock_iface
    pm = PeerManager(tmp_path)
    pm.connect("hub.example.com:4242")
    pm.disconnect_all()
    mock_iface.detach.assert_called_once()
    assert len(pm.connections()) == 0
