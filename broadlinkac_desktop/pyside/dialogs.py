"""对话框模块：设置 / 诊断 / 日志 / 规则编辑 / 台风预警"""

import os, sys, subprocess, json, urllib.request, threading

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6 import QtSvg

import broadlinkac_core.config as _cfg
from broadlinkac_core.config import save_config, apply_config, AC_BRANDS, LOG_DIR
from broadlinkac_core.ac_control import MODES, MODE_KEYS
from broadlinkac_core.logger import get_log_dates, write_log
from broadlinkac_core.weather import city_lookup
from ._utils import frm, lbl


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
                widget.setStyleSheet(f"QFrame#sched_summary_box {{ background:{bg}; border:1px solid {bd}; border-radius:8px; }} QFrame#sched_summary_box QWidget {{ background-color:transparent; }}")
                # 内部内容动态渲染，触发重建以适配分隔线颜色
                from broadlinkac_desktop.pyside.ac_tab import _update_schedule_display
                _update_schedule_display(app)
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


def _make_dialog(parent, title, w, h, frameless=False):
    """创建对话框：Windows 无边框自绘，其他原生。frameless=True 用原生窗口"""
    if frameless or sys.platform != "win32":
        dlg = QtWidgets.QDialog(parent)
    else:
        dlg = QtWidgets.QDialog(parent, QtCore.Qt.FramelessWindowHint)
        dlg.setAttribute(QtCore.Qt.WA_TranslucentBackground)
    dlg.resize(w, h)
    dlg.setWindowModality(QtCore.Qt.WindowModal)
    dlg.setWindowTitle(title)
    return dlg


def _dialog_content(dlg, title="", title_size=13, frameless=False):
    """返回 (layout, swl)，Windows 下自绘标题+白底圆角，其他原生
       frameless=True 跳过外层卡片框，用原生窗口背景"""
    if sys.platform == "win32" and not frameless:
        from ._utils import is_dark
        dark = is_dark()
        bg = "#2D2D2D" if dark else "white"
        bd = "#444" if dark else "#DEDEDE"
        outer = QtWidgets.QFrame(dlg)
        outer.setStyleSheet(f"QFrame {{ background:{bg}; border:1px solid {bd}; border-radius:12px; }}")
        ov = QtWidgets.QVBoxLayout(outer); ov.setContentsMargins(0, 0, 0, 0); ov.setSpacing(0)
        if title:
            tb = QtWidgets.QWidget(); tb.setFixedHeight(36)
            tb.setStyleSheet(f"background: transparent; border-bottom: 1px solid {bd};")
            tl = QtWidgets.QHBoxLayout(tb); tl.setContentsMargins(16, 0, 8, 0)
            tl.addWidget(lbl(title, bold=True, size=title_size)); tl.addStretch()
            close = QtWidgets.QPushButton("✕"); close.setFixedSize(28, 28); close.setFlat(True)
            close.setStyleSheet(f"QPushButton {{ font-size:14px; color:{'#AAA' if dark else '#888'}; border:none; background:transparent; }} QPushButton:hover {{ background:{'#444' if dark else '#F0F0F0'}; border-radius:4px; }}")
            close.clicked.connect(dlg.reject); tl.addWidget(close)
            ov.addWidget(tb)
        layout = QtWidgets.QVBoxLayout(); layout.setContentsMargins(12, 8, 12, 12)
        scroll = QtWidgets.QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        sw = QtWidgets.QWidget(); sw.setStyleSheet(f"background: {bg};")
        swl = QtWidgets.QVBoxLayout(sw); scroll.setWidget(sw); layout.addWidget(scroll)
        ov.addLayout(layout)
        full = QtWidgets.QVBoxLayout(dlg); full.setContentsMargins(0, 0, 0, 0); full.addWidget(outer)
    else:
        layout = QtWidgets.QVBoxLayout(dlg)
        layout.setContentsMargins(20 if frameless else 12, 16 if frameless else 12,
                                   20 if frameless else 12, 16 if frameless else 12)
        if frameless:
            from ._utils import is_dark
            dlg.setStyleSheet(f"QDialog {{ background:{ '#2D2D2D' if is_dark() else 'white' }; }}")
        sw = QtWidgets.QWidget(); swl = QtWidgets.QVBoxLayout(sw); layout.addWidget(sw)
    return layout, swl


# ── 设置对话框 ──
def _do_learn_wizard(settings_dlg, cb):
    """模块级函数：从设置弹窗中启动学习向导"""
    from .learn_dialog import NewRemoteDialog, LearnWizard
    from broadlinkac_core.ir_learner import list_custom

    new_dlg = NewRemoteDialog(settings_dlg)
    result = new_dlg.exec()
    if not result:
        return

    saved_name = result["name"]
    while True:
        wizard = LearnWizard(settings_dlg, result["name"], result["logo"], result["steps"])
        if not wizard.exec():
            break
        # 继续学习：用编辑模式打开，加载已有组合
        from broadlinkac_core.ir_learner import load_custom_codes
        existing = load_custom_codes().get(result["name"], {})
        new_dlg = NewRemoteDialog(settings_dlg, edit_mode=True,
                                   edit_name=result["name"],
                                   edit_logo=result["logo"],
                                   edit_codes=existing.get("codes", {}))
        result = new_dlg.exec()
        if not result or "steps" not in result:
            break

    customs = list_custom()
    for i in range(cb.count() - 1, -1, -1):
        if cb.itemText(i).startswith("🛠 "):
            cb.removeItem(i)
    for c in customs:
        cb.addItem(f"🛠 {c}")
    idx = cb.findText(f"🛠 {saved_name}")
    if idx >= 0:
        cb.setCurrentIndex(idx)


def _do_edit_custom(settings_dlg, cb, name, entry):
    """编辑已有自定义遥控器"""
    from .learn_dialog import NewRemoteDialog, LearnWizard, LOGO_LIST
    from broadlinkac_core.ir_learner import load_custom_codes, save_learned_codes, save_custom_codes, list_custom

    # 打开编辑窗口（加载已有数据）
    edit_dlg = NewRemoteDialog(settings_dlg, edit_mode=True, edit_name=name, edit_logo=entry.get("logo", ""), edit_codes=entry.get("codes", {}))
    result = edit_dlg.exec()
    if not result:
        return

    # result = {"name": ..., "logo": ..., "new_combos": [...], "deleted_combos": [...]}
    new_name = result["name"]
    new_logo = result["logo"]

    # 先删除已移除的组合
    codes = entry.get("codes", {}).copy()
    for dk in result.get("deleted_combos", []):
        codes.pop(dk, None)
    # 直接覆盖保存（不合并，确保删除生效）
    all_codes = load_custom_codes()
    all_codes[new_name] = {"logo": new_logo, "learned_at": entry.get("learned_at", ""), "codes": codes}
    if new_name != name:
        all_codes.pop(name, None)
    save_custom_codes(all_codes)

    # 如果有新增组合，弹出学习向导（_finish 内部会 merge 到现有码）
    if result.get("new_combos"):
        steps = [("关机", "请先打开遥控器，然后对准博联设备按遥控器的【关机】键")]
        for combo in result["new_combos"]:
            parts = combo.replace("开机_", "").replace("°C", "").split("_")
            if len(parts) >= 3:
                m, t, f = parts[0], parts[1], parts[2]
                steps.append((combo, f"请在遥控器上设为：模式【{m}】、温度【{t}°C】、风速【{f}】。\n设好后关掉遥控器，对准博联设备按【开机】"))
        wizard = LearnWizard(settings_dlg, new_name, new_logo, steps)
        wizard.exec()

    # 刷新下拉框
    customs = list_custom()
    for i in range(cb.count() - 1, -1, -1):
        if cb.itemText(i).startswith("🛠 "):
            cb.removeItem(i)
    for c in customs:
        cb.addItem(f"🛠 {c}")
    idx = cb.findText(f"🛠 {new_name}")
    if idx >= 0:
        cb.setCurrentIndex(idx)


