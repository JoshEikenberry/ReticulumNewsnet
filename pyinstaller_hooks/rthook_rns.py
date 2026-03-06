"""Runtime hook: fix RNS.Interfaces discovery in frozen PyInstaller builds.

RNS.Interfaces.__init__ uses glob.glob() to find .py files on disk and build
__all__.  In a frozen bundle there are no .py files, so the glob returns nothing
and `from RNS.Interfaces import *` imports zero names.

This hook patches glob.glob BEFORE the main script runs, so the fix is in place
before any RNS code is imported.
"""

import glob as _glob
import os as _os
import sys

_original_glob = _glob.glob

_INTERFACE_MODULES = [
    "Interface", "LocalInterface", "AutoInterface", "BackboneInterface",
    "TCPInterface", "UDPInterface", "I2PInterface", "SerialInterface",
    "PipeInterface", "KISSInterface", "AX25KISSInterface",
    "RNodeInterface", "RNodeMultiInterface", "WeaveInterface",
]


def _patched_glob(pattern, *args, **kwargs):
    # Only intercept the top-level RNS/Interfaces/ glob, not subdirs
    if pattern.endswith("*.py") and pattern.replace("\\", "/").endswith("Interfaces/*.py"):
        base = pattern[:-4]
        return [_os.path.join(base, f"{m}.py") for m in _INTERFACE_MODULES]
    if pattern.endswith("*.pyc") and pattern.replace("\\", "/").endswith("Interfaces/*.pyc"):
        return []
    return _original_glob(pattern, *args, **kwargs)


_glob.glob = _patched_glob
