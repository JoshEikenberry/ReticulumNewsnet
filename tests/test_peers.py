# tests/test_peers.py
import pytest
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
