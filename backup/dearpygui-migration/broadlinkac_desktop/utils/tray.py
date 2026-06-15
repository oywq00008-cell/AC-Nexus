"""系统托盘功能模块"""

import platform
import threading
from pathlib import Path

import pystray
from PIL import Image

from .assets import get_asset

IS_MAC = platform.system() == "Darwin"
APP_NAME = "BroadlinkAC"


class TrayManager:
    """系统托盘管理器"""
    
    def __init__(self, app):
        self.app = app
        self.tray_icon = None
        
    def setup(self):
        """创建系统托盘图标（Windows 隐藏到任务栏）"""
        if IS_MAC:
            return
        img_path = get_asset("broadlink.png")
        if not img_path.exists():
            return
        img = Image.open(img_path)
        menu = pystray.Menu(
            pystray.MenuItem("显示", self.restore_window, default=True),
            pystray.MenuItem("退出", self.quit_app),
        )
        self.tray_icon = pystray.Icon(APP_NAME, img, APP_NAME, menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
    
    def on_close(self):
        """点 X：Mac 退出，Windows 最小化到托盘"""
        if IS_MAC:
            self.app.quit()
        else:
            self.app.withdraw()
    
    def restore_window(self):
        """从托盘恢复窗口"""
        self.app.deiconify()
        self.app.update_idletasks()  # 确保窗口完全准备好
        self.app.lift()
        self.app.focus_force()
    
    def quit_app(self):
        """托盘菜单退出"""
        if self.tray_icon:
            self.tray_icon.stop()
        self.app.quit()