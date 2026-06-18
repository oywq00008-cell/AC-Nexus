"""开机自启管理 — 平台适配"""
import sys
import os
from pathlib import Path

STARTUP_NAME = "AC-Nexus"


def _get_startup_path():
    if sys.platform == "win32":
        return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / f"{STARTUP_NAME}.vbs"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "LaunchAgents" / f"{STARTUP_NAME}.plist"
    else:  # Linux
        return Path.home() / ".config" / "autostart" / f"{STARTUP_NAME}.desktop"


def is_enabled():
    return _get_startup_path().exists()


def enable(script_path=None):
    """启用开机自启。script_path: .py 入口文件绝对路径"""
    if script_path is None:
        script_path = str(Path(__file__).parent.parent / "ac_controller_pyside6.py")
    p = _get_startup_path()
    p.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32":
        vbs = f'CreateObject("WScript.Shell").Run """{sys.executable}"" ""{script_path}"" --tray", 0, False'
        p.write_text(vbs, encoding="utf-8")

    elif sys.platform == "darwin":
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{STARTUP_NAME}</string>
    <key>ProgramArguments</key>
    <array><string>{sys.executable}</string><string>{script_path}</string></array>
    <key>RunAtLoad</key><true/>
</dict>
</plist>"""
        p.write_text(plist, encoding="utf-8")

    else:  # Linux
        desktop = f"""[Desktop Entry]
Type=Application
Name={STARTUP_NAME}
Exec={sys.executable} {script_path}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
"""
        p.write_text(desktop, encoding="utf-8")


def disable():
    p = _get_startup_path()
    if p.exists():
        p.unlink()
