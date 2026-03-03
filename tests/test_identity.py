import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from newsnet.identity import IdentityManager


def test_create_new_identity(tmp_path):
    identity_path = tmp_path / "identity"
    with patch("newsnet.identity.RNS") as mock_rns:
        mock_identity = MagicMock()
        mock_identity.hash = b"\x01" * 16
        mock_identity.get_public_key.return_value = b"pubkey"
        mock_rns.Identity.return_value = mock_identity
        mock_rns.Identity.from_file.return_value = None

        mgr = IdentityManager(str(identity_path))
        identity = mgr.get_or_create()

        assert identity is mock_identity
        mock_identity.to_file.assert_called_once_with(str(identity_path))


def test_load_existing_identity(tmp_path):
    identity_path = tmp_path / "identity"
    identity_path.touch()
    with patch("newsnet.identity.RNS") as mock_rns:
        mock_identity = MagicMock()
        mock_identity.hash = b"\x02" * 16
        mock_rns.Identity.from_file.return_value = mock_identity

        mgr = IdentityManager(str(identity_path))
        identity = mgr.get_or_create()

        assert identity is mock_identity
        mock_rns.Identity.from_file.assert_called_once_with(str(identity_path))


def test_identity_hash_hex(tmp_path):
    identity_path = tmp_path / "identity"
    with patch("newsnet.identity.RNS") as mock_rns:
        mock_identity = MagicMock()
        mock_identity.hash = bytes.fromhex("abcdef0123456789abcdef0123456789")
        mock_rns.Identity.return_value = mock_identity
        mock_rns.Identity.from_file.return_value = None

        mgr = IdentityManager(str(identity_path))
        mgr.get_or_create()
        assert mgr.hash_hex == "abcdef0123456789abcdef0123456789"