def open_settings(app):
    dlg = QtWidgets.QDialog(app, QtCore.Qt.FramelessWindowHint if sys.platform == "win32" else QtCore.Qt.Dialog)
    # 继承主窗口的 QPalette (Fusion 焦点框颜色 = Highlight 色)
    dlg.setPalette(app.palette())
    if sys.platform == "win32":
        dlg.setAttribute(QtCore.Qt.WA_TranslucentBackground)
    dlg.resize(500, 680)
    dlg.setWindowModality(QtCore.Qt.WindowModal)
    dlg.setWindowTitle("设置")

    if sys.platform == "win32":
        # 自绘无边框窗口
        from ._utils import is_dark
        dark = is_dark()
        outer_bg = "#2D2D2D" if dark else "white"
        outer_bd = "#444" if dark else "#DEDEDE"
        title_bd = "#444" if dark else "#E5E7EB"
        title_close_hover = "#444" if dark else "#F0F0F0"

        outer = QtWidgets.QFrame(dlg)
        outer.setObjectName("settings_outer")
        outer.setStyleSheet(f"QFrame#settings_outer {{ background:{outer_bg}; border:1px solid {outer_bd}; border-radius:12px; }}")
        ov = QtWidgets.QVBoxLayout(outer)
        ov.setContentsMargins(0, 0, 0, 0)
        ov.setSpacing(0)

        # 自绘标题栏
        title_bar = QtWidgets.QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet(f"background: transparent; border-bottom: 1px solid {title_bd};")
        tbl = QtWidgets.QHBoxLayout(title_bar)
        tbl.setContentsMargins(16, 0, 8, 0)
        gear_svg = os.path.join(os.path.dirname(__file__), "..", "..", "icons", "settings_black.svg")
        gear_px = QtGui.QPixmap(22, 22); gear_px.fill(QtCore.Qt.transparent)
        QtSvg.QSvgRenderer(gear_svg).render(QtGui.QPainter(gear_px))
        gear_btn = QtWidgets.QToolButton(); gear_btn.setIcon(QtGui.QIcon(gear_px)); gear_btn.setIconSize(QtCore.QSize(22, 22))
        gear_btn.setStyleSheet("QToolButton { border:none; background:transparent; margin-top:1px; }"); gear_btn.setEnabled(False)
        tbl.addWidget(gear_btn)
        tbl.addWidget(lbl("设置", bold=True, size=14))
        tbl.addStretch()
        close_btn = QtWidgets.QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setFlat(True)
        close_color = "#AAA" if dark else "#888"
        close_btn.setStyleSheet(f"QPushButton {{ font-size:14px; color:{close_color}; border:none; background:transparent; }} QPushButton:hover {{ background:{title_close_hover}; border-radius:4px; }}")
        close_btn.clicked.connect(dlg.reject)
        tbl.addWidget(close_btn)
        ov.addWidget(title_bar)

        def move_window(event):
            if event.buttons() == QtCore.Qt.LeftButton:
                dlg.move(event.globalPosition().toPoint() - title_bar.property("drag_pos"))
        title_bar.mouseMoveEvent = move_window
        title_bar.mousePressEvent = lambda e: title_bar.setProperty("drag_pos", e.globalPosition().toPoint() - dlg.frameGeometry().topLeft())

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        scroll = QtWidgets.QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        sw = QtWidgets.QWidget()
        sw.setStyleSheet("background: white;")
        swl = QtWidgets.QVBoxLayout(sw); scroll.setWidget(sw); layout.addWidget(scroll)
        ov.addLayout(layout)

        full = QtWidgets.QVBoxLayout(dlg)
        full.setContentsMargins(0, 0, 0, 0)
        full.addWidget(outer)
    else:
        # macOS/Linux 原生窗口
        layout = QtWidgets.QVBoxLayout(dlg)
        scroll = QtWidgets.QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; }")
        sw = QtWidgets.QWidget(); swl = QtWidgets.QVBoxLayout(sw); scroll.setWidget(sw); layout.addWidget(scroll)
        outer = dlg  # 兼容后续引用
        title_bar = None
        close_btn = None

    # ══════════════════════════════════════════
    # 卡片布局：左侧 1/5 图标区 + 右侧 4/5 内容区
    # ══════════════════════════════════════════

    def _make_card(icon_path, title):
        from ._utils import is_dark
        dark = is_dark()
        card_bg = "#2D2D2D" if dark else "white"
        card_bd = "#444" if dark else "#E5E7EB"
        side_bg = "#1E2D3D" if dark else "#EDF8FF"
        title_color = "#5B9BD5" if dark else "#1AA6FF"
        card = QtWidgets.QFrame()
        card.setObjectName("settings_card")
        card.setStyleSheet(f"QFrame#settings_card {{ background:{card_bg}; border:1px solid {card_bd}; border-radius:12px; }}")
        cl = QtWidgets.QHBoxLayout(card); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)
        side = QtWidgets.QWidget()
        side.setFixedWidth(100)
        side.setStyleSheet(f"background:{side_bg}; border-top-left-radius:12px; border-bottom-left-radius:12px;")
        sl = QtWidgets.QVBoxLayout(side); sl.setAlignment(QtCore.Qt.AlignCenter)
        sl.setContentsMargins(8, 12, 8, 12)
        svg = QSvgWidget(icon_path)
        svg.setFixedSize(40, 40)
        sl.addWidget(svg, alignment=QtCore.Qt.AlignCenter)
        tl = lbl(title, bold=True, size=11, color=title_color)
        sl.addWidget(tl, alignment=QtCore.Qt.AlignCenter)
        cl.addWidget(side)
        right = QtWidgets.QWidget()
        rl = QtWidgets.QVBoxLayout(right); rl.setContentsMargins(12, 10, 12, 10)
        cl.addWidget(right, 1)
        return card, rl

    icons_dir = os.path.join(os.path.dirname(__file__), "..", "..", "icons")

    # ── 1. 基础设置 ──
    card1, c1l = _make_card(os.path.join(icons_dir, "settings.svg"), "基础设置")

    from broadlinkac_core.autostart import is_enabled, enable, disable
    r = QtWidgets.QWidget(); rl = QtWidgets.QHBoxLayout(r); rl.setContentsMargins(0, 0, 0, 0)
    rl.addWidget(QtWidgets.QLabel("开机自启:")); rl.addStretch(1)
    autostart_cb = QtWidgets.QComboBox(); autostart_cb.addItems(["关", "开"])
    autostart_cb.setCurrentText("开" if is_enabled() else "关")
    autostart_cb.setMinimumWidth(140); autostart_cb.setMaximumWidth(140)
    autostart_cb.setStyleSheet("QComboBox { selection-background-color: #2F80ED; selection-color: white; }")
    autostart_cb.setEditable(True); autostart_cb.lineEdit().setAlignment(QtCore.Qt.AlignCenter); autostart_cb.lineEdit().setReadOnly(True)
    def toggle_autostart(txt):
        script = os.path.join(os.path.dirname(__file__), "..", "ac_controller_pyside6.py")
        if txt == "开": enable(script)
        else: disable()
    autostart_cb.currentTextChanged.connect(toggle_autostart)
    rl.addWidget(autostart_cb, alignment=QtCore.Qt.AlignRight); c1l.addWidget(r)

    r = QtWidgets.QWidget(); rl = QtWidgets.QHBoxLayout(r); rl.setContentsMargins(0, 0, 0, 0)
    rl.addWidget(QtWidgets.QLabel("主题:")); rl.addStretch(1)
    theme_cb = QtWidgets.QComboBox()
    theme_cb.setMinimumWidth(140); theme_cb.setMaximumWidth(140)
    theme_cb.setStyleSheet("QComboBox { selection-background-color: #2F80ED; selection-color: white; }")
    theme_cb.setEditable(True); theme_cb.lineEdit().setAlignment(QtCore.Qt.AlignCenter); theme_cb.lineEdit().setReadOnly(True)
    rl.addWidget(theme_cb, alignment=QtCore.Qt.AlignRight); c1l.addWidget(r)
    mode_map = {"system": "跟随系统", "light": "浅色", "dark": "深色"}
    cur_mode = _cfg.config.get("appearance_mode", "system")
    with QtCore.QSignalBlocker(theme_cb):
        theme_cb.addItems(["跟随系统", "浅色", "深色"])
        theme_cb.setCurrentText(mode_map.get(cur_mode, "跟随系统"))
    def _refresh_settings_theme(dark):
        """刷新设置窗口自身的主题"""
        if sys.platform != "win32": return
        outer.setStyleSheet(f"QFrame#settings_outer {{ background:{'#2D2D2D' if dark else 'white'}; border:1px solid {'#444' if dark else '#DEDEDE'}; border-radius:12px; }}")
        title_bar.setStyleSheet(f"background: transparent; border-bottom: 1px solid {'#444' if dark else '#E5E7EB'};")
        close_btn.setStyleSheet(f"QPushButton {{ font-size:14px; color:{'#AAA' if dark else '#888'}; border:none; background:transparent; }} QPushButton:hover {{ background:{'#444' if dark else '#F0F0F0'}; border-radius:4px; }}")
        scroll.setStyleSheet(f"QScrollArea {{ border:none; background:{'#2D2D2D' if dark else 'white'}; }}")
        sw.setStyleSheet(f"background: {'#2D2D2D' if dark else 'white'};")
        # 卡片标头
        for card in dlg.findChildren(QtWidgets.QFrame):
            if card.objectName() == "settings_card":
                card.setStyleSheet(f"QFrame#settings_card {{ background:{'#2D2D2D' if dark else 'white'}; border:1px solid {'#444' if dark else '#E5E7EB'}; border-radius:12px; }}")
        # 侧栏
        for side in dlg.findChildren(QtWidgets.QWidget):
            s = side.styleSheet()
            if "border-top-left-radius:12px" in s and "border-bottom-left-radius:12px" in s:
                side.setStyleSheet(f"background:{'#1E2D3D' if dark else '#EDF8FF'}; border-top-left-radius:12px; border-bottom-left-radius:12px;")
        # 城市搜索输入框
        for inp in dlg.findChildren(QtWidgets.QLineEdit):
            if inp.objectName() == "city_search_input":
                inp.setStyleSheet(f"QLineEdit {{ color:{'#EEE' if dark else '#333'}; background:{'#3D3D3D' if dark else 'white'}; border:1px solid {'#555' if dark else '#DEDEDE'}; border-radius:6px; padding:4px 8px; }}")
        # 取消 / 保存按钮（只改颜色，不改尺寸）
        for btn in dlg.findChildren(QtWidgets.QPushButton):
            if btn.objectName() == "settings_cancel_btn":
                btn.setStyleSheet(f"QPushButton#settings_cancel_btn {{ background:{'#555' if dark else 'white'}; color:{'#DDD' if dark else '#333'}; border:1px solid {'#666' if dark else '#DEDEDE'}; border-radius:8px; font-size:13px; }} QPushButton#settings_cancel_btn:hover {{ background:{'#666' if dark else '#F5F5F5'}; }}")
            elif btn.objectName() == "settings_save_btn":
                btn.setStyleSheet(f"QPushButton#settings_save_btn {{ background:{'#0076D4' if not dark else '#2F80ED'}; color:white; border:1px solid {'#0076D4' if not dark else '#2F80ED'}; border-radius:8px; font-size:13px; font-weight:500; }} QPushButton#settings_save_btn:hover {{ background:{'#0065B8' if not dark else '#1A6FD8'}; }}")
    def on_theme_change(t):
        mode = {v: k for k, v in mode_map.items()}.get(t, "system")
        apply_theme(mode)
        d = mode == "dark" or (mode == "system" and _is_system_dark())
        _refresh_settings_theme(d)
        _cfg.config["appearance_mode"] = mode
        save_config(_cfg.config, sync_device=False)
    theme_cb.currentTextChanged.connect(on_theme_change)

    r = QtWidgets.QWidget(); rl = QtWidgets.QHBoxLayout(r); rl.setContentsMargins(0, 0, 0, 0)
    rl.addWidget(QtWidgets.QLabel("空调遥控器:")); rl.addStretch(1)
    brand_cb = QtWidgets.QComboBox(); brand_cb.addItems(list(AC_BRANDS.keys()))
    from broadlinkac_core.ir_learner import list_custom
    customs = list_custom()
    for c in customs:
        brand_cb.addItem("🛠 " + c)
    cur_brand = _cfg.config.get("brand", "格力")
    idx = brand_cb.findText("🛠 " + cur_brand)
    if idx >= 0: brand_cb.setCurrentIndex(idx)
    else: brand_cb.setCurrentText(cur_brand)
    brand_cb.setMinimumWidth(140); brand_cb.setMaximumWidth(140)
    brand_cb.setStyleSheet("QComboBox { selection-background-color: #2F80ED; selection-color: white; }")
    brand_cb.setEditable(True); brand_cb.lineEdit().setAlignment(QtCore.Qt.AlignCenter); brand_cb.lineEdit().setReadOnly(True)
    rl.addWidget(brand_cb, alignment=QtCore.Qt.AlignRight); c1l.addWidget(r)

    r = QtWidgets.QWidget(); rl = QtWidgets.QHBoxLayout(r); rl.setContentsMargins(0, 0, 0, 0)
    rl.addStretch(1)
    def _make_icon_btn(svg_path, qss, tooltip, size=28):
        px = QtGui.QPixmap(size-8, size-8); px.fill(QtCore.Qt.transparent)
        QtSvg.QSvgRenderer(svg_path).render(QtGui.QPainter(px))
        btn = QtWidgets.QToolButton(); btn.setIcon(QtGui.QIcon(px)); btn.setIconSize(QtCore.QSize(size-8, size-8))
        btn.setFixedSize(size, size); btn.setStyleSheet(qss); btn.setToolTip(tooltip)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        return btn

    del_btn = _make_icon_btn(os.path.join(icons_dir, "delete_red.svg"),
        "QToolButton { border:1px solid #E74C3C; border-radius:4px; } QToolButton:hover { background:#FDE8E8; }",
        "删除当前自定义品牌")
    def _delete_custom():
        name = brand_cb.currentText()
        if not name.startswith("🛠 "): return
        name = name[2:]
        if QtWidgets.QMessageBox.question(dlg, "确认删除", "确定要删除 '" + name + "' 及其所有学习码吗？",
                                          QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No) != QtWidgets.QMessageBox.Yes:
            return
        from broadlinkac_core.ir_learner import load_custom_codes, save_custom_codes
        codes = load_custom_codes(); codes.pop(name, None); save_custom_codes(codes)
        for i in range(brand_cb.count() - 1, -1, -1):
            if brand_cb.itemText(i).startswith("🛠 "): brand_cb.removeItem(i)
        from broadlinkac_core.ir_learner import list_custom
        for c in list_custom(): brand_cb.addItem("🛠 " + c)
        brand_cb.setCurrentText("格力"); del_btn.setVisible(False); edit_btn.setVisible(False)
    del_btn.clicked.connect(_delete_custom); rl.addWidget(del_btn)

    edit_btn = _make_icon_btn(os.path.join(icons_dir, "edit_blue.svg"),
        "QToolButton { border:1px solid #2F80ED; border-radius:4px; } QToolButton:hover { background:#E8F0FE; }",
        "编辑当前自定义遥控器")
    def _edit_custom():
        name = brand_cb.currentText()
        if not name.startswith("🛠 "): return
        name = name[2:]
        from broadlinkac_core.ir_learner import load_custom_codes
        all_codes = load_custom_codes()
        entry = all_codes.get(name)
        if not entry: return
        _do_edit_custom(dlg, brand_cb, name, entry)
    edit_btn.clicked.connect(_edit_custom); rl.addWidget(edit_btn)
    brand_cb.currentIndexChanged.connect(lambda: [del_btn.setVisible(brand_cb.currentText().startswith("🛠 ")), edit_btn.setVisible(brand_cb.currentText().startswith("🛠 "))])
    is_custom = brand_cb.currentText().startswith("🛠 "); del_btn.setVisible(is_custom); edit_btn.setVisible(is_custom)

    learn_btn = _make_icon_btn(os.path.join(icons_dir, "add.svg"),
        "QToolButton { border:1px solid #2F80ED; border-radius:4px; } QToolButton:hover { background:#E8F0FE; }",
        "新增自定义遥控器")
    learn_btn.clicked.connect(lambda: _do_learn_wizard(dlg, brand_cb))
    rl.addWidget(learn_btn); c1l.addWidget(r)
    swl.addWidget(card1)

    # ── 2. 城市设置 ──
    card2, c2l = _make_card(os.path.join(icons_dir, "location_blue.svg"), "城市设置")

    loc_info = QtWidgets.QLabel("当前: " + _cfg.LOCATION['name'])
    loc_info.setStyleSheet("color:#27AE60; font-size:13px;")
    c2l.addWidget(loc_info, alignment=QtCore.Qt.AlignRight)

    dl = dlg
    def auto_locate():
        loc_info.setText("⏳ 定位中..."); loc_info.setStyleSheet("color:#E67E22;")
        try:
            resp = urllib.request.urlopen("http://ip-api.com/json/?fields=lat,lon,city,regionName,status", timeout=8)
            data = json.loads(resp.read())
            if data.get("status") == "success":
                dl._picked_loc = {"lat": data["lat"], "lon": data["lon"], "name": data['city'] + data.get('regionName','')}
                loc_info.setText("当前: " + dl._picked_loc['name'])
                loc_info.setStyleSheet("color:#27AE60;")
            else: loc_info.setText("定位失败"); loc_info.setStyleSheet("color:#E74C3C;")
        except Exception as e: loc_info.setText("定位失败: " + str(e)); loc_info.setStyleSheet("color:#E74C3C;")
    b = QtWidgets.QPushButton()
    b.setIcon(QtGui.QIcon(os.path.join(icons_dir, "location.svg")))
    b.setText(" 自动定位")
    b.clicked.connect(lambda: threading.Thread(target=auto_locate, daemon=True).start())
    c2l.addWidget(b)
    c2l.addWidget(lbl("自动定位基于IP, 建议使用搜索", size=9, color="gray"), alignment=QtCore.Qt.AlignRight)

    sr = QtWidgets.QWidget(); srl = QtWidgets.QHBoxLayout(sr); srl.setContentsMargins(0, 0, 0, 0)
    city_entry = QtWidgets.QLineEdit()
    city_entry.setPlaceholderText("输入位置(如：翻斗花园)")
    city_entry.setObjectName("city_search_input")
    srl.addWidget(city_entry)
    dw = dlg
    search_btn = QtWidgets.QPushButton("  🔍 搜索  ")
    def do_search():
        city = city_entry.text().strip()
        if not city: return
        search_btn.setText("⏳ 搜索中...")
        QtCore.QTimer.singleShot(50, lambda: _do_search_thread(city))
    def _reset_btn():
        search_btn.setText("  🔍 搜索  ")
    def _do_search_thread(city):
        def _run():
            try:
                results = _cfg.search_cities(city)
                app._ui(lambda: [_show_city_picker(results, city), _reset_btn()])
            except Exception as e:
                app._ui(lambda: [search_btn.setText("❌ 搜索失败"), QtCore.QTimer.singleShot(2000, _reset_btn)])
        threading.Thread(target=_run, daemon=True).start()
    def _apply_picked(lat, lon, dname):
        dw._picked_loc = {"lat": lat, "lon": lon, "name": dname}
        loc_info.setText("当前: " + dname)
        loc_info.setStyleSheet("color:#27AE60;")
    def _show_city_picker(results, city=""):
        """弹出城市选择窗口 — 0条/1条/多条都弹窗，由用户手动选择"""
        picker = QtWidgets.QDialog(dlg, QtCore.Qt.FramelessWindowHint if sys.platform == "win32" else QtCore.Qt.Dialog)
        picker.setWindowModality(QtCore.Qt.WindowModal)
        picker.setWindowTitle("选择城市")
        picker.resize(300, 340)
        if sys.platform == "win32":
            picker.setAttribute(QtCore.Qt.WA_TranslucentBackground)
            from ._utils import is_dark
            dark = is_dark()
            outer_bg = "#2D2D2D" if dark else "white"
            outer_bd = "#444" if dark else "#DEDEDE"
            outer = QtWidgets.QFrame(picker)
            outer.setObjectName("picker_outer")
            outer.setStyleSheet(f"QFrame#picker_outer {{ background:{outer_bg}; border:1px solid {outer_bd}; border-radius:12px; }}")
            # 阴影
            shadow = QtWidgets.QGraphicsDropShadowEffect()
            shadow.setBlurRadius(24)
            shadow.setOffset(0, 4)
            shadow.setColor(QtGui.QColor(0, 0, 0, 40))
            outer.setGraphicsEffect(shadow)
            ov = QtWidgets.QVBoxLayout(outer); ov.setContentsMargins(0, 0, 0, 0); ov.setSpacing(0)
            tb = QtWidgets.QWidget(); tb.setFixedHeight(38)
            tb.setStyleSheet(f"background: transparent; border-bottom: 1px solid {outer_bd}; QWidget {{ border:none; background:transparent; }}")
            t_bl = QtWidgets.QHBoxLayout(tb); t_bl.setContentsMargins(14, 0, 8, 0)
            title_text = "搜索结果 — 请选择你的城市" if results else f"未找到 \"{city}\" 的匹配结果"
            loc_icon = QtWidgets.QLabel()
            loc_icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "icons", "location.svg")
            loc_icon.setPixmap(QtGui.QIcon(loc_icon_path).pixmap(18, 18))
            t_bl.addWidget(loc_icon)
            t_bl.addWidget(lbl(title_text, bold=True, size=11))
            t_bl.addStretch()
            close_btn = QtWidgets.QPushButton("✕"); close_btn.setFixedSize(28, 28); close_btn.setFlat(True)
            close_btn.setStyleSheet(f"QPushButton {{ font-size:14px; color:{'#AAA' if dark else '#888'}; border:none; background:transparent; }} QPushButton:hover {{ background:{'#444' if dark else '#F0F0F0'}; border-radius:4px; }}")
            close_btn.clicked.connect(picker.reject); t_bl.addWidget(close_btn)
            ov.addWidget(tb)
            # 列表
            lw = QtWidgets.QListWidget()
            lw.setStyleSheet(f"QListWidget {{ border:none; font-size:13px; background:{outer_bg}; }} QListWidget::item {{ padding:8px 14px; }} QListWidget::item:selected {{ background:{'#3D3D3D' if dark else '#E8F0FE'}; color:{'#EEE' if dark else '#333'}; border-radius:6px; }} QListWidget::item:hover {{ background:{'#3D3D3D' if dark else '#F5F8FC'}; border-radius:6px; }}")
            ov.addWidget(lw)
            inner = QtWidgets.QWidget(); iv = QtWidgets.QVBoxLayout(inner); iv.setContentsMargins(10, 8, 10, 10)
            ov.addWidget(inner)
        else:
            inner = picker; iv = QtWidgets.QVBoxLayout(inner)
            iv.setContentsMargins(14, 14, 14, 14)
            lw = QtWidgets.QListWidget()
            lw.setStyleSheet("QListWidget {{ border:1px solid #DEDEDE; border-radius:8px; font-size:13px; }} QListWidget::item {{ padding:8px 14px; border-bottom:1px solid #F0F0F0; }}")
            iv.addWidget(lw)
        if results:
            for lat, lon, dname, province, nation, context in results:
                # 上下文展示：省 / 国（或用完整层级）
                region_str = context if context else (" / ".join(p for p in (province, nation) if p))
                display = f"{dname} — {region_str}" if region_str else dname
                item = QtWidgets.QListWidgetItem(display)
                item.setData(QtCore.Qt.UserRole, (lat, lon, dname))
                item.setToolTip(f"{region_str}\n经纬度: {lat:.4f}, {lon:.4f}" if region_str else f"经纬度: {lat:.4f}, {lon:.4f}")
                lw.addItem(item)
            lw.setCurrentRow(0)
        else:
            # 空结果提示
            empty_item = QtWidgets.QListWidgetItem("没有匹配结果，请尝试更具体的名称（如 广州天河 或 北京朝阳）")
            empty_item.setFlags(QtCore.Qt.NoItemFlags)
            empty_item.setForeground(QtGui.QColor("#999"))
            lw.addItem(empty_item)
        # 按钮
        btns = QtWidgets.QWidget(); bl = QtWidgets.QHBoxLayout(btns)
        bl.addStretch()
        bl.addWidget(QtWidgets.QPushButton("取消", clicked=picker.reject))
        if results:
            def _confirm():
                item = lw.currentItem()
                if item and item.flags() & QtCore.Qt.ItemIsSelectable:
                    lat, lon, dname = item.data(QtCore.Qt.UserRole)
                    _apply_picked(lat, lon, dname)
                    picker.accept()
            ok_btn = QtWidgets.QPushButton("✓ 确定")
            ok_btn.setStyleSheet("QPushButton { background:#2F80ED; color:white; border:none; border-radius:6px; padding:6px 18px; font-weight:bold; } QPushButton:hover { background:#1A6FD8; }")
            ok_btn.clicked.connect(_confirm); bl.addWidget(ok_btn)
            # 双击也确认
            lw.itemDoubleClicked.connect(_confirm)
        iv.addWidget(btns)
        if sys.platform == "win32":
            full = QtWidgets.QVBoxLayout(picker); full.setContentsMargins(0, 0, 0, 0); full.addWidget(outer)
        # 按最长文字自适应宽度
        fm_title = QtGui.QFontMetrics(lbl(title_text, bold=True, size=11).font())
        fm_item = lw.fontMetrics()
        max_w = fm_title.horizontalAdvance(title_text) + 90  # 图标+关闭按钮+边距
        for i in range(lw.count()):
            w = fm_item.horizontalAdvance(lw.item(i).text()) + 50  # 列表项内边距
            if w > max_w: max_w = w
        max_w = max(min(max_w, 600), 280)
        picker.resize(max_w, picker.height())
        picker.exec()
    search_btn.clicked.connect(do_search); srl.addWidget(search_btn)
    c2l.addWidget(sr)
    swl.addWidget(card2)

    # ── 3. 天气 API ──
    card3, c3l = _make_card(os.path.join(icons_dir, "weather", "cloudy_blue.svg"), "天气 API")

    pr = QtWidgets.QWidget(); prl = QtWidgets.QHBoxLayout(pr); prl.setContentsMargins(0, 0, 0, 0)
    prl.addStretch()
    prl.addWidget(QtWidgets.QLabel("数据源:"))
    provider_cb = QtWidgets.QComboBox()
    provider_cb.addItems(["百度天气", "和风天气"])
    provider_cb.setCurrentText("百度天气" if _cfg.config.get("weather_provider", "baidu") == "baidu" else "和风天气")
    provider_cb.setMinimumWidth(140); provider_cb.setMaximumWidth(140)
    provider_cb.setStyleSheet("QComboBox { selection-background-color: #2F80ED; selection-color: white; }")
    provider_cb.setEditable(True); provider_cb.lineEdit().setAlignment(QtCore.Qt.AlignCenter); provider_cb.lineEdit().setReadOnly(True)
    prl.addWidget(provider_cb); prl.addStretch(); c3l.addWidget(pr)

    bd_frame = QtWidgets.QWidget(); bdl = QtWidgets.QVBoxLayout(bd_frame); bdl.setContentsMargins(0, 0, 0, 0)
    bd_entry = QtWidgets.QLineEdit(_cfg.config.get("baidu_key", ""))
    bd_entry.setPlaceholderText("百度 API Key"); bd_entry.setEchoMode(QtWidgets.QLineEdit.Password)
    bdl.addWidget(bd_entry); bdl.addWidget(lbl("每天 5,000 次调用", color="gray"), alignment=QtCore.Qt.AlignCenter); c3l.addWidget(bd_frame)

    qw_frame = QtWidgets.QWidget(); qwl = QtWidgets.QVBoxLayout(qw_frame); qwl.setContentsMargins(0, 0, 0, 0)
    qw_key = QtWidgets.QLineEdit(_cfg.QW_KEY)
    qw_key.setPlaceholderText("和风 API Key"); qw_key.setEchoMode(QtWidgets.QLineEdit.Password); qwl.addWidget(qw_key)
    qw_host = QtWidgets.QLineEdit(_cfg.QW_HOST)
    qw_host.setPlaceholderText("https://xxx.re.qweatherapi.com"); qwl.addWidget(qw_host)
    qwl.addWidget(lbl("免费订阅需填入个人 Host 地址", color="gray"), alignment=QtCore.Qt.AlignCenter); c3l.addWidget(qw_frame)

    if "和风" in provider_cb.currentText(): bd_frame.hide()
    else: qw_frame.hide()
    def on_provider_change(txt):
        if "和风" in txt: bd_frame.hide(); qw_frame.show()
        else: qw_frame.hide(); bd_frame.show()
    provider_cb.currentTextChanged.connect(on_provider_change)
    swl.addWidget(card3)

    # ── 保存 ──
    def save():
        _cfg.config["weather_provider"] = "qweather" if "和风" in provider_cb.currentText() else "baidu"
        _cfg.config["baidu_key"] = bd_entry.text().strip()
        _cfg.config["api_key"] = qw_key.text().strip()
        _cfg.config["qw_host"] = qw_host.text().strip()
        _cfg.config.pop("qweather_key", None)
        _cfg.config.pop("qweather_host", None)
        raw_brand = brand_cb.currentText()
        if raw_brand.startswith("🛠 "):
            raw_brand = raw_brand[2:]  # "🛠 " = 2 chars
        _cfg.config["brand"] = raw_brand
        _cfg.config["appearance_mode"] = {v: k for k, v in mode_map.items()}.get(theme_cb.currentText(), "system")
        if hasattr(dl, "_picked_loc"):
            _cfg.config["location"] = dl._picked_loc
        save_config(_cfg.config); apply_config()
        app._ctrl_title.setText(f"{raw_brand}空调控制")
        from .ac_tab import update_brand_logo; update_brand_logo(app)
        app._wx_title.setText("当前天气")
        app._update_alert_source()
        # 重新获取天气（无论是否切换位置/源）
        app._fetch_weather_all()
        write_log("系统", "设置已更新")
        dlg.accept()

    btns = QtWidgets.QWidget(); bl = QtWidgets.QHBoxLayout(btns)
    bl.addStretch()
    cancel_btn = QtWidgets.QPushButton("取消")
    cancel_btn.setFixedSize(100, 30)
    cancel_btn.setObjectName("settings_cancel_btn")
    cancel_btn.setCursor(QtCore.Qt.PointingHandCursor)
    cancel_btn.setStyleSheet("QPushButton#settings_cancel_btn { background:white; color:#333; border:1px solid #DEDEDE; border-radius:8px; font-size:13px; } QPushButton#settings_cancel_btn:hover { background:#F5F5F5; }")
    cancel_btn.clicked.connect(lambda: dlg.close())
    bl.addWidget(cancel_btn)
    save_btn = QtWidgets.QPushButton()
    save_btn.setObjectName("settings_save_btn")
    save_btn.setIcon(QtGui.QIcon(os.path.join(icons_dir, "save_white.svg")))
    save_btn.setText("保存")
    save_btn.setIconSize(QtCore.QSize(16, 16))
    save_btn.setFixedSize(100, 30)
    save_btn.setCursor(QtCore.Qt.PointingHandCursor)
    save_btn.setStyleSheet("QPushButton#settings_save_btn { background:#0076D4; color:white; border:1px solid #0076D4; border-radius:8px; font-size:13px; font-weight:500; } QPushButton#settings_save_btn:hover { background:#0065B8; }")
    save_btn.clicked.connect(save); bl.addWidget(save_btn)
    layout.addWidget(btns)

    # 初始化深色/浅色适配（必须在所有 widget 创建之后）
    from ._utils import is_dark
    _refresh_settings_theme(is_dark())

    import threading; dlg.exec()


