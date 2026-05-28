# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for emv_profiler GUI (Windows one-file build)."""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

a = Analysis(
    ['emv_profiler/__main__.py'],
    pathex=['.'],
    binaries=[],
    datas=collect_data_files('PyQt6', include_py_files=False),
    hiddenimports=[
        'PyQt6.sip',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'emv_profiler.gui',
        'emv_profiler.parser',
        'emv_profiler.env_template',
        'emv_profiler.visa_env_template',
        'emv_profiler.cli',
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
    name='emv_profiler',
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
