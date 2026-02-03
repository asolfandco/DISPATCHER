# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=[('templates', 'templates')],
    hiddenimports=['pandas', 'openpyxl', 'pandas._libs', 'pandas._libs.tslibs', 'pandas._libs.tslibs.fields', 'pandas._libs.tslibs.np_datetime', 'pandas._libs.tslibs.offsets', 'pandas._libs.tslibs.timedeltas', 'pandas._libs.tslibs.timestamps', 'pandas.io.excel', 'pandas.io.formats.excel', 'openpyxl.workbook', 'openpyxl.worksheet', 'openpyxl.styles'],
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
    name='DISPATCHER',
    icon='icon.ico',
    version='version_info.txt',
    uac_admin=True,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DISPATCHER',
)
