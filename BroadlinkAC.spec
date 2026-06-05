# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['ac_controller.py'],
    pathex=[],
    binaries=[],
    datas=[('protocols', 'protocols'), ('logos', 'logos'), ('使用文档.md', '.')],
    hiddenimports=[
        'protocols.haier', 'protocols.aux_ac', 'protocols.panasonic',
        'hvac_ir.gree', 'hvac_ir.midea', 'hvac_ir.hisense',
        'hvac_ir.daikin', 'hvac_ir.mitsubishi',
        'pystray', 'PIL',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='BroadlinkAC',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='broadlink.ico',
)
