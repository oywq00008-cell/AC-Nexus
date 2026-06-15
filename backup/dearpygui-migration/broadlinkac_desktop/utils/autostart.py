"""开机自启功能模块"""

import sys
import platform
from pathlib import Path

IS_MAC = platform.system() == "Darwin"
LAUNCH_AGENT = Path.home() / "Library/LaunchAgents/com.local.ac-controller.plist"


def check_autostart():
    return LAUNCH_AGENT.exists()


def enable_autostart():
    if IS_MAC:
        # macOS: LaunchAgent plist
        import plistlib
        plist = {
            "Label": "com.local.ac-controller",
            "ProgramArguments": [sys.executable, str(Path(__file__).resolve().parent.parent.parent / "ac_controller.py")],
            "RunAtLoad": True,
        }
        LAUNCH_AGENT.parent.mkdir(parents=True, exist_ok=True)
        plistlib.dump(plist, LAUNCH_AGENT.open("wb"))
    else:
        # Windows: 注册表 Run 键
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "BroadlinkAC", 0, winreg.REG_SZ, sys.executable)


def disable_autostart():
    if IS_MAC:
        if LAUNCH_AGENT.exists():
            LAUNCH_AGENT.unlink()
    else:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, "BroadlinkAC")
        except OSError:
            pass