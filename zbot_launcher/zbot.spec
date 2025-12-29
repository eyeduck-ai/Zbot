# -*- mode: python ; coding: utf-8 -*-
"""
Zbot Launcher + Systray PyInstaller Spec File
Creates a single executable that:
1. Downloads and updates Zbot_Server
2. Manages Zbot_Server lifecycle
3. Displays system tray icon with menu
"""
import os

block_cipher = None

# Paths
launcher_dir = os.path.dirname(os.path.abspath(SPEC))
launcher_assets = os.path.join(launcher_dir, 'assets')

# Bundle icon for systray use (from launcher's own assets)
datas = [
    (launcher_assets, 'assets'),
]

a = Analysis(
    ['main.py'],
    pathex=[launcher_dir],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'httpx',
        'httpcore',
        'h11',
        'anyio',
        'packaging',
        'packaging.version',
        'packaging.specifiers',
        # Systray module
        'infi.systray',
        'infi.systray.traybar',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'tk', '_tkinter',
        'unittest', 'pytest',
    ],
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
    name='Zbot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep console for launcher status messages during update
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(launcher_assets, 'icon.ico') if os.path.exists(os.path.join(launcher_assets, 'icon.ico')) else None,
)
