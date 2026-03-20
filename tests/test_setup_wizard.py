"""Tests for first-run setup wizard."""
from __future__ import annotations
from io import StringIO
from unittest.mock import MagicMock, patch
import pytest

from newsnet.config import NewsnetConfig
from newsnet.wizard import is_first_run, run_wizard


def test_is_first_run_when_token_empty():
    cfg = NewsnetConfig(api_token="")
    assert is_first_run(cfg) is True


def test_is_first_run_false_when_token_set():
    cfg = NewsnetConfig(api_token="some-token")
    assert is_first_run(cfg) is False


def test_wizard_sets_display_name(tmp_path):
    cfg = NewsnetConfig(config_dir_override=str(tmp_path))
    cfg.ensure_dirs()
    responses = iter(["alice", "", ""])
    with patch("builtins.input", lambda _: next(responses)):
        run_wizard(cfg, add_peer_fn=None)
    assert cfg.display_name == "alice"
    assert cfg.api_token != ""  # token was generated


def test_wizard_uses_default_name_on_empty_input(tmp_path):
    cfg = NewsnetConfig(config_dir_override=str(tmp_path))
    cfg.ensure_dirs()
    responses = iter(["", "", ""])
    with patch("builtins.input", lambda _: next(responses)):
        run_wizard(cfg, add_peer_fn=None)
    assert cfg.display_name == "anonymous"


def test_wizard_calls_add_peer_when_provided(tmp_path):
    cfg = NewsnetConfig(config_dir_override=str(tmp_path))
    cfg.ensure_dirs()
    add_peer = MagicMock()
    responses = iter(["alice", "", "192.168.1.50:4965"])
    with patch("builtins.input", lambda _: next(responses)):
        run_wizard(cfg, add_peer_fn=add_peer)
    add_peer.assert_called_once_with("192.168.1.50:4965")


def test_wizard_skips_peer_on_empty(tmp_path):
    cfg = NewsnetConfig(config_dir_override=str(tmp_path))
    cfg.ensure_dirs()
    add_peer = MagicMock()
    responses = iter(["", "", ""])
    with patch("builtins.input", lambda _: next(responses)):
        run_wizard(cfg, add_peer_fn=add_peer)
    add_peer.assert_not_called()
