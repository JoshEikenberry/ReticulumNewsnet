import os
import tempfile
from pathlib import Path
from newsnet.config import NewsnetConfig


def test_default_config():
    config = NewsnetConfig()
    assert config.display_name == "anonymous"
    assert config.retention_hours == 168
    assert config.sync_interval_minutes == 15
    assert config.strict_filtering is True


def test_config_from_toml():
    toml_content = """
display_name = "testuser"
retention_hours = 24
sync_interval_minutes = 5
strict_filtering = false
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(toml_content)
        f.flush()
        config = NewsnetConfig.from_file(f.name)

    os.unlink(f.name)
    assert config.display_name == "testuser"
    assert config.retention_hours == 24
    assert config.sync_interval_minutes == 5
    assert config.strict_filtering is False


def test_retention_hours_clamped():
    config = NewsnetConfig(retention_hours=0)
    assert config.retention_hours == 1
    config = NewsnetConfig(retention_hours=9999)
    assert config.retention_hours == 720


def test_config_dir():
    config = NewsnetConfig()
    assert config.config_dir == Path.home() / ".config" / "reticulum-newsnet"
    assert config.db_path == config.config_dir / "newsnet.db"
    assert config.identity_path == config.config_dir / "identity"


def test_config_has_api_fields():
    cfg = NewsnetConfig()
    assert cfg.api_token == ""
    assert cfg.api_host == "127.0.0.1"
    assert cfg.api_port == 8765

def test_config_save_roundtrip(tmp_path):
    cfg = NewsnetConfig(
        display_name="alice",
        api_token="test-token-123",
        api_host="0.0.0.0",
        api_port=9000,
        config_dir_override=str(tmp_path),
    )
    cfg.ensure_dirs()
    cfg.save()
    loaded = NewsnetConfig.from_file(cfg.config_file_path)
    assert loaded.display_name == "alice"
    assert loaded.api_token == "test-token-123"
    assert loaded.api_host == "0.0.0.0"
    assert loaded.api_port == 9000

def test_config_from_file_ignores_unknown_keys(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('display_name = "bob"\nunknown_key = "ignored"\n')
    cfg = NewsnetConfig.from_file(p)
    assert cfg.display_name == "bob"
