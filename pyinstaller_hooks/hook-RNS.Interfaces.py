"""PyInstaller hook for RNS.Interfaces.

RNS.Interfaces.__init__ uses glob.glob() to dynamically build __all__,
which fails in a frozen PyInstaller bundle. This hook ensures all
interface modules are collected as hidden imports.
"""

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('RNS.Interfaces')
