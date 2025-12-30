# -*- mode: python ; coding: utf-8 -*-
"""
Zbot_Server PyInstaller Spec File
Pure FastAPI backend server (no systray) - runs as independent process
"""
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Paths (Relative to this spec file, which is in backend/)
project_root = os.path.dirname(os.path.abspath(SPEC))
# Root of the repository (one level up)
repo_root = os.path.dirname(project_root)

# Correct paths relative to repo root
frontend_dist = os.path.join(repo_root, 'frontend', 'dist')
launcher_assets = os.path.join(repo_root, 'zbot_launcher', 'assets')

# Hidden imports for FastAPI/Uvicorn (NO systray here)
hidden_imports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'starlette',
    'pydantic',
    'httpx',
    'httpcore',
    'anyio',
    'anyio._backends',
    'anyio._backends._asyncio',
    'sniffio',
    'h11',
    'email_validator',
    # Supabase
    'supabase',
    'postgrest',
    'gotrue',
    'realtime',
    'storage3',
    # Google Sheets / Utility
    'gspread',
    'google.auth',
    'google.oauth2',
    'pandas',
    'pygsheets',
    'aiosmtplib',
    'bs4',
    'lxml',
]

# Collect backend app module
hidden_imports += collect_submodules('app')
hidden_imports += collect_submodules('vghsdk')

# Data files
datas = [
    # Frontend dist
    (frontend_dist, 'frontend/dist'),
    # Assets (Icon) - from launcher assets
    (launcher_assets, 'assets'),
]

# Explicitly bundle local packages
datas += collect_data_files('app', include_py_files=False)
datas += collect_data_files('vghsdk', include_py_files=False)

a = Analysis(
    [os.path.join(project_root, 'run_server.py')],  # New entry point
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest', '_pytest',
        'tkinter', 'tk', '_tkinter',
        'matplotlib', 'PIL.ImageTk',
        'numpy.testing', 'numpy.f2py', 'numpy.distutils',
        'pandas.tests',
        'scipy',
        'IPython', 'jupyter', 'notebook',
        # Exclude systray (not needed for server)
        'infi.systray',
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
    [],
    exclude_binaries=True,
    name='Zbot_Server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(launcher_assets, 'icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name='Zbot_Server',
)