# ── 故障诊断 ──
def open_repair(app):
    dlg = QtWidgets.QDialog(app)
    dlg.setWindowTitle("故障诊断")
    dlg.resize(430, 520)
    dlg.setWindowModality(QtCore.Qt.WindowModal)
    layout = QtWidgets.QVBoxLayout(dlg)

    layout.addWidget(lbl("故障诊断", bold=True, size=16), alignment=QtCore.Qt.AlignCenter)
    layout.addWidget(lbl("检测运行环境、设备连接和网络状态", color="gray", size=11), alignment=QtCore.Qt.AlignCenter)
    layout.addSpacing(8)

    diag_text = QtWidgets.QTextEdit(); diag_text.setReadOnly(True)
    diag_text.setStyleSheet("QTextEdit { font-family: 'Consolas', 'HarmonyOS Sans SC', monospace; font-size: 12px; border: 1px solid #DEDEDE; border-radius: 6px; }")
    layout.addWidget(diag_text)

    btns = QtWidgets.QWidget(); bl = QtWidgets.QHBoxLayout(btns)
    bl.addStretch()
    bl.addWidget(QtWidgets.QPushButton("关闭", clicked=dlg.reject))
    diag_btn = QtWidgets.QPushButton("开始诊断")
    diag_btn.setObjectName("primary")
    bl.addWidget(diag_btn)
    bl.addStretch()
    layout.addWidget(btns)

    def _render(lines):
        """主线程渲染"""
        diag_text.clear()
        for text, color in lines:
            diag_text.append(f'<span style="color:{color};">{text}</span>')
        diag_btn.setEnabled(True); diag_btn.setText("🔄 重新诊断")

    def _do_diag():
        """工作线程：收集所有行，最后一次性投递主线程"""
        def push(result, text, color="#333"):
            result.append((text, color))

        lines = []
        import socket, platform

        # ── Python 环境 ──
        push(lines, "┌─ Python 环境 ───────────", "#888")
        push(lines, f"│ ✅ Python {sys.version.split()[0]}", "#27AE60")
        push(lines, f"│    {sys.executable}", "#888")
        push(lines, "└────────────────────────", "#888")
        push(lines, "")

        # ── 依赖 ──
        push(lines, "┌─ 核心依赖 ─────────────", "#888")
        for mod_name in ["broadlink", "PIL", "schedule"]:
            try:
                mod = __import__(mod_name)
                ver = getattr(mod, "__version__", "OK")
                push(lines, f"│ ✅ {mod_name} {ver}", "#27AE60")
            except Exception:
                push(lines, f"│ ❌ {mod_name} 未安装  → pip install {mod_name}", "#E74C3C")
        push(lines, "└────────────────────────", "#888")
        push(lines, "")

        # ── 设备扫描 ──
        push(lines, "┌─ 博联设备扫描 ─────────", "#888")
        push(lines, "│ 🔍 扫描局域网中...", "#E67E22")
        from broadlinkac_core.ac_control import discover_devices
        from broadlinkac_core.config import get_current_device, add_or_update_device, save_config
        old_dev = get_current_device()
        old_ip = old_dev.get("host") if old_dev else None
        try:
            devices = discover_devices(timeout=5)
            if devices:
                d = devices[0]; new_ip = d.host[0] if isinstance(d.host, tuple) else str(d.host)
                ip_changed = old_ip and new_ip != old_ip
                push(lines, f"│ ✅ {d.model} ({getattr(d, 'name', '')})", "#27AE60")
                push(lines, f"│    IP:   {new_ip}", "#AAA")
                mac_hex = d.mac.hex() if isinstance(d.mac, bytes) else str(d.mac)
                push(lines, f"│    MAC:  {mac_hex}", "#AAA")
                if ip_changed:
                    push(lines, f"│    ⚠ IP 已变更: {old_ip} → {new_ip}", "#E67E22")
                try:
                    d.auth()
                    push(lines, "│    🔐 认证: ✅ 通过", "#27AE60")
                    add_or_update_device(mac_hex, {"host": new_ip, "port": d.host[1] if isinstance(d.host, tuple) else 80, "mac": mac_hex, "model": d.model, "name": getattr(d, "name", d.model)})
                    save_config(_cfg.config)
                    if ip_changed: push(lines, "│    📝 缓存已更新", "#27AE60")
                except Exception as ae:
                    push(lines, f"│    🔐 认证: ❌ {ae}", "#E74C3C")
            else:
                push(lines, "│ ❌ 未发现设备", "#E74C3C")
                push(lines, "│    → 确保设备与电脑在同一局域网", "#E67E22")
                push(lines, "│    → 尝试重启博联设备后重新扫描", "#E67E22")
        except Exception as de:
            push(lines, f"│ ❌ 扫描异常: {de}", "#E74C3C")
        push(lines, "└────────────────────────", "#888")
        push(lines, "")

        # ── 网络诊断 ──
        def _ping_ok(host):
            param = "-n" if platform.system() == "Windows" else "-c"
            try:
                r = subprocess.run(["ping", param, "2", host], capture_output=True, text=True, timeout=5)
                return r.returncode == 0
            except Exception: return False

        def _http_ok():
            """HTTP 联网检测（打包后无系统证书链，需跳过 SSL 验证）"""
            import ssl
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request("https://www.baidu.com", headers={"User-Agent": "BroadlinkAC/5.0"})
                urllib.request.urlopen(req, timeout=5, context=ctx)
                return True
            except Exception:
                return False

        push(lines, "┌─ 网络诊断 ─────────────", "#888")
        if _http_ok():
            # 通过真实路由获取本机 IP（gethostbyname 在 macOS 常返回 127.0.0.1）
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
            except Exception:
                local_ip = "未知"
            push(lines, f"│ 📶 本机 IP: {local_ip}", "#AAA")
            gateway = ".".join(local_ip.split(".")[:3] + ["1"]) if local_ip != "未知" else None
            if gateway and not _ping_ok(gateway):
                push(lines, f"│ ❌ 网关 {gateway} 不通", "#E74C3C")
                push(lines, "│    → 路由器连接有问题", "#E67E22")
            else:
                push(lines, f"│ ✅ 路由器 {gateway} 可达", "#27AE60")
                push(lines, "│ ✅ 外网可达", "#27AE60")
        else:
            push(lines, "│ ❌ 无法连接外网", "#E74C3C")
            push(lines, "│    → 请检查网线/WiFi", "#E67E22")
        push(lines, "└────────────────────────", "#888")
        push(lines, "")

        # ── 天气 API ──
        push(lines, "┌─ 和风天气 API ─────────", "#888")
        key = _cfg.QW_KEY; host = _cfg.QW_HOST
        if not key: push(lines, "│ ❌ API Key 未填写", "#E74C3C")
        else: push(lines, f"│ ✅ API Key: {key[:4]}...{key[-4:]}", "#27AE60")
        if host: push(lines, f"│    Host: {host}", "#AAA")
        try:
            if key and host:
                lon, lat = _cfg.LOCATION["lon"], _cfg.LOCATION["lat"]
                base = host.replace("https://", "").replace("http://", "").rstrip("/")
                url = f"https://{base}/v7/weather/now?location={lon},{lat}&key={key}"
                import ssl, gzip
                ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(url, headers={"User-Agent": "BroadlinkAC/2.0"})
                resp = urllib.request.urlopen(req, timeout=6, context=ctx)
                raw = resp.read()
                data = json.loads(gzip.decompress(raw))
                if data.get("code") == "200":
                    push(lines, "│ ✅ API 请求成功", "#27AE60")
                else:
                    push(lines, f"│ ⚠ {data.get('code')}", "#E67E22")
        except Exception as we:
            push(lines, f"│ ❌ API 请求失败: {we}", "#E74C3C")
        push(lines, "└────────────────────────", "#888")

        # ── 百度天气 API ──
        push(lines, "┌─ 百度天气 API ─────────", "#888")
        bd_key = _cfg.config.get("baidu_key", "")
        if not bd_key:
            push(lines, "│ ❌ API Key 未填写", "#E74C3C")
        else:
            push(lines, f"│ ✅ API Key: {bd_key[:4]}...{bd_key[-4:]}", "#27AE60")
            try:
                lon, lat = _cfg.LOCATION["lon"], _cfg.LOCATION["lat"]
                url = f"https://api.map.baidu.com/weather/v1/?location={lon},{lat}&coordtype=wgs84&data_type=now&ak={bd_key}"
                req = urllib.request.Request(url, headers={"User-Agent": "BroadlinkAC/2.0"})
                import ssl
                ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
                resp = urllib.request.urlopen(req, timeout=6, context=ctx)
                data = json.loads(resp.read())
                if data.get("status") == 0:
                    push(lines, "│ ✅ API 请求成功", "#27AE60")
                else:
                    push(lines, f"│ ⚠ {data.get('message', data)}", "#E67E22")
            except Exception as we:
                push(lines, f"│ ❌ API 请求失败: {we}", "#E74C3C")
        push(lines, "└────────────────────────", "#888")
        push(lines, "")

        # 如果有失败项，提示查看使用文档
        has_failure = any("❌" in text for text, color in lines)
        if has_failure:
            push(lines, "─" * 26, "#888")
            push(lines, "💡 遇到 ❌ 怎么办？", "#2F80ED")
            push(lines, "   打开菜单栏 帮助 → 使用文档", "#AAA")
            push(lines, "   里面有每一项问题的详细解决方法", "#AAA")
            push(lines, "─" * 26, "#888")

        # 一次性投递到主线程渲染
        app._ui(lambda: _render(lines))

    def _start_diag():
        """主线程：设置按钮状态，启动工作线程"""
        diag_btn.setEnabled(False); diag_btn.setText("诊断中...")
        diag_text.clear()
        threading.Thread(target=_do_diag, daemon=True).start()

    diag_btn.clicked.connect(_start_diag)
    dlg.exec()


