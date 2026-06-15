"""资源加载工具模块"""

import sys
from pathlib import Path


def get_asset(filename):
    """获取资源文件路径，兼容源码运行和 PyInstaller 打包"""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / filename
    return Path(__file__).resolve().parent.parent.parent / filename