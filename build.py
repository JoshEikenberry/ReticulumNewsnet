#!/usr/bin/env python3
"""Build standalone newsnet executable using PyInstaller.

RNS uses dynamic module discovery (glob.glob on .py files) that breaks in
frozen PyInstaller builds. This script patches the installed RNS source
before building, then restores it afterward.
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# Patches for RNS source files
# --------------------------------------------------------------------------- #

# RNS/Reticulum.py — replace the wildcard import with explicit imports
# (mirrors what RNS already does for the Android branch)
RETICULUM_OLD = "    from RNS.Interfaces import *"
RETICULUM_NEW = """\
    from RNS.Interfaces import Interface
    from RNS.Interfaces import LocalInterface
    from RNS.Interfaces import AutoInterface
    from RNS.Interfaces import BackboneInterface
    from RNS.Interfaces import TCPInterface
    from RNS.Interfaces import UDPInterface
    from RNS.Interfaces import I2PInterface
    from RNS.Interfaces import SerialInterface
    from RNS.Interfaces import PipeInterface
    from RNS.Interfaces import KISSInterface
    from RNS.Interfaces import AX25KISSInterface
    from RNS.Interfaces import RNodeInterface
    from RNS.Interfaces import RNodeMultiInterface
    from RNS.Interfaces import WeaveInterface"""


def _find_rns_file(module_path: str) -> Path | None:
    """Locate an installed RNS source file."""
    spec = importlib.util.find_spec(module_path)
    if spec and spec.origin:
        p = Path(spec.origin)
        if p.exists():
            return p
    return None


def _patch_file(path: Path, old: str, new: str) -> Path | None:
    """Replace `old` with `new` in a file, backing up the original."""
    content = path.read_text()
    if old not in content:
        print(f"  WARNING: patch target not found in {path.name}, skipping")
        return None
    backup = path.with_suffix(path.suffix + ".bak")
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(content.replace(old, new, 1))
    print(f"  Patched {path}")
    return backup


def _restore(backup: Path):
    """Restore a backed-up file."""
    target = backup.with_name(backup.name.removesuffix(".bak"))
    shutil.copy2(backup, target)
    backup.unlink()
    print(f"  Restored {target}")


def main():
    backups: list[Path] = []

    # Patch RNS/Reticulum.py
    print("Patching RNS for frozen build...")
    ret_path = _find_rns_file("RNS.Reticulum")
    if ret_path:
        b = _patch_file(ret_path, RETICULUM_OLD, RETICULUM_NEW)
        if b:
            backups.append(b)
    else:
        print("  WARNING: Could not find RNS/Reticulum.py")

    try:
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--clean",
            "newsnet.spec",
        ]
        print(f"\nRunning: {' '.join(cmd)}")
        result = subprocess.run(cmd)
    finally:
        print("\nRestoring patched files...")
        for backup in backups:
            _restore(backup)

    if result.returncode == 0:
        print("\nBuild complete! Executable is in dist/newsnet")
    else:
        print("\nBuild failed.", file=sys.stderr)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
