# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for 多表格同步服务.

Build:
    pyinstaller sync_service.spec

Output:
    dist/sync_service/sync_service.exe  (Windows)
    dist/sync_service/sync_service      (macOS/Linux)
"""

import sys
from pathlib import Path

block_cipher = None
root = Path(SPECPATH)

a = Analysis(
    [str(root / 'main.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[
        # Bundle .env.example so first-run setup can use it as template
        (str(root / '.env.example'), '.'),
    ],
    hiddenimports=[
        'config',
        'config.settings',
        'config.mappings',
        'connectors',
        'connectors.base',
        'connectors.tencent_docs',
        'connectors.feishu_sheets',
        'models',
        'models.records',
        'models.task_models',
        'models.state_models',
        'services',
        'services.gross_profit_service',
        'services.refund_match_service',
        'services.c_to_a_sync_service',
        'services.scheduler_service',
        'services.state_service',
        'utils',
        'utils.logger',
        'utils.parser',
        'utils.diff',
        'utils.retry',
        'cli',
        'cli.commands',
        'cli.setup',
        # Pydantic v2 needs these
        'pydantic',
        'pydantic_settings',
        'annotated_types',
        'dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='sync_service',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Must be console app for interactive CLI
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='sync_service',
)