# ── 关于 BroadlinkAC ──
def open_about(parent):
    dlg = _make_dialog(parent, "关于 BroadlinkAC", 440, 360, frameless=True)
    layout, swl = _dialog_content(dlg, frameless=True)

    layout.addStretch()
    layout.addWidget(lbl("BroadlinkAC v5.0", bold=True, size=18), alignment=QtCore.Qt.AlignCenter)
    layout.addSpacing(10)
    layout.addWidget(lbl("智能空调控制系统", size=13), alignment=QtCore.Qt.AlignCenter)
    layout.addWidget(lbl("支持 Broadlink RM 系列红外设备", color="#666", size=11), alignment=QtCore.Qt.AlignCenter)
    layout.addSpacing(12)
    layout.addWidget(lbl("十余种空调品牌遥控 | 室外温度实时监测", color="#555", size=11), alignment=QtCore.Qt.AlignCenter)
    layout.addWidget(lbl("台风路径预报与预警 | 多时段定时开关 | 智能温控", color="#555", size=11), alignment=QtCore.Qt.AlignCenter)
    layout.addSpacing(16)

    gh_url = "https://github.com/oywq00008-cell/BroadlinkAC-For-Agent"
    gh_link = QtWidgets.QLabel(f'<a href="{gh_url}" style="color:#2F80ED;">{gh_url}</a>')
    gh_link.setOpenExternalLinks(True)
    gh_link.setStyleSheet("font-size:10px;")
    layout.addWidget(gh_link, alignment=QtCore.Qt.AlignCenter)
    layout.addSpacing(16)

    layout.addWidget(lbl("by 欧阳小白", color="gray", size=10), alignment=QtCore.Qt.AlignCenter)
    layout.addStretch()
    btn = QtWidgets.QPushButton("确定")
    btn.clicked.connect(dlg.accept)
    layout.addWidget(btn, alignment=QtCore.Qt.AlignCenter)
    dlg.exec()


