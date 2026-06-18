"""主题引擎：深色/浅色调色板、系统检测、全局 QSS、主题切换"""

import sys

from PySide6 import QtCore, QtGui, QtWidgets

import acnexus_core.config as _cfg


# ── 深色/浅色调色板 ──

def _dark_palette():
    p = QtGui.QPalette()
    p.setColor(QtGui.QPalette.Window, QtGui.QColor(45, 45, 45))
    p.setColor(QtGui.QPalette.WindowText, QtGui.QColor(220, 220, 220))
    p.setColor(QtGui.QPalette.Base, QtGui.QColor(35, 35, 35))
    p.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(45, 45, 45))
    p.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(45, 45, 45))
    p.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(220, 220, 220))
    p.setColor(QtGui.QPalette.Text, QtGui.QColor(220, 220, 220))
    p.setColor(QtGui.QPalette.Button, QtGui.QColor(55, 55, 55))
    p.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(220, 220, 220))
    p.setColor(QtGui.QPalette.BrightText, QtGui.QColor(255, 0, 0))
    p.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
    p.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
    p.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(255, 255, 255))
    return p


def _is_system_dark():
    try:
        if sys.platform == "win32":
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            val, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
            return val == 0
        elif sys.platform == "darwin":
            import subprocess
            r = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                               capture_output=True, text=True)
            return "Dark" in r.stdout
        else:
            # Linux: 检查 GTK 或 KDE 主题偏好
            import subprocess
            try:
                r = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                                   capture_output=True, text=True, timeout=3)
                if "dark" in r.stdout.lower():
                    return True
            except: pass
            try:
                r = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                                   capture_output=True, text=True, timeout=3)
                if "dark" in r.stdout.lower() or "prefer-dark" in r.stdout.lower():
                    return True
            except: pass
    except: pass
    return False


