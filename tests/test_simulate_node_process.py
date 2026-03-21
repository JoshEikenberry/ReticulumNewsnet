# tests/test_simulate_node_process.py
import tomllib
import tempfile
import pathlib
from unittest.mock import patch, MagicMock
from tools.simulate.node_process import NodeProcess, _write_config


def test_write_config_creates_valid_toml(tmp_path):
    _write_config(tmp_path, index=2, port=19002, token="test-tok-xyz")
    config_path = tmp_path / "config.toml"
    assert config_path.exists()
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    assert data["api_port"] == 19002
    assert data["api_token"] == "test-tok-xyz"
    assert data["display_name"] == "sim-node-2"
    assert data["strict_filtering"] == False
    assert data["api_host"] == "127.0.0.1"


def test_write_config_sets_sync_interval_to_one(tmp_path):
    _write_config(tmp_path, index=0, port=19000, token="tok")
    with open(tmp_path / "config.toml", "rb") as f:
        data = tomllib.load(f)
    assert data["sync_interval_minutes"] == 1


def test_node_process_url():
    node = NodeProcess.__new__(NodeProcess)
    node.port = 19003
    node.token = "abc"
    node.index = 3
    node._proc = None
    node._temp_dir = None
    assert node._url("/api/articles") == "http://127.0.0.1:19003/api/articles"


def test_node_process_post_article_calls_correct_endpoint():
    node = NodeProcess.__new__(NodeProcess)
    node.port = 19000
    node.token = "tok"
    node.index = 0
    node._proc = None
    node._temp_dir = None

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"message_id": "mid-abc"}

    with patch("httpx.post", return_value=mock_response) as mock_post:
        result = node.post_article("sim.group-0", "hello world", "body text")

    mock_post.assert_called_once_with(
        "http://127.0.0.1:19000/api/articles",
        json={"newsgroup": "sim.group-0", "subject": "hello world",
              "body": "body text", "references": []},
        headers={"Authorization": "Bearer tok"},
        timeout=10,
    )
    assert result == "mid-abc"


def test_node_process_list_article_ids():
    node = NodeProcess.__new__(NodeProcess)
    node.port = 19000
    node.token = "tok"
    node.index = 0
    node._proc = None
    node._temp_dir = None

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = [
        {"message_id": "mid-1"}, {"message_id": "mid-2"}
    ]

    with patch("httpx.get", return_value=mock_response):
        ids = node.list_article_ids()

    assert ids == {"mid-1", "mid-2"}


def test_node_process_add_tcp_peer():
    node = NodeProcess.__new__(NodeProcess)
    node.port = 19000
    node.token = "tok"
    node.index = 0
    node._proc = None
    node._temp_dir = None

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"address": "127.0.0.1:19001"}

    with patch("httpx.post", return_value=mock_response) as mock_post:
        node.add_tcp_peer("127.0.0.1", 19001)

    mock_post.assert_called_once_with(
        "http://127.0.0.1:19000/api/peers",
        json={"address": "127.0.0.1:19001"},
        headers={"Authorization": "Bearer tok"},
        timeout=10,
    )