# ── 日志对话框 ──
def open_log_dialog(app):
    dates = get_log_dates()
    if not dates:
        QtWidgets.QMessageBox.information(app, "日志", "暂无日志记录。"); return

    dlg = _make_dialog(app, "日志查看", 350, 400, frameless=True)
    layout, swl = _dialog_content(dlg, frameless=True)

    swl.addWidget(lbl("选择日期查看日志", bold=True, size=14), alignment=QtCore.Qt.AlignCenter)
    lw = QtWidgets.QListWidget()
    lw.setStyleSheet("QListWidget { font-size:14px; } QListWidget::item { padding:6px; }")
    for d in sorted(dates, reverse=True):
        item = QtWidgets.QListWidgetItem(d)
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        lw.addItem(item)
    swl.addWidget(lw)
    btns = QtWidgets.QWidget(); bl = QtWidgets.QHBoxLayout(btns)
    bl.addStretch()
    bl.addWidget(QtWidgets.QPushButton("取消", clicked=dlg.reject))
    def open_log():
        item = lw.currentItem()
        if not item: return
        log_path = LOG_DIR / f"{item.text()}.md"
        if os.name == "nt": os.startfile(str(log_path))
        else: subprocess.run(["open", str(log_path)])
        dlg.accept()
    bl.addWidget(QtWidgets.QPushButton("打开", clicked=open_log))
    bl.addStretch()
    layout.addWidget(btns); dlg.exec()


