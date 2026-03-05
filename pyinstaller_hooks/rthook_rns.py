"""Runtime hook to fix RNS.Interfaces wildcard import in frozen builds.

RNS.Interfaces.__init__ uses glob.glob() to discover .py files on disk
and build __all__ dynamically. In a frozen PyInstaller bundle, there are
no .py files, so __all__ ends up empty and `from RNS.Interfaces import *`
imports nothing — causing NameError for Interface, LocalInterface, etc.

This hook monkey-patches glob.glob to return the expected module names
when called from RNS.Interfaces.__init__.
"""

import glob
import os
import sys

_original_glob = glob.glob

# The interface module basenames that RNS expects to find
_INTERFACE_MODULES = [
    'Interface',
    'LocalInterface',
    'AutoInterface',
    'BackboneInterface',
    'TCPInterface',
    'UDPInterface',
    'I2PInterface',
    'SerialInterface',
    'PipeInterface',
    'KISSInterface',
    'AX25KISSInterface',
    'RNodeInterface',
    'RNodeMultiInterface',
    'WeaveInterface',
]


def _patched_glob(pattern, *args, **kwargs):
    # Detect when RNS.Interfaces.__init__ is globbing for *.py or *.pyc
    if ('RNS' in pattern or 'Interfaces' in pattern) and (pattern.endswith('*.py') or pattern.endswith('*.pyc')):
        if pattern.endswith('*.py'):
            parent = pattern[:-4]  # strip /*.py
            return [os.path.join(parent, f'{m}.py') for m in _INTERFACE_MODULES]
        else:
            return []  # no .pyc needed, .py list is sufficient
    return _original_glob(pattern, *args, **kwargs)


glob.glob = _patched_glob
