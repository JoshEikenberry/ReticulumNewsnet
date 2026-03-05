# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for building the newsnet executable."""

import os
import sys

block_cipher = None

a = Analysis(
    ['cli/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('tui/app.tcss', 'tui'),
    ],
    hiddenimports=[
        'newsnet',
        'newsnet.config',
        'newsnet.node',
        'newsnet.store',
        'newsnet.filters',
        'newsnet.article',
        'newsnet.identity',
        'newsnet.sync',
        'cli',
        'tui',
        'tui.app',
        'RNS',
        'umsgpack',
        'textual',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='newsnet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
)
