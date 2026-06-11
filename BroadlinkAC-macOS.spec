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
        ('logos', 'logos'),
        ('fonts', 'fonts'),
        ('icons', 'icons'),
        ('使用文档.md', '.'),
        ('broadlink.png', '.'),
        ('broadlink.icns', '.'),
        ('broadlinkac_desktop/pyside', 'broadlinkac_desktop/pyside'),
    ],
    hiddenimports=[
        'protocols.haier', 'protocols.aux_ac', 'protocols.panasonic',
        'broadlinkac_desktop.pyside', 'broadlinkac_desktop.pyside.ac_tab',
        'broadlinkac_desktop.pyside.ty_tab', 'broadlinkac_desktop.pyside.dialogs',
        'broadlinkac_desktop.pyside._utils',
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

app = BUNDLE(
    exe,
    name='BroadlinkAC.app',
    icon='broadlink.icns',
    bundle_identifier='com.broadlinkac.app',
    info_plist={
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.13',
    },
)
