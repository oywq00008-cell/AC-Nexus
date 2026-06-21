# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

pyside_hidden = [
    'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
    'shiboken6',
]

a = Analysis(
    ['ac_controller_pyside6.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('protocols', 'protocols'),
        ('hvac_ir', 'hvac_ir'),
        ('logos', 'logos'),
        ('fonts', 'fonts'),
        ('icons', 'icons'),
        ('langs', 'langs'),
        ('使用文档.md', '.'),
        ('acnexus.png', '.'),
        ('acnexus_desktop/pyside', 'acnexus_desktop/pyside'),
    ],
    hiddenimports=[
        'protocols.haier', 'protocols.aux_ac', 'protocols.panasonic',
        'acnexus_core.ir_learner', 'acnexus_core.autostart','acnexus_core.xiaomi_cloud','acnexus_core.xiaomi_local',
        'acnexus_desktop.pyside', 'acnexus_desktop.pyside.ac_tab',
        'acnexus_desktop.pyside.ty_tab', 'acnexus_desktop.pyside.dialogs',
        'acnexus_desktop.pyside._utils',
        'acnexus_desktop.pyside.theme',
        'acnexus_desktop.pyside.settings_dialog',
        'acnexus_desktop.pyside.schedule_dialog',
        'acnexus_desktop.pyside.repair_dialog',
        'acnexus_desktop.pyside.learn_dialog',
        'acnexus_desktop.pyside.brand_dialog','acnexus_desktop.pyside.xiaomi_login_dialog','acnexus_desktop.pyside.xiaomi_device_picker','schedule','python-miio','qrcode','Pillow','pycryptodome','requests',
    ] + pyside_hidden + collect_submodules('hvac_ir'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6.Qt3D*', 'PySide6.QtWebEngine*', 'PySide6.QtCharts*',
        'PySide6.QtQuick*', 'PySide6.QtQml*', 'PySide6.QtMultimedia*',
        'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtSensors',
        'PySide6.QtSerialPort', 'PySide6.QtSql', 'PySide6.QtTest',
        'PySide6.QtHelp', 'PySide6.QtLocation', 'PySide6.QtPositioning',
        'PySide6.QtTextToSpeech', 'PySide6.QtWebChannel',
    ],
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
    name='AC-Nexus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
