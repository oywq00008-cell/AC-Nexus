"""对话框模块：设置 / 诊断 / 日志 / 规则编辑 / 台风预警"""

import os, sys, subprocess, json, urllib.request, threading

from PySide6 import QtCore, QtGui, QtWidgets

import broadlinkac_core.config as _cfg
from broadlinkac_core.config import save_config, apply_config, AC_BRANDS, LOG_DIR
from broadlinkac_core.ac_control import MODES, MODE_KEYS
from broadlinkac_core.logger import get_log_dates
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
def open_settings(app):
    dlg = QtWidgets.QDialog(app, QtCore.Qt.FramelessWindowHint if sys.platform == "win32" else QtCore.Qt.Dialog)
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
        sw = QtWidgets.QWidget(); swl = QtWidgets.QVBoxLayout(sw); scroll.setWidget(sw); layout.addWidget(scroll)
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

    # ── 天气 API ──
    f1 = frm(); fl = QtWidgets.QVBoxLayout(f1); fl.setContentsMargins(10, 8, 10, 8)
    fl.addWidget(lbl("天气 API", bold=True, size=13), alignment=QtCore.Qt.AlignCenter)
    pr = QtWidgets.QWidget(); prl = QtWidgets.QHBoxLayout(pr); prl.setContentsMargins(0, 0, 0, 0)
    prl.addWidget(QtWidgets.QLabel("数据源:"))
    provider_cb = QtWidgets.QComboBox()
    provider_cb.addItems(["百度天气", "和风天气"])
    provider_cb.setCurrentText("百度天气" if _cfg.config.get("weather_provider", "baidu") == "baidu" else "和风天气")
    prl.addWidget(provider_cb); prl.addStretch(); fl.addWidget(pr)

    # 百度输入区
    bd_frame = QtWidgets.QWidget(); bdl = QtWidgets.QVBoxLayout(bd_frame); bdl.setContentsMargins(0, 0, 0, 0)
    bd_entry = QtWidgets.QLineEdit(_cfg.config.get("baidu_key", ""))
    bd_entry.setPlaceholderText("百度 API Key"); bd_entry.setEchoMode(QtWidgets.QLineEdit.Password)
    bdl.addWidget(bd_entry)
    bdl.addWidget(lbl("💡 每天 5,000 次调用", color="gray"))
    fl.addWidget(bd_frame)

    # 和风输入区
    qw_frame = QtWidgets.QWidget(); qwl = QtWidgets.QVBoxLayout(qw_frame); qwl.setContentsMargins(0, 0, 0, 0)
    qw_key = QtWidgets.QLineEdit(_cfg.QW_KEY)
    qw_key.setPlaceholderText("和风 API Key"); qw_key.setEchoMode(QtWidgets.QLineEdit.Password)
    qwl.addWidget(qw_key)
    qw_host = QtWidgets.QLineEdit(_cfg.QW_HOST)
    qw_host.setPlaceholderText("https://xxx.re.qweatherapi.com")
    qwl.addWidget(qw_host)
    qwl.addWidget(lbl("💡 免费订阅需填入个人 Host 地址", color="gray"))
    fl.addWidget(qw_frame)

    if "和风" in provider_cb.currentText():
        bd_frame.hide()
    else:
        qw_frame.hide()

    def on_provider_change(txt):
        if "和风" in txt:
            bd_frame.hide(); qw_frame.show()
        else:
            qw_frame.hide(); bd_frame.show()
    provider_cb.currentTextChanged.connect(on_provider_change)
    swl.addWidget(f1)

    # ── 基础设置 ──
    f2 = frm(); f2l = QtWidgets.QVBoxLayout(f2); f2l.setContentsMargins(10, 8, 10, 8)
    f2l.addWidget(lbl("基础设置", bold=True, size=13), alignment=QtCore.Qt.AlignCenter)

    # 主题
    r = QtWidgets.QWidget(); rl = QtWidgets.QHBoxLayout(r); rl.setContentsMargins(0, 0, 0, 0)
    rl.addWidget(QtWidgets.QLabel("主题:"))
    rl.addStretch(1)
    theme_cb = QtWidgets.QComboBox(); theme_cb.addItems(["跟随系统", "浅色", "深色"])
    theme_cb.setMinimumWidth(180); theme_cb.setMaximumWidth(180)
    theme_cb.setStyleSheet("QComboBox { selection-background-color: #2F80ED; selection-color: white; }")
    rl.addWidget(theme_cb); f2l.addWidget(r)
    mode_map = {"system": "跟随系统", "light": "浅色", "dark": "深色"}
    cur_mode = _cfg.config.get("appearance_mode", "system")
    theme_cb.setCurrentText(mode_map.get(cur_mode, "跟随系统"))
    def _refresh_settings_theme(dark):
        """刷新设置窗口自身的主题"""
        if sys.platform != "win32":
            return  # macOS/Linux 用原生窗口，不需要刷新
        outer.setStyleSheet(f"QFrame#settings_outer {{ background:{'#2D2D2D' if dark else 'white'}; border:1px solid {'#444' if dark else '#DEDEDE'}; border-radius:12px; }}")
        title_bar.setStyleSheet(f"background: transparent; border-bottom: 1px solid {'#444' if dark else '#E5E7EB'};")
        close_btn.setStyleSheet(f"QPushButton {{ font-size:14px; color:{'#AAA' if dark else '#888'}; border:none; background:transparent; }} QPushButton:hover {{ background:{'#444' if dark else '#F0F0F0'}; border-radius:4px; }}")
        scroll.setStyleSheet(f"QScrollArea {{ border:none; background:{'#2D2D2D' if dark else 'white'}; }}")
        sw.setStyleSheet(f"background: {'#2D2D2D' if dark else 'white'};")

    def on_theme_change(t):
        mode = {v: k for k, v in mode_map.items()}.get(t, "system")
        apply_theme(mode)
        d = mode == "dark" or (mode == "system" and _is_system_dark())
        _refresh_settings_theme(d)

    theme_cb.currentTextChanged.connect(on_theme_change)
    rl.addWidget(theme_cb); rl.addStretch(); f2l.addWidget(r)

    # 品牌
    r = QtWidgets.QWidget(); rl = QtWidgets.QHBoxLayout(r); rl.setContentsMargins(0, 0, 0, 0)
    rl.addWidget(QtWidgets.QLabel("空调品牌:"))
    rl.addStretch(1)
    brand_cb = QtWidgets.QComboBox(); brand_cb.addItems(list(AC_BRANDS.keys()))
    brand_cb.setCurrentText(_cfg.config.get("brand", "格力"))
    brand_cb.setMinimumWidth(180); brand_cb.setMaximumWidth(180)
    brand_cb.setStyleSheet("QComboBox { selection-background-color: #2F80ED; selection-color: white; }")
    rl.addWidget(brand_cb, alignment=QtCore.Qt.AlignRight); f2l.addWidget(r)
    swl.addWidget(f2)

    # ── 城市设置 ──
    f3 = frm(); f3l = QtWidgets.QVBoxLayout(f3); f3l.setContentsMargins(10, 8, 10, 8)
    f3l.addWidget(lbl("城市设置", bold=True, size=13), alignment=QtCore.Qt.AlignCenter)

    loc_info = QtWidgets.QLabel(
        f"当前: {_cfg.LOCATION['name']} ({_cfg.LOCATION['lat']}°N, {_cfg.LOCATION['lon']}°E)")
    loc_info.setStyleSheet("color:#27AE60;")
    f3l.addWidget(loc_info, alignment=QtCore.Qt.AlignCenter)

    dl = dlg  # capture reference

    def auto_locate():
        loc_info.setText("⏳ 定位中..."); loc_info.setStyleSheet("color:#E67E22;")
        try:
            resp = urllib.request.urlopen("http://ip-api.com/json/", timeout=5)
            data = json.loads(resp.read())
            if data.get("status") == "success":
                dl._picked_loc = {
                    "lat": data["lat"], "lon": data["lon"],
                    "name": f"{data['city']}{data.get('regionName','')}"
                }
                loc_info.setText(f"当前: {dl._picked_loc['name']} ({data['lat']:.2f}°N, {data['lon']:.2f}°E)")
                loc_info.setStyleSheet("color:#27AE60;")
            else:
                loc_info.setText("定位失败"); loc_info.setStyleSheet("color:#E74C3C;")
        except Exception as e:
            loc_info.setText(f"定位失败: {e}"); loc_info.setStyleSheet("color:#E74C3C;")

    b = QtWidgets.QPushButton("📍 自动定位"); b.clicked.connect(lambda: threading.Thread(target=auto_locate, daemon=True).start())
    f3l.addWidget(b)
    f3l.addWidget(lbl("自动定位基于IP, 建议使用搜索", size=9, color="gray"), alignment=QtCore.Qt.AlignCenter)

    sr = QtWidgets.QWidget(); srl = QtWidgets.QHBoxLayout(sr); srl.setContentsMargins(0, 0, 0, 0)
    city_entry = QtWidgets.QLineEdit(); city_entry.setPlaceholderText("输入城市名搜索")
    srl.addWidget(city_entry)
    def do_search():
        q = city_entry.text().strip()
        if not q: QtWidgets.QMessageBox.warning(dlg, "提示", "请输入城市名称"); return
        results = city_lookup(q)
        if not results: QtWidgets.QMessageBox.information(dlg, "未找到", f"未找到 '{q}'"); return
        pd = QtWidgets.QDialog(dlg, QtCore.Qt.FramelessWindowHint if sys.platform == "win32" else QtCore.Qt.Dialog)
        if sys.platform == "win32":
            pd.setAttribute(QtCore.Qt.WA_TranslucentBackground)
            pd.setWindowTitle("选择城市")
        pd.resize(500, 400)
        pd.setWindowModality(QtCore.Qt.WindowModal)

        if sys.platform == "win32":
            p_outer = QtWidgets.QFrame(pd)
            p_outer.setStyleSheet(f"QFrame {{ background:{outer_bg}; border:1px solid {outer_bd}; border-radius:12px; }}")
            p_ov = QtWidgets.QVBoxLayout(p_outer)
            p_ov.setContentsMargins(0, 0, 0, 0); p_ov.setSpacing(0)
            p_title = QtWidgets.QWidget(); p_title.setFixedHeight(36)
            p_title.setStyleSheet(f"background: transparent; border-bottom: 1px solid {title_bd};")
            ptl = QtWidgets.QHBoxLayout(p_title); ptl.setContentsMargins(16, 0, 8, 0)
            ptl.addWidget(lbl("选择城市", bold=True, size=10))
            ptl.addStretch()
            p_close = QtWidgets.QPushButton("✕"); p_close.setFixedSize(28, 28); p_close.setFlat(True)
            p_close.setStyleSheet(close_btn.styleSheet())
            p_close.clicked.connect(pd.reject); ptl.addWidget(p_close)
            p_ov.addWidget(p_title)
            pl = QtWidgets.QVBoxLayout(); pl.setContentsMargins(12, 8, 12, 12)
        else:
            pl = QtWidgets.QVBoxLayout(pd)
            pl.setContentsMargins(12, 12, 12, 12)
        pl.addWidget(lbl(f"搜索 '{q}' 找到 {len(results)} 个结果", size=12, color="gray"))
        lw = QtWidgets.QListWidget()
        lw.setStyleSheet("QListWidget { border:1px solid #DEDEDE; border-radius:6px; } QListWidget::item { padding:6px 8px; } QListWidget::item:selected { background:#E8F0FE; color:#2F80ED; }")
        for r in results:
            item = QtWidgets.QListWidgetItem(f"{r['name']}  {r['display']}")
            item.setToolTip(f"{r['lat']:.4f}°N, {r['lon']:.4f}°E")
            lw.addItem(item)
        pl.addWidget(lw)
        pb = QtWidgets.QWidget(); pbl = QtWidgets.QHBoxLayout(pb)
        pbl.addStretch()
        pbl.addWidget(QtWidgets.QPushButton("取消", clicked=pd.reject))
        def pick():
            idx = lw.currentRow()
            if idx >= 0 and idx < len(results):
                dl._picked_loc = results[idx]
                loc_info.setText(f"当前: {results[idx]['name']} ({results[idx]['lat']:.2f}°N, {results[idx]['lon']:.2f}°E)")
                loc_info.setStyleSheet("color:#27AE60;")
            pd.accept()
        pb_pick = QtWidgets.QPushButton("确认", clicked=pick); pbl.addWidget(pb_pick)
        pl.addWidget(pb)
        if sys.platform == "win32":
            p_ov.addLayout(pl)
            p_full = QtWidgets.QVBoxLayout(pd); p_full.setContentsMargins(0, 0, 0, 0); p_full.addWidget(p_outer)
        pd.exec()
    b = QtWidgets.QPushButton("🔍 搜索"); b.clicked.connect(do_search); srl.addWidget(b)
    f3l.addWidget(sr)
    swl.addWidget(f3)

    # ── 保存 ──
    def save():
        _cfg.config["weather_provider"] = "qweather" if "和风" in provider_cb.currentText() else "baidu"
        _cfg.config["baidu_key"] = bd_entry.text().strip()
        _cfg.config["qweather_key"] = qw_key.text().strip()
        _cfg.config["qweather_host"] = qw_host.text().strip()
        _cfg.config["brand"] = brand_cb.currentText()
        _cfg.config["appearance_mode"] = {v: k for k, v in mode_map.items()}.get(theme_cb.currentText(), "system")
        if hasattr(dl, "_picked_loc"):
            _cfg.config["location"] = dl._picked_loc
        save_config(_cfg.config); apply_config()
        app._ctrl_title.setText(f"{_cfg.config.get('brand','格力')}空调控制")
        from .ac_tab import update_brand_logo; update_brand_logo(app)
        app._wx_title.setText("当前天气")
        app._update_alert_source()
        # 重新获取天气（无论是否切换位置/源）
        app._fetch_weather_all()
        dlg.accept()

    btns = QtWidgets.QWidget(); bl = QtWidgets.QHBoxLayout(btns)
    bl.addStretch(); bl.addWidget(QtWidgets.QPushButton("取消", clicked=dlg.reject))
    bl.addWidget(QtWidgets.QPushButton("💾 保存", clicked=save)); layout.addWidget(btns)

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
                r = subprocess.run(["ping", param, "1", host], capture_output=True, text=True, timeout=5)
                return r.returncode == 0
            except Exception: return False

        push(lines, "┌─ 网络诊断 ─────────────", "#888")
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            if local_ip.startswith("127."):
                push(lines, "│ ❌ 电脑未接入互联网", "#E74C3C")
                push(lines, "│    → 请检查网线/WiFi", "#E67E22")
            else:
                gateway = ".".join(local_ip.split(".")[:3] + ["1"])
                push(lines, f"│ 📶 本机 IP: {local_ip}", "#AAA")
                if not _ping_ok(gateway):
                    push(lines, f"│ ❌ 网关 {gateway} 不通", "#E74C3C")
                    push(lines, "│    → 路由器连接有问题", "#E67E22")
                else:
                    push(lines, f"│ ✅ 路由器 {gateway} 可达", "#27AE60")
                    if _ping_ok("baidu.com"):
                        push(lines, "│ ✅ 外网 baidu.com 可达", "#27AE60")
                    else:
                        push(lines, "│ ❌ 外网不通（路由通但不出网）", "#E74C3C")
        except Exception as ne:
            push(lines, f"│ ❌ {ne}", "#E74C3C")
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
                del_s_btn.clicked.connect(_del_grp_slot)
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
            w.deleteLater()
        del_btn.clicked.connect(_del_group)

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
        save_config(_cfg.config)
        from broadlinkac_core.scheduler import register_all_jobs
        with __import__("broadlinkac_core.scheduler", fromlist=["_sched_lock"])._sched_lock:
            register_all_jobs()
        app._ui(lambda: app._update_schedule_display())
        dlg.accept()
    bl.addWidget(QtWidgets.QPushButton("保存", clicked=_save))
    bl.addStretch()
    layout.addWidget(btns); dlg.exec()


