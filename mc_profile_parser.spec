# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for mc_profile_parser GUI (Windows one-file build)."""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

a = Analysis(
    ['mc_profile_parser/__main__.py'],
    pathex=['.'],
    binaries=[],
    datas=collect_data_files('PyQt6', include_py_files=False),
    hiddenimports=[
        'PyQt6.sip',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'mc_profile_parser.gui',
        'mc_profile_parser.parser',
        'mc_profile_parser.env_template',
        'mc_profile_parser.visa_env_template',
        'mc_profile_parser.cli',
        'xml.etree.ElementTree',
        'zipfile',
        'csv',
        'json',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'numpy', 'IPython'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='mc_profile_parser',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no console window on Windows
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # set to 'icon.ico' if you add one
)