# ── 设备重命名 ──
def open_rename_device(parent, old_name, mac):
    dlg = _make_dialog(parent, "修改设备名称", 400, 180, frameless=True)
    layout, swl = _dialog_content(dlg, frameless=True)

    swl.addWidget(lbl(f"设备: {old_name}  ({mac})", size=11, color="gray"))
    entry = QtWidgets.QLineEdit(old_name)
    entry.selectAll()
    swl.addWidget(entry)
    swl.addStretch()
    btns = QtWidgets.QWidget(); bl = QtWidgets.QHBoxLayout(btns)
    bl.addStretch()
    result = [None]
    def confirm():
        t = entry.text().strip()
        if t and t != old_name:
            result[0] = t
            dlg.accept()
        else:
            dlg.reject()
    bl.addWidget(QtWidgets.QPushButton("取消", clicked=dlg.reject))
    bl.addWidget(QtWidgets.QPushButton("确认", clicked=confirm))
    layout.addWidget(btns)
    dlg.exec()
    return result[0]


# ── 设备删除确认 ──
def open_delete_device(parent, name=None, allow=True):
    dlg = _make_dialog(parent, "删除设备", 380, 160, frameless=True)
    layout, swl = _dialog_content(dlg, frameless=True)

    if allow:
        swl.addWidget(lbl(f"确定要删除「{name}」吗？此操作不可撤销。", size=13))
    else:
        swl.addWidget(lbl("无法删除：至少需要保留一台设备。", size=13, color="#E74C3C"))
    swl.addStretch()
    btns = QtWidgets.QWidget(); bl = QtWidgets.QHBoxLayout(btns)
    bl.addStretch()
    result = [False]
    if allow:
        def do_delete(): result[0] = True; dlg.accept()
        bl.addWidget(QtWidgets.QPushButton("取消", clicked=dlg.reject))
        btn = QtWidgets.QPushButton("确认删除")
        btn.setStyleSheet("QPushButton { color: #E74C3C; font-weight: bold; }")
        btn.clicked.connect(do_delete); bl.addWidget(btn)
    else:
        bl.addWidget(QtWidgets.QPushButton("知道了", clicked=dlg.reject))
    layout.addWidget(btns)
    dlg.exec()
    return result[0]


# ── 定时模板编辑 ──
_WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _schedule_summary(app):
    """返回当前模板的摘要数据，支持多日期组
    返回: {"name": str, "groups": [{"days_str": str, "times": [str, ...]}, ...]}，错误时含 "error" 键
    """
    mac = _cfg.config.get("current_device_mac", "")
    dev = _cfg.config.get("devices", {}).get(mac, {})
    tmpl_name = dev.get("active_template")
    enabled = dev.get("schedule_enabled", True)
    if not enabled or not tmpl_name:
        return {"name": "", "groups": [], "error": "定时任务未开启"}
    tmpl = (_cfg.config.get("schedule_templates", {}) or {}).get(tmpl_name)
    if not tmpl:
        return {"name": "", "groups": [], "error": "模板不存在"}
    groups = tmpl.get("groups", [])
    if not groups:
        days = tmpl.get("days", [])
        slots = tmpl.get("slots", [])
        if not days or not slots:
            return {"name": tmpl_name, "groups": [], "error": "无有效设置"}
        groups = [{"days": days, "slots": slots}]
    result = {"name": tmpl_name, "groups": []}
    for grp in groups:
        days = grp.get("days", [])
        slots = grp.get("slots", [])
        if not days or not slots:
            continue
        day_names = "、".join(_WEEKDAYS[d-1] for d in sorted(days))
        times = []
        for s in slots:
            parts = []
            if s.get("on_enabled", True): parts.append(f"{s['on']}开机")
            if s.get("off_enabled", True) and s.get("off"): parts.append(f"{s['off']}关机")
            if parts: times.append(" → ".join(parts))
        result["groups"].append({"days_str": day_names, "times": times})
    return result