# ── 规则编辑 ──
def edit_rules(app):
    dlg = QtWidgets.QDialog(app); dlg.setWindowTitle("✏ 编辑温度规则"); dlg.resize(450, 400)
    dlg.setWindowModality(QtCore.Qt.WindowModal)
    layout = QtWidgets.QVBoxLayout(dlg)
    scroll = QtWidgets.QScrollArea(); scroll.setWidgetResizable(True)
    sw = QtWidgets.QWidget(); swl = QtWidgets.QVBoxLayout(sw); scroll.setWidget(sw); layout.addWidget(scroll)
    entries = []
    for i, (low, high, target, mode) in enumerate(_cfg.config.get("temp_rules", [
        [36, 99, 24, "cool"], [33, 35, 25, "cool"], [30, 32, 26, "cool"],
        [25, 29, 27, "cool"], [18, 24, 0, "off"], [0, 17, 28, "heat"]
    ])):
        r = QtWidgets.QWidget(); rl = QtWidgets.QHBoxLayout(r); rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QtWidgets.QLabel(f"规则{i + 1}:"))
        e1 = QtWidgets.QLineEdit(str(low)); e1.setFixedWidth(40); rl.addWidget(e1)
        rl.addWidget(QtWidgets.QLabel("~"))
        e2 = QtWidgets.QLineEdit(str(high)); e2.setFixedWidth(40); rl.addWidget(e2)
        rl.addWidget(QtWidgets.QLabel("°C →"))
        cb = QtWidgets.QComboBox(); cb.addItems(list(MODES.keys()))
        cb.setCurrentText(MODE_KEYS.get(mode, "制冷")); cb.setFixedWidth(80); rl.addWidget(cb)
        e3 = QtWidgets.QLineEdit(str(target)); e3.setFixedWidth(40); rl.addWidget(e3)
        rl.addWidget(QtWidgets.QLabel("°C")); swl.addWidget(r)
        entries.append((e1, e2, cb, e3))

    btns = QtWidgets.QWidget(); bl = QtWidgets.QHBoxLayout(btns)
    b = QtWidgets.QPushButton("取消"); b.clicked.connect(dlg.reject); bl.addWidget(b)
    b = QtWidgets.QPushButton("💾 保存")
    def save():
        rules = []
        for a, b, c, d in entries:
            try: rules.append([int(a.text()), int(b.text()), int(d.text()), MODES[c.currentText()]])
            except: pass
        if rules:
            _cfg.config["temp_rules"] = rules; save_config(_cfg.config); app._refresh_rules_display()
        dlg.accept()
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
    b = QtWidgets.QPushButton("保存"); b.clicked.connect(save); bl.addWidget(b)
    b = QtWidgets.QPushButton("取消"); b.clicked.connect(dlg.reject); bl.addWidget(b)
    layout.addWidget(btns); dlg.exec()
