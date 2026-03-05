"""PyInstaller hook for RNS.

Collect all RNS submodules since many are loaded dynamically.
"""

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('RNS')