def open_schedule_template(app):
    """定时模板编辑弹窗 — 支持多日期组"""
    mac = _cfg.config.get("current_device_mac", "")
    dev = _cfg.config.setdefault("devices", {}).setdefault(mac, {})
    templates = _cfg.config.setdefault("schedule_templates", {})
    if not templates:
        templates["默认"] = {"groups": [{"days": [1,2,3,4,5], "slots": []}]}
    active = dev.get("active_template", list(templates.keys())[0] if templates else "")

    dlg = _make_dialog(app, "定时模板编辑", 460, 520, frameless=True)
    layout, swl = _dialog_content(dlg, frameless=True)
    swl.setSpacing(8)

    # ── 模板选择行 ──
    tr = QtWidgets.QWidget()
    trl = QtWidgets.QHBoxLayout(tr); trl.setContentsMargins(0, 0, 0, 0); trl.setSpacing(6)
    trl.addWidget(QtWidgets.QLabel("模板:"))
    tmpl_cb = QtWidgets.QComboBox()
    tmpl_cb.setMinimumWidth(140)
    def _refresh_tmpl_list():
        current = tmpl_cb.currentText()
        tmpl_cb.clear()
        tmpl_cb.addItems(list(templates.keys()))
        if current in templates: tmpl_cb.setCurrentText(current)
    _refresh_tmpl_list()
    trl.addWidget(tmpl_cb)
    trl.addStretch()
    def _add_tmpl():
        name, ok = QtWidgets.QInputDialog.getText(dlg, "新增模板", "模板名称:")
        if ok and name.strip() and name.strip() not in templates:
            templates[name.strip()] = {"groups": [{"days": [1,2,3,4,5], "slots": []}]}
            _refresh_tmpl_list()
            tmpl_cb.setCurrentText(name.strip())
            _rebuild_all()
            write_log("定时", f"新增模板: {name.strip()}")
    btn = QtWidgets.QPushButton("＋"); btn.setFixedSize(30, 26)
    btn.setToolTip("新增模板")
    btn.clicked.connect(_add_tmpl); trl.addWidget(btn)

    def _rename_tmpl():
        old = tmpl_cb.currentText()
        if not old: return
        name, ok = QtWidgets.QInputDialog.getText(dlg, "重命名模板", "新名称:", text=old)
        if ok and name.strip() and name.strip() != old and name.strip() not in templates:
            templates[name.strip()] = templates.pop(old)
            for d in _cfg.config.get("devices", {}).values():
                if d.get("active_template") == old:
                    d["active_template"] = name.strip()
            _refresh_tmpl_list(); tmpl_cb.setCurrentText(name.strip())
            write_log("定时", f"模板重命名: {old} → {name.strip()}")
    btn = QtWidgets.QPushButton("✎"); btn.setFixedSize(30, 26)
    btn.setToolTip("重命名模板")
    btn.clicked.connect(_rename_tmpl); trl.addWidget(btn)

    def _del_tmpl():
        name = tmpl_cb.currentText()
        if not name or len(templates) <= 1:
            QtWidgets.QMessageBox.warning(dlg, "无法删除", "至少保留一个模板")
            return
        if QtWidgets.QMessageBox.question(dlg, "删除", f"确定删除「{name}」？") != QtWidgets.QMessageBox.Yes:
            return
        del templates[name]
        for dmac, d in _cfg.config.get("devices", {}).items():
            if d.get("active_template") == name:
                if dmac == mac:
                    d.pop("active_template", None)
                else:
                    d.pop("active_template", None)
                    d["schedule_enabled"] = False
        _refresh_tmpl_list(); _rebuild_all()
        write_log("定时", f"已删除模板: {name}")
    btn = QtWidgets.QPushButton("🗑"); btn.setFixedSize(30, 26)
    btn.setToolTip("删除模板")
    btn.clicked.connect(_del_tmpl); trl.addWidget(btn)
    swl.addWidget(tr)

    # ── 日期组区域（可滚动）──
    _HOURS = [f"{h:02d}" for h in range(24)]
    _MINS  = [f"{m:02d}" for m in range(0, 60, 5)]
    groups_widget = QtWidgets.QWidget()
    groups_layout = QtWidgets.QVBoxLayout(groups_widget)
    groups_layout.setContentsMargins(0, 0, 0, 0); groups_layout.setSpacing(10)

    def _add_group(days=None, slots=None):
        """添加一个日期组 → groups_layout"""
        grp_idx = groups_layout.count()
        days = days if isinstance(days, list) else [1,2,3,4,5]
        slots = slots if isinstance(slots, list) else []

        frame = QtWidgets.QFrame()
        frame.setStyleSheet("QFrame { background:#F8FAFC; border:1px solid #DEDEDE; border-radius:8px; }")
        fl = QtWidgets.QVBoxLayout(frame); fl.setContentsMargins(10, 8, 10, 8); fl.setSpacing(6)

        # 组标题
        header = QtWidgets.QWidget()
        hl = QtWidgets.QHBoxLayout(header); hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(lbl(f"日期组 {grp_idx + 1}", bold=True, size=11, color="#555"))
        hl.addStretch()
        del_btn = QtWidgets.QPushButton("✕ 删除此组")
        del_btn.setStyleSheet("QPushButton { border:none; color:#E74C3C; font-size:11px; } QPushButton:hover { text-decoration:underline; }")
        hl.addWidget(del_btn)
        fl.addWidget(header)

        # 星期勾选
        day_checks = []
        dw = QtWidgets.QWidget()
        dwl = QtWidgets.QHBoxLayout(dw); dwl.setContentsMargins(0, 0, 0, 0); dwl.setSpacing(2)
        for i, name in enumerate(_WEEKDAYS):
            cb = QtWidgets.QCheckBox(name)
            cb.setChecked((i+1) in days)
            dwl.addWidget(cb); day_checks.append(cb)
        dwl.addStretch()
        fl.addWidget(dw)

        # 时段区域
        slot_list = QtWidgets.QWidget()
        slot_layout = QtWidgets.QVBoxLayout(slot_list)
        slot_layout.setContentsMargins(4, 0, 4, 0); slot_layout.setSpacing(4)
        frame._slot_layout = slot_layout  # 供 _save 读取（Python 原生属性）

        def _rebuild_group_slots():
            sl = slots  # 直接使用闭包列表引用
            while slot_layout.count():
                w = slot_layout.takeAt(0).widget()
                if w: w.deleteLater()
            for si, slot in enumerate(sl):
                # 时段行
                row = QtWidgets.QWidget()
                rl = QtWidgets.QHBoxLayout(row); rl.setContentsMargins(0, 2, 0, 2); rl.setSpacing(4)
                on_chk = QtWidgets.QCheckBox("开机")
                on_chk.setChecked(slot.get("on_enabled", True))
                rl.addWidget(on_chk)
                on_h, on_m = slot["on"].split(":") if ":" in slot["on"] else ("08", "00")
                on_h_cb = QtWidgets.QComboBox(); on_h_cb.addItems(_HOURS); on_h_cb.setCurrentText(on_h); on_h_cb.setFixedWidth(50)
                rl.addWidget(on_h_cb)
                rl.addWidget(QtWidgets.QLabel(":"))
                on_m_cb = QtWidgets.QComboBox(); on_m_cb.addItems(_MINS); on_m_cb.setCurrentText(on_m); on_m_cb.setFixedWidth(50)
                rl.addWidget(on_m_cb)
                rl.addSpacing(12)
                off_chk = QtWidgets.QCheckBox("关机")
                off_chk.setChecked(slot.get("off_enabled", True) and bool(slot.get("off")))
                rl.addWidget(off_chk)
                off_h, off_m = (slot["off"].split(":") if slot.get("off") and ":" in slot["off"] else ("18", "00"))
                off_h_cb = QtWidgets.QComboBox(); off_h_cb.addItems(_HOURS); off_h_cb.setCurrentText(off_h); off_h_cb.setFixedWidth(50)
                rl.addWidget(off_h_cb)
                rl.addWidget(QtWidgets.QLabel(":"))
                off_m_cb = QtWidgets.QComboBox(); off_m_cb.addItems(_MINS); off_m_cb.setCurrentText(off_m); off_m_cb.setFixedWidth(50)
                rl.addWidget(off_m_cb)
                rl.addStretch()
                def _del_grp_slot():
                    # 通过 slot_layout 确认删除第几个
                    for j in range(slot_layout.count()):
                        if slot_layout.itemAt(j).widget() is row:
                            if 0 <= j < len(slots): del slots[j]
                            break
                    _rebuild_group_slots()
                del_s_btn = QtWidgets.QPushButton("×")
                del_s_btn.setFixedSize(22, 22)
                del_s_btn.setStyleSheet("QPushButton { border:1px solid #CCC; border-radius:3px; color:#999; } QPushButton:hover { background:#EEE; }")
                del_s_btn.clicked.connect(lambda checked=False: _del_grp_slot())
                rl.addWidget(del_s_btn)
                slot_layout.addWidget(row)
        _rebuild_group_slots()
        fl.addWidget(slot_list)

        # 添加时段按钮
        add_s_btn = QtWidgets.QPushButton("+ 添加时段")
        add_s_btn.setStyleSheet("QPushButton { border:1px dashed #CCC; border-radius:4px; color:#888; background:transparent; padding:2px; } QPushButton:hover { border-color:#2F80ED; color:#2F80ED; }")
        def _add_grp_slot_clicked():
            slots.append({"on": "08:00", "on_enabled": True, "off": "18:00", "off_enabled": True})
            _rebuild_group_slots()
        add_s_btn.clicked.connect(_add_grp_slot_clicked)
        fl.addWidget(add_s_btn)

        # 删除组
        def _del_group(w=frame):
            w.hide()
            groups_layout.removeWidget(w)
            w.setParent(None)
        del_btn.clicked.connect(lambda checked=False, w=frame: _del_group(w))

        groups_layout.addWidget(frame)

    def _rebuild_all():
        while groups_layout.count():
            w = groups_layout.takeAt(0).widget()
            if w: w.deleteLater()
        name = tmpl_cb.currentText()
        tmpl = templates.get(name, {})
        groups = tmpl.get("groups", [])
        if not groups and tmpl.get("days"):
            groups = [{"days": tmpl.get("days", []), "slots": tmpl.get("slots", [])}]
        for grp in groups:
            _add_group(days=grp.get("days", [1,2,3,4,5]), slots=grp.get("slots", []))
        if not groups:
            _add_group()

    swl.addWidget(groups_widget)

    # ── 添加日期组按钮 ──
    add_grp_btn = QtWidgets.QPushButton("+ 添加日期组")
    add_grp_btn.clicked.connect(lambda: _add_group())
    swl.addWidget(add_grp_btn, alignment=QtCore.Qt.AlignCenter)
    swl.addSpacing(8)

    tmpl_cb.currentTextChanged.connect(lambda t: _rebuild_all())
    if active and active in templates:
        tmpl_cb.setCurrentText(active)
    _rebuild_all()

    swl.addStretch()

    # ── 保存 / 取消 ──
    btns = QtWidgets.QWidget(); bl = QtWidgets.QHBoxLayout(btns)
    bl.addStretch()
    bl.addWidget(QtWidgets.QPushButton("取消", clicked=dlg.reject))
    def _save():
        name = tmpl_cb.currentText()
        if not name: return
        groups_data = []
        for i in range(groups_layout.count()):
            frame = groups_layout.itemAt(i).widget()
            if not isinstance(frame, QtWidgets.QFrame): continue
            # 收集星期
            day_checks = [w for w in frame.findChildren(QtWidgets.QCheckBox) if w.text() in _WEEKDAYS]
            days = [j+1 for j, cb in enumerate(day_checks) if cb.isChecked()]
            # 收集时段（从 slot_layout 属性直接读取）
            s_layout = getattr(frame, "_slot_layout", None)
            slots_data = []
            if s_layout:
                for si in range(s_layout.count()):
                    row = s_layout.itemAt(si).widget()
                    if not row: continue
                    chks = row.findChildren(QtWidgets.QCheckBox)
                    cbs = row.findChildren(QtWidgets.QComboBox)
                    if len(chks) >= 2 and len(cbs) >= 4:
                        on_t = f"{cbs[0].currentText()}:{cbs[1].currentText()}"
                        off_t = f"{cbs[2].currentText()}:{cbs[3].currentText()}"
                        slots_data.append({
                            "on": on_t, "on_enabled": chks[0].isChecked(),
                            "off": off_t, "off_enabled": chks[1].isChecked(),
                        })
            if days and slots_data:
                groups_data.append({"days": sorted(days), "slots": sorted(slots_data, key=lambda s: s["on"])})
        if not groups_data:
            QtWidgets.QMessageBox.warning(dlg, "提示", "请至少添加一个有效的日期组")
            return
        tmpl = templates.setdefault(name, {})
        tmpl["groups"] = groups_data
        tmpl.pop("days", None); tmpl.pop("slots", None)  # 清理旧字段
        dev["active_template"] = name
        dev["schedule_enabled"] = True
        _cfg.config["schedule_enabled"] = True
        save_config(_cfg.config)
        from broadlinkac_core.scheduler import register_all_jobs
        with __import__("broadlinkac_core.scheduler", fromlist=["_sched_lock"])._sched_lock:
            register_all_jobs()
        app._ui(lambda: app._update_schedule_display())
        write_log("定时", f"已保存模板: {name}")
        dlg.accept()
    bl.addWidget(QtWidgets.QPushButton("保存", clicked=_save))
    bl.addStretch()
    layout.addWidget(btns); dlg.exec()


