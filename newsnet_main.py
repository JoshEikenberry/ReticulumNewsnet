"""Entry point for frozen (PyInstaller) and direct execution."""
from __future__ import annotations

import sys

_BUILD_VERSION = "0.1.11"

# ---------------------------------------------------------------------------
# Frozen-build fix: RNS.Interfaces.__init__ uses glob.glob() to discover .py
# files on disk. In a PyInstaller bundle there are no .py files, so the glob
# returns nothing and `from RNS.Interfaces import *` silently imports zero
# names — crashing later with NameError.  Monkey-patching glob.glob *before*
# any RNS code is imported makes the discovery work inside frozen builds.
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    print(f"[newsnet v{_BUILD_VERSION} frozen build]", flush=True)

    import glob as _glob
    import os as _os

    _original_glob = _glob.glob
    _INTERFACE_MODULES = [
        "Interface", "LocalInterface", "AutoInterface", "BackboneInterface",
        "TCPInterface", "UDPInterface", "I2PInterface", "SerialInterface",
        "PipeInterface", "KISSInterface", "AX25KISSInterface",
        "RNodeInterface", "RNodeMultiInterface", "WeaveInterface",
    ]

    def _patched_glob(pattern, *args, **kwargs):
        # Only intercept RNS.Interfaces glob, not subdirs like Android/ or util/
        if pattern.endswith("*.py") and pattern.replace("\\", "/").endswith("Interfaces/*.py"):
            base = pattern[:-4]  # strip /*.py
            return [_os.path.join(base, f"{m}.py") for m in _INTERFACE_MODULES]
        if pattern.endswith("*.pyc") and pattern.replace("\\", "/").endswith("Interfaces/*.pyc"):
            return []
        return _original_glob(pattern, *args, **kwargs)

    _glob.glob = _patched_glob

if __name__ == "__main__":
    from cli.main import main
    main()
