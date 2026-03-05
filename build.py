#!/usr/bin/env python3
"""Build standalone newsnet executable using PyInstaller.

RNS uses dynamic module discovery (glob.glob on .py files) that breaks in
frozen PyInstaller builds. This script patches the installed RNS source
before building, then restores it afterward.
"""

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


def _find_rns_dir() -> Path | None:
    """Find the installed RNS package directory without importing it."""
    result = subprocess.run(
        [sys.executable, "-c", "import RNS, os; print(os.path.dirname(RNS.__file__))"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        p = Path(result.stdout.strip())
        if p.is_dir():
            return p

    # Fallback: search site-packages
    for path in sys.path:
        candidate = Path(path) / "RNS"
        if (candidate / "Reticulum.py").exists():
            return candidate
    return None


def _patch_file(path: Path, old: str, new: str) -> Path | None:
    """Replace `old` with `new` in a file, backing up the original."""
    content = path.read_text(encoding="utf-8")
    if old not in content:
        print(f"  WARNING: patch target not found in {path.name}, skipping")
        return None
    backup = path.with_suffix(path.suffix + ".bak")
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(content.replace(old, new, 1), encoding="utf-8")
    print(f"  Patched {path}")
    return backup


def _clear_pycache(directory: Path):
    """Remove __pycache__ dirs so Python doesn't use stale bytecode."""
    for cache_dir in directory.rglob("__pycache__"):
        shutil.rmtree(cache_dir)
        print(f"  Cleared {cache_dir}")


def _restore(backup: Path):
    """Restore a backed-up file."""
    target = backup.with_name(backup.name.removesuffix(".bak"))
    shutil.copy2(backup, target)
    backup.unlink()
    print(f"  Restored {target}")


def main():
    backups: list[Path] = []

    rns_dir = _find_rns_dir()
    if rns_dir is None:
        print("ERROR: Could not find installed RNS package")
        sys.exit(1)

    print(f"Found RNS at: {rns_dir}")

    # Patch RNS/Reticulum.py
    print("Patching RNS for frozen build...")
    ret_path = rns_dir / "Reticulum.py"
    if ret_path.exists():
        b = _patch_file(ret_path, RETICULUM_OLD, RETICULUM_NEW)
        if b:
            backups.append(b)
    else:
        print(f"  ERROR: {ret_path} not found")
        sys.exit(1)

    # Clear bytecode caches so PyInstaller sees the patched source
    _clear_pycache(rns_dir)

    # Verify the patch was applied
    content = ret_path.read_text(encoding="utf-8")
    if "from RNS.Interfaces import Interface" in content:
        print("  Verified: patch is present in source file")
    else:
        print("  ERROR: patch verification failed!")
        sys.exit(1)

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
