# -*- mode: python ; coding: utf-8 -*-
# macOS 打包 → pyinstaller BroadlinkAC-macOS.spec
from PyInstaller.utils.hooks import collect_submodules

a = Analysis(
    ['ac_controller.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('protocols', 'protocols'),
        ('logos', 'logos'),
        ('使用文档.md', '.'),
        # 新增：包含拆分后的模块目录
        ('broadlinkac_desktop/ui', 'broadlinkac_desktop/ui'),
        ('broadlinkac_desktop/dialogs', 'broadlinkac_desktop/dialogs'),
        ('broadlinkac_desktop/utils', 'broadlinkac_desktop/utils'),
        ('broadlinkac_desktop/workers', 'broadlinkac_desktop/workers'),
    ],
    hiddenimports=[
        'protocols.haier', 'protocols.aux_ac', 'protocols.panasonic',
        # 新增：动态导入的模块
        'plistlib', 'winreg',
        # 新增：拆分后的模块
        'broadlinkac_desktop.ui',
        'broadlinkac_desktop.ui.ac_panel',
        'broadlinkac_desktop.ui.weather_panel',
        'broadlinkac_desktop.ui.typhoon_panel',
        'broadlinkac_desktop.ui.device_panel',
        'broadlinkac_desktop.dialogs',
        'broadlinkac_desktop.dialogs.diagnosis_dialog',
        'broadlinkac_desktop.dialogs.log_dialog',
        'broadlinkac_desktop.dialogs.rules_dialog',
        'broadlinkac_desktop.dialogs.typhoon_alert',
        'broadlinkac_desktop.utils',
        'broadlinkac_desktop.utils.autostart',
        'broadlinkac_desktop.utils.tray',
        'broadlinkac_desktop.utils.assets',
        'broadlinkac_desktop.workers',
        'broadlinkac_desktop.workers.weather_worker',
        'broadlinkac_desktop.workers.typhoon_worker',
        'broadlinkac_desktop.workers.device_worker',
    ] + collect_submodules('hvac_ir'),
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
    [],
    exclude_binaries=True,
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
    icon='broadlink.icns',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BroadlinkAC',
)

app = BUNDLE(
    coll,
    name='BroadlinkAC.app',
    icon='broadlink.icns',
    bundle_identifier='com.local.broadlinkac',
)