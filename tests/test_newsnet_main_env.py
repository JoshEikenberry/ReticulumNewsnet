# tests/test_newsnet_main_env.py
import os
import importlib
from unittest.mock import patch, MagicMock
import tempfile
import pathlib


def test_config_dir_override_from_env(tmp_path):
    """NEWSNET_CONFIG_DIR sets config_dir_override on the loaded config."""
    (tmp_path / "config.toml").write_text(
        'display_name = "tester"\napi_token = "tok"\napi_port = 9000\n'
        'retention_hours = 168\nsync_interval_minutes = 15\nstrict_filtering = false\n'
        'api_host = "127.0.0.1"\n',
        encoding="utf-8",
    )
    with patch.dict(os.environ, {"NEWSNET_CONFIG_DIR": str(tmp_path)}):
        import newsnet_main
        importlib.reload(newsnet_main)
        cfg = newsnet_main._load_config()
    assert str(cfg.config_dir) == str(tmp_path)
    assert cfg.display_name == "tester"


def test_no_browser_env_suppresses_timer():
    """NEWSNET_NO_BROWSER=1 means _open_browser_if_allowed skips the timer."""
    import newsnet_main
    importlib.reload(newsnet_main)

    with patch("threading.Timer") as mock_timer:
        with patch.dict(os.environ, {"NEWSNET_NO_BROWSER": "1"}):
            newsnet_main._open_browser_if_allowed("http://127.0.0.1:9999/")

    mock_timer.assert_not_called()


def test_no_browser_unset_creates_timer():
    """Without NEWSNET_NO_BROWSER, _open_browser_if_allowed creates a timer."""
    import newsnet_main
    importlib.reload(newsnet_main)

    env = {k: v for k, v in os.environ.items() if k != "NEWSNET_NO_BROWSER"}
    with patch.dict(os.environ, env, clear=True):
        with patch("threading.Timer") as mock_timer:
            mock_timer.return_value = MagicMock()
            newsnet_main._open_browser_if_allowed("http://127.0.0.1:9999/")

    mock_timer.assert_called_once()