def apply_theme(mode=None):
    """应用主题 system light dark"""
    if mode is None:
        mode = _cfg.config.get("appearance_mode", "system")
    if mode == "system":
        dark = _is_system_dark()
    else:
        dark = (mode == "dark")

    from ._utils import set_dark_mode
    set_dark_mode(dark)

    app = QtWidgets.QApplication.instance()
    if dark:
        app.setPalette(_dark_palette())
    else:
        app.setPalette(app.style().standardPalette())

    # 刷新所有卡片、工具栏、状态栏样式
    for widget in app.allWidgets():
        if isinstance(widget, QtWidgets.QWidget):
            obj = widget.objectName()
            if obj == "card":
                from ._utils import _build_card_qss
                widget.setStyleSheet(_build_card_qss())
            elif obj == "info_box":
                bg = "#2D2D2D" if dark else "white"
                widget.setStyleSheet(f"QFrame#info_box {{ background:{bg}; border:1px solid {'#444' if dark else '#DEDEDE'}; border-radius:8px; }} QFrame#info_box QWidget {{ background-color:transparent; }}")
            elif obj == "sched_summary_box":
                bg = "#2D2D2D" if dark else "white"
                bd = "#444" if dark else "#DEDEDE"
                widget.setStyleSheet(f"QFrame#sched_summary_box {{ background:{bg}; border:1px solid {bd}; border-radius:8px; }}")
                # 内部内容动态渲染，触发重建以适配分隔线颜色
                from .ac_tab import _update_schedule_display
                _update_schedule_display(app, dark=dark)
            elif obj in ("ty_grp1", "ty_grp2"):
                bg = "#2D2D2D" if dark else "white"
                bd = "#444" if dark else "#DEDEDE"
                widget.setStyleSheet(f"QFrame#{obj} {{ background:{bg}; border:1px solid {bd}; border-radius:6px; }} QFrame#{obj} QWidget {{ background-color:transparent; }}")
            elif obj == "ty_modify_btn":
                widget.setStyleSheet(f"QPushButton#ty_modify_btn {{ border:1px solid {'#666' if dark else '#CCC'}; border-radius:4px; background:{'#3D3D3D' if dark else '#F5F5F5'}; color:{'#CCC' if dark else '#333'}; }} QPushButton#ty_modify_btn:hover {{ background:{'#555' if dark else '#E8E8E8'}; }}")
            elif obj == "tab_btn":
                checked_bg, unchecked_bg, color, checked_color, border = ("#2D2D2D", "#1E1E1E", "#999", "#5B9BD5", "#444") if dark else ("white", "#F1F5F9", "#666", "#2F80ED", "#E5E7EB")
                widget.setStyleSheet(f"""
                    QPushButton {{ padding:6px 0px; font-size:14px; font-weight:500; border:1px solid {border}; border-radius:10px; background:{unchecked_bg}; color:{color}; }}
                    QPushButton:checked {{ background:{checked_bg}; color:{checked_color}; font-weight:bold; border:1px solid {checked_color}; }}
                """)
            elif obj == "central_bg":
                widget.setStyleSheet(f"background: {'#1A1A1A' if dark else '#F5F8FC'};")
            elif obj in ("temp_down_btn", "temp_up_btn"):
                bg = "#3D3D3D" if dark else "#F0F0F0"
                hv = "#555" if dark else "#DEE4EA"
                fg = "#DCDCDC" if dark else "#333"
                widget.setStyleSheet(f"QPushButton#{obj} {{ border:none; background:{bg}; color:{fg}; border-radius:8px; font-size:16px; font-weight:bold; }} QPushButton#{obj}:hover {{ background:{hv}; }}")
            elif obj == "status_bar":
                bg, border = ("#2D2D2D", "#444") if dark else ("#F8FAFC", "#E5E7EB")
                widget.setStyleSheet(f"QStatusBar {{ background:{bg}; border-top:1px solid {border}; }}")
    # 刷新状态栏标签颜色
    for label in app.allWidgets():
        if isinstance(label, QtWidgets.QLabel):
            kind = label.property("status_label_kind")
            if kind == "ok":
                label.setStyleSheet(f"color:{'#4CAF50' if dark else '#27AE60'}; font-weight:bold;")
            elif kind == "version":
                label.setStyleSheet(f"color:{'#888' if dark else '#999'};")
    # 更新表头
    for header in app.allWidgets():
        if isinstance(header, QtWidgets.QHeaderView):
            hl = "#1E1E1E" if dark else "#F5F8FC"
            hc = "#DCDCDC" if dark else "#333"
            hb = "#444" if dark else "#DEDEDE"
            header.setStyleSheet(f"QHeaderView::section {{ background:{hl}; color:{hc}; border-bottom:1px solid {hb}; padding:4px; font-weight:bold; }}")
    # 更新全局主窗口/状态栏/菜单 QSS
    _set_global_qss(app, dark)
    # 刷新所有文字标签颜色
    from ._utils import refresh_labels
    refresh_labels(app)
    # 刷新设备按钮 hover 样式
    from ..app_pyside6 import App
    for w in app.topLevelWidgets():
        if isinstance(w, App) and hasattr(w, '_refresh_brand_btn_style'):
            w._refresh_brand_btn_style()
            break


def _set_global_qss(app, dark):
    """重新设置全局 QSS"""
    if dark:
        app.setStyleSheet("""
            QMainWindow { background: #1A1A1A; }
            QMenuBar { background: #2D2D2D; color: #DCDCDC; border-bottom: 1px solid #444; }
            QMenuBar::item:selected { background: #3D3D3D; }
            QStatusBar { background: #2D2D2D; color: #999; border-top: 1px solid #444; }
        """)
    else:
        app.setStyleSheet("""
            QMainWindow { background: #F5F8FC; }
            QMenuBar { background: white; border-bottom: 1px solid #E5E7EB; }
            QMenuBar::item:selected { background: #E8F0FE; }
        """)
    # ComboBox 选中色 — Fusion 下 QSS 无法穿透弹窗，必须用 QPalette，且必须在 setStyleSheet 之后
    p = app.palette()
    p.setColor(QtGui.QPalette.Highlight, QtGui.QColor("#E8E8E8" if not dark else "#444"))
    p.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#333" if not dark else "#EEE"))
    app.setPalette(p)