# ── 规则编辑 ──
def edit_rules(app):
    from ._utils import is_dark
    dark = is_dark()
    bg = "#2D2D2D" if dark else "white"
    tc = "#EEE" if dark else "#333"
    ibg = "#3D3D3D" if dark else "white"
    ibd = "#555" if dark else "#DEDEDE"

    dlg = QtWidgets.QDialog(app); dlg.setWindowTitle("✏ 编辑温度规则"); dlg.resize(450, 400)
    dlg.setWindowModality(QtCore.Qt.WindowModal)
    dlg.setStyleSheet(f"QDialog {{ background:{bg}; }}")
    layout = QtWidgets.QVBoxLayout(dlg)
    scroll = QtWidgets.QScrollArea(); scroll.setWidgetResizable(True)
    scroll.setStyleSheet(f"QScrollArea {{ border:none; background:{bg}; }}")
    sw = QtWidgets.QWidget(); sw.setStyleSheet(f"background:{bg};"); swl = QtWidgets.QVBoxLayout(sw); scroll.setWidget(sw); layout.addWidget(scroll)
    entries = []
    for i, (low, high, target, mode) in enumerate(_cfg.config.get("temp_rules", [
        [36, 99, 24, "cool"], [33, 35, 25, "cool"], [30, 32, 26, "cool"],
        [25, 29, 27, "cool"], [18, 24, 0, "off"], [0, 17, 28, "heat"]
    ])):
        r = QtWidgets.QWidget(); rl = QtWidgets.QHBoxLayout(r); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(2)
        lb = QtWidgets.QLabel(f"规则{i + 1}："); lb.setStyleSheet(f"color:{tc}; font-size:13px;"); rl.addWidget(lb)
        lb_out = QtWidgets.QLabel("室外"); lb_out.setStyleSheet(f"color:{tc}; font-size:13px;"); rl.addWidget(lb_out)
        e1 = QtWidgets.QLineEdit(str(low)); e1.setFixedWidth(36); e1.setAlignment(QtCore.Qt.AlignCenter)
        e1.setStyleSheet(f"color:{tc}; background:{ibg}; border:1px solid {ibd}; border-radius:4px; font-size:13px;"); rl.addWidget(e1)
        lb_tilde = QtWidgets.QLabel("~"); lb_tilde.setFixedWidth(14); lb_tilde.setAlignment(QtCore.Qt.AlignCenter)
        lb_tilde.setStyleSheet(f"color:{tc}; font-size:13px;"); rl.addWidget(lb_tilde)
        e2 = QtWidgets.QLineEdit(str(high)); e2.setFixedWidth(36); e2.setAlignment(QtCore.Qt.AlignCenter)
        e2.setStyleSheet(f"color:{tc}; background:{ibg}; border:1px solid {ibd}; border-radius:4px; font-size:13px;"); rl.addWidget(e2)
        lb_c = QtWidgets.QLabel("℃"); lb_c.setStyleSheet(f"color:{tc}; font-size:13px;"); rl.addWidget(lb_c)
        lb_arr = QtWidgets.QLabel("→"); lb_arr.setStyleSheet(f"color:{tc}; font-size:13px;"); rl.addWidget(lb_arr)
        cb = QtWidgets.QComboBox(); cb.addItems(list(MODES.keys()))
        cb.setCurrentText(MODE_KEYS.get(mode, "制冷")); cb.setFixedWidth(80)
        cb.setStyleSheet(f"QComboBox {{ color:{tc}; background:{ibg}; border:1px solid {ibd}; border-radius:4px; padding:2px 4px; font-size:13px; }} QComboBox QAbstractItemView {{ background:{ibg}; color:{tc}; selection-background-color:#2F80ED; font-size:13px; }}")
        rl.addWidget(cb)
        # 温度容器 — 永远占位，只隐藏/显示内容
        temp_holder = QtWidgets.QWidget()
        temp_holder.setFixedWidth(70)
        thl = QtWidgets.QHBoxLayout(temp_holder); thl.setContentsMargins(0, 0, 0, 0); thl.setSpacing(2)
        e3 = QtWidgets.QLineEdit(str(target)); e3.setFixedWidth(40); e3.setAlignment(QtCore.Qt.AlignCenter)
        e3.setStyleSheet(f"color:{tc}; background:{ibg}; border:1px solid {ibd}; border-radius:4px; font-size:13px;")
        thl.addWidget(e3)
        lb4 = QtWidgets.QLabel("°C"); lb4.setStyleSheet(f"color:{tc}; font-size:13px;")
        thl.addWidget(lb4)
        rl.addWidget(temp_holder)
        # 关闭模式隐藏温度内容（容器占位不变）
        def _make_toggle(_e3, _lb4):
            def _toggle_temp(txt):
                hide = txt == "关闭"
                _e3.setVisible(not hide)
                _lb4.setVisible(not hide)
            return _toggle_temp
        cb.currentTextChanged.connect(_make_toggle(e3, lb4))
        _make_toggle(e3, lb4)(cb.currentText())
        swl.addWidget(r)
        entries.append((e1, e2, cb, e3))

    btns = QtWidgets.QWidget(); bl = QtWidgets.QHBoxLayout(btns)
    b = QtWidgets.QPushButton("取消")
    b.setStyleSheet(f"QPushButton {{ background:{'#555' if dark else 'white'}; color:{'#DDD' if dark else '#333'}; border:1px solid {'#666' if dark else '#DEDEDE'}; border-radius:6px; padding:4px 14px; }} QPushButton:hover {{ background:{'#666' if dark else '#F5F5F5'}; }}")
    b.clicked.connect(dlg.reject); bl.addWidget(b)
    def save():
        rules = []
        for a, b, c, d in entries:
            try:
                mode_key = MODES[c.currentText()]
                target = 0 if mode_key == "off" else int(d.text())
                rules.append([int(a.text()), int(b.text()), target, mode_key])
            except: pass
        if not rules:
            return
        brand = _cfg.config.get("brand", "格力")
        if brand not in AC_BRANDS:
            from broadlinkac_core.ir_learner import get_raw_code
            missing = []
            for low, high, target, mode in rules:
                if target == 0:
                    if not get_raw_code(brand, "off", mode, target, "auto"):
                        missing.append("关机")
                else:
                    mode_ch = MODE_KEYS.get(mode, "制冷")
                    if not get_raw_code(brand, "on", mode, target, "auto"):
                        missing.append(f"{mode_ch} {target}°C 自动风")
            if missing:
                dups = list(dict.fromkeys(missing))
                msg = "规则中有自定义遥控器缺少的指令，\n定时或自动调温可能不工作：\n\n" + "\n".join(dups[:10])
                if len(dups) > 10:
                    msg += f"\n... 等 {len(dups)} 项"
                msg += "\n\n请先在设置中学习这些组合。\n仍然要保存当前规则吗？"
                mb = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, "指令缺失", msg, parent=dlg)
                save_btn = mb.addButton("保存", QtWidgets.QMessageBox.AcceptRole)
                mb.addButton("取消", QtWidgets.QMessageBox.RejectRole)
                mb.exec()
                if mb.clickedButton() != save_btn:
                    return
        _cfg.config["temp_rules"] = rules; save_config(_cfg.config); app._refresh_rules_display()
        write_log("系统", "已更新温度规则")
        dlg.accept()
    b = QtWidgets.QPushButton("💾 保存")
    b.setStyleSheet(f"QPushButton {{ background:{'#2F80ED' if dark else '#0076D4'}; color:white; border:none; border-radius:6px; padding:4px 14px; font-weight:500; }} QPushButton:hover {{ background:{'#1A6FD8' if dark else '#0065B8'}; }}")
    b.clicked.connect(save); bl.addWidget(b)
    layout.addWidget(btns); dlg.exec()


# ── 台风预警编辑 ──
def edit_ty_alert(app):
    dlg = QtWidgets.QDialog(app); dlg.setWindowTitle("修改预警设置"); dlg.resize(320, 130)
    dlg.setWindowModality(QtCore.Qt.WindowModal)
    layout = QtWidgets.QVBoxLayout(dlg)
    r = QtWidgets.QWidget(); rl = QtWidgets.QHBoxLayout(r)
    rl.addWidget(QtWidgets.QLabel("预警距离:"))
    entry = QtWidgets.QLineEdit(str(_cfg.config.get("typhoon_alert_km", 800)))
    entry.setFixedWidth(80); rl.addWidget(entry); rl.addWidget(QtWidgets.QLabel("km"))
    alert_sw = QtWidgets.QCheckBox("弹窗提醒")
    alert_sw.setChecked(_cfg.config.get("typhoon_alert_enabled", True)); rl.addWidget(alert_sw)
    rl.addStretch()
    layout.addWidget(r)
    btns = QtWidgets.QWidget(); bl = QtWidgets.QHBoxLayout(btns)
    def save():
        try: _cfg.config["typhoon_alert_km"] = int(entry.text())
        except: _cfg.config["typhoon_alert_km"] = 800
        _cfg.config["typhoon_alert_enabled"] = alert_sw.isChecked()
        save_config(_cfg.config); app._update_ty_status(); dlg.accept()
        write_log("台风", f"预警设置已更新: 距离={_cfg.config['typhoon_alert_km']}km, 提醒={'开' if _cfg.config['typhoon_alert_enabled'] else '关'}")
    b = QtWidgets.QPushButton("保存"); b.clicked.connect(save); bl.addWidget(b)
    b = QtWidgets.QPushButton("取消"); b.clicked.connect(dlg.reject); bl.addWidget(b)
    layout.addWidget(btns); dlg.exec()
