"""对话框模块：设置 / 诊断 / 日志 / 规则编辑 / 台风预警"""

import os, sys, subprocess, json, urllib.request, threading

from PySide6 import QtCore, QtGui, QtWidgets

import acnexus_core.config as _cfg
from acnexus_core.config import save_config, apply_config, AC_BRANDS, LOG_DIR
from acnexus_core.ac_control import MODES, MODE_KEYS
from acnexus_core.logger import get_log_dates, write_log
from ._utils import lbl


# ── 主题引擎（已拆分至 theme.py）──
from .theme import apply_theme, _is_system_dark  # noqa: F401


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


def _dialog_content(dlg, title="", title_size=13, frameless=False, scroll=True, bg_override=None):
    """返回 (layout, swl)，Windows 下自绘标题+白底圆角，其他原生
       frameless=True 跳过外层卡片框，用原生窗口背景"""
    if sys.platform == "win32" and not frameless:
        from ._utils import is_dark
        dark = is_dark()
        bg = bg_override if bg_override else ("#2D2D2D" if dark else "white")
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
        if scroll:
            sw = QtWidgets.QWidget(); sw.setStyleSheet(f"background: {bg};")
            swl = QtWidgets.QVBoxLayout(sw)
            sa = QtWidgets.QScrollArea(); sa.setWidgetResizable(True)
            sa.setStyleSheet("QScrollArea { border:none; background:transparent; }")
            sa.setWidget(sw); layout.addWidget(sa)
        else:
            swl = QtWidgets.QVBoxLayout()
            layout.addLayout(swl)
        ov.addLayout(layout)
        full = QtWidgets.QVBoxLayout(dlg); full.setContentsMargins(0, 0, 0, 0); full.addWidget(outer)
    else:
        layout = QtWidgets.QVBoxLayout(dlg)
        layout.setContentsMargins(20 if frameless else 12, 16 if frameless else 12,
                                   20 if frameless else 12, 16 if frameless else 12)
        if frameless:
            from ._utils import is_dark
            dlg.setStyleSheet(f"QDialog {{ background:{ '#2D2D2D' if is_dark() else 'white' }; }}")
        if scroll:
            sw = QtWidgets.QWidget(); swl = QtWidgets.QVBoxLayout(sw); layout.addWidget(sw)
        else:
            swl = QtWidgets.QVBoxLayout(); layout.addLayout(swl)
    return layout, swl


# ── 设置对话框 + 学习向导委托（已拆分至 settings_dialog.py）──
from .settings_dialog import open_settings, _do_learn_wizard, _do_edit_custom  # noqa: F401


# ── 故障诊断（已拆分至 repair_dialog.py）──
from .repair_dialog import open_repair  # noqa: F401


def open_about(parent):
    dlg = _make_dialog(parent, "关于 AC-Nexus", 440, 360, frameless=True)
    layout, swl = _dialog_content(dlg, frameless=True)

    layout.addStretch()
    layout.addWidget(lbl("AC-Nexus v5.2", bold=True, size=18), alignment=QtCore.Qt.AlignCenter)
    layout.addSpacing(10)
    layout.addWidget(lbl("智能空调控制系统", size=13), alignment=QtCore.Qt.AlignCenter)
    layout.addWidget(lbl("Broadlink RM + 米家 MIoT 红外遥控器", color="#666", size=11), alignment=QtCore.Qt.AlignCenter)
    layout.addSpacing(12)
    layout.addWidget(lbl("17 品牌空调遥控 | 室外温度实时监测", color="#555", size=11), alignment=QtCore.Qt.AlignCenter)
    layout.addWidget(lbl("台风路径预报与预警 | 多时段定时开关 | 智能温控", color="#555", size=11), alignment=QtCore.Qt.AlignCenter)
    layout.addSpacing(16)

    gh_url = "https://github.com/oywq00008-cell/AC-Nexus-For-Agent"
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
    dlg = _make_dialog(parent, "删除设备", 360, 160, frameless=True)
    layout, swl = _dialog_content(dlg, frameless=True)

    if allow:
        msg = lbl(f"确定要删除「{name}」吗？此操作不可撤销。", size=13)
        msg.setWordWrap(True)
        msg.setMaximumWidth(300)
        swl.addWidget(msg)
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


# ── 定时模板编辑（已拆分至 schedule_dialog.py）──
from .schedule_dialog import _schedule_summary, open_schedule_template  # noqa: F401


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
            from acnexus_core.ir_learner import get_raw_code
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
        _cfg.config["temp_rules"] = rules
        # 同时直接写入当前设备，避免依赖 save_config sync
        mac = _cfg.config.get("current_device_mac", "")
        provider = _cfg.config.get("current_brand_type", "broadlink")
        dev = _cfg.config.setdefault("devices", {}).setdefault(provider, {}).setdefault(mac, {})
        dev["temp_rules"] = rules
        save_config(_cfg.config); app._refresh_rules_display()
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
