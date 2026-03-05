#!/usr/bin/env python3
"""Build standalone newsnet executable using PyInstaller."""

import importlib.util
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

# RNS.Interfaces.__init__ uses glob.glob() to discover modules on disk.
# In a PyInstaller frozen bundle there are no .py files, so __all__ is empty
# and `from RNS.Interfaces import *` imports nothing. We patch the installed
# copy before building so all interface names are statically listed.

PATCHED_INTERFACES_INIT = textwrap.dedent("""\
    import os
    import glob
    import RNS.Interfaces.Android
    import RNS.Interfaces.util
    import RNS.Interfaces.util.netinfo as netinfo

    # Explicit imports for PyInstaller compatibility.
    # The original code uses glob.glob() to discover .py files and build __all__,
    # then Reticulum.py does `from RNS.Interfaces import *`. In a frozen bundle
    # glob finds nothing, so we explicitly import every interface module here
    # to ensure they exist as attributes on this package.
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
    from RNS.Interfaces import WeaveInterface

    __all__ = [
        "Interface",
        "LocalInterface",
        "AutoInterface",
        "BackboneInterface",
        "TCPInterface",
        "UDPInterface",
        "I2PInterface",
        "SerialInterface",
        "PipeInterface",
        "KISSInterface",
        "AX25KISSInterface",
        "RNodeInterface",
        "RNodeMultiInterface",
        "WeaveInterface",
    ]
""")


def _find_rns_interfaces_init() -> Path | None:
    spec = importlib.util.find_spec("RNS.Interfaces")
    if spec and spec.submodule_search_locations:
        for loc in spec.submodule_search_locations:
            init = Path(loc) / "__init__.py"
            if init.exists():
                return init
    return None


def _patch_rns():
    """Patch RNS.Interfaces.__init__.py with a static fallback for __all__."""
    init_path = _find_rns_interfaces_init()
    if init_path is None:
        print("WARNING: Could not find RNS.Interfaces.__init__.py — skipping patch")
        return None

    backup = init_path.with_suffix(".py.bak")
    if not backup.exists():
        shutil.copy2(init_path, backup)
        print(f"Backed up {init_path} -> {backup.name}")

    init_path.write_text(PATCHED_INTERFACES_INIT)
    print(f"Patched {init_path}")
    return backup


def _restore_rns(backup: Path | None):
    if backup and backup.exists():
        target = backup.with_suffix("")  # remove .bak
        shutil.copy2(backup, target)
        backup.unlink()
        print(f"Restored original {target.name}")


def main():
    backup = _patch_rns()
    try:
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--clean",
            "newsnet.spec",
        ]
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)
    finally:
        _restore_rns(backup)

    if result.returncode == 0:
        print("\nBuild complete! Executable is in dist/newsnet")
    else:
        print("\nBuild failed.", file=sys.stderr)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
