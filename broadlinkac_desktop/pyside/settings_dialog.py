"""设置对话框 — 基础设置 / 城市设置 / 天气 API 三张卡片"""

import json
import os
import sys
import threading
import urllib.request

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6 import QtSvg

import broadlinkac_core.config as _cfg
from broadlinkac_core.config import save_config, apply_config, AC_BRANDS
from broadlinkac_core.logger import write_log
from broadlinkac_core import autostart as _autostart

from .theme import apply_theme, _is_system_dark
from ._utils import lbl, is_dark as _is_dark


# ── 学习向导委托 ──

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
    from broadlinkac_core.ir_learner import load_custom_codes, save_custom_codes, list_custom

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
        steps = [("关机", "请先打开遥控器，然后对准红外设备按遥控器的【关机】键")]
        for combo in result["new_combos"]:
            parts = combo.replace("开机_", "").replace("°C", "").split("_")
            if len(parts) >= 3:
                m, t, f = parts[0], parts[1], parts[2]
                steps.append((combo, f"请在遥控器上设为：模式【{m}】、温度【{t}°C】、风速【{f}】。\n设好后关掉遥控器，对准红外设备按【开机】"))
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


# ── 设置对话框 ──

def open_settings(app):
    dlg = QtWidgets.QDialog(app, QtCore.Qt.FramelessWindowHint if sys.platform == "win32" else QtCore.Qt.Dialog)
    # 继承主窗口的 QPalette (Fusion 焦点框颜色 = Highlight 色)
    dlg.setPalette(app.palette())
    if sys.platform == "win32":
        dlg.setAttribute(QtCore.Qt.WA_TranslucentBackground)
    dlg.resize(540, 720)  # 预留阴影空间 (原 500×680 + 40)
    dlg.setWindowModality(QtCore.Qt.WindowModal)
    dlg.setWindowTitle("设置")

    if sys.platform == "win32":
        # 自绘无边框窗口
        dark = _is_dark()
        outer_bg = "#2D2D2D" if dark else "white"
        outer_bd = "#444" if dark else "#DEDEDE"
        title_bd = "#444" if dark else "#E5E7EB"
        title_close_hover = "#444" if dark else "#F0F0F0"

        outer = QtWidgets.QFrame(dlg)
        outer.setObjectName("settings_outer")
        outer.setStyleSheet(f"QFrame#settings_outer {{ background:{outer_bg}; border:1px solid {outer_bd}; border-radius:12px; }}")
        # 阴影
        shadow = QtWidgets.QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 0)
        shadow.setColor(QtGui.QColor(0, 0, 0, 100))
        outer.setGraphicsEffect(shadow)
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
        full.setContentsMargins(20, 20, 20, 20)
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
        dark = _is_dark()
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

    r = QtWidgets.QWidget(); rl = QtWidgets.QHBoxLayout(r); rl.setContentsMargins(0, 0, 0, 0)
    rl.addWidget(QtWidgets.QLabel("开机自启:")); rl.addStretch(1)
    autostart_cb = QtWidgets.QComboBox(); autostart_cb.addItems(["关", "开"])
    autostart_cb.setCurrentText("开" if _autostart.is_enabled() else "关")
    autostart_cb.setMinimumWidth(140); autostart_cb.setMaximumWidth(140)
    autostart_cb.setStyleSheet("QComboBox { selection-background-color: #2F80ED; selection-color: white; }")
    autostart_cb.setEditable(True); autostart_cb.lineEdit().setAlignment(QtCore.Qt.AlignCenter); autostart_cb.lineEdit().setReadOnly(True)
    def toggle_autostart(txt):
        script = os.path.join(os.path.dirname(__file__), "..", "ac_controller_pyside6.py")
        if txt == "开": _autostart.enable(script)
        else: _autostart.disable()
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
    rl.addWidget(QtWidgets.QLabel("自定义遥控器:"))
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
        "删除当前自定义遥控器")
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
        picker.resize(340, 380)  # 预留阴影 (原 300×340 + 40)
        if sys.platform == "win32":
            picker.setAttribute(QtCore.Qt.WA_TranslucentBackground)
            dark = _is_dark()
            outer_bg = "#2D2D2D" if dark else "white"
            outer_bd = "#444" if dark else "#DEDEDE"
            outer = QtWidgets.QFrame(picker)
            outer.setObjectName("picker_outer")
            outer.setStyleSheet(f"QFrame#picker_outer {{ background:{outer_bg}; border:1px solid {outer_bd}; border-radius:12px; }}")
            # 阴影
            shadow = QtWidgets.QGraphicsDropShadowEffect()
            shadow.setBlurRadius(20)
            shadow.setOffset(0, 0)
            shadow.setColor(QtGui.QColor(0, 0, 0, 100))
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
            # 标题栏拖拽
            def move_window(event):
                if event.buttons() == QtCore.Qt.LeftButton:
                    picker.move(event.globalPosition().toPoint() - tb.property("drag_pos"))
            tb.mouseMoveEvent = move_window
            tb.mousePressEvent = lambda e: tb.setProperty("drag_pos", e.globalPosition().toPoint() - picker.frameGeometry().topLeft())
            # 列表
            lw = QtWidgets.QListWidget()
            lw.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            lw.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
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
            full = QtWidgets.QVBoxLayout(picker); full.setContentsMargins(20, 20, 20, 20); full.addWidget(outer)
        # 按最长文字自适应宽度
        fm_title = QtGui.QFontMetrics(lbl(title_text, bold=True, size=11).font())
        fm_item = lw.fontMetrics()
        max_w = fm_title.horizontalAdvance(title_text) + 90  # 图标+关闭按钮+边距
        for i in range(lw.count()):
            w = fm_item.horizontalAdvance(lw.item(i).text()) + 50  # 列表项内边距
            if w > max_w: max_w = w
        max_w = max(min(max_w + 40, 900), 280)  # +40 补偿阴影边距
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
    _refresh_settings_theme(_is_dark())

    import threading; dlg.exec()
