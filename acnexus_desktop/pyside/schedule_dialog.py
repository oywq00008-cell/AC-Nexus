"""定时模板编辑 — 摘要数据 + 多日期组模板管理对话框"""

from PySide6 import QtCore, QtGui, QtWidgets

import acnexus_core.config as _cfg
from acnexus_core.config import save_config
from acnexus_core.logger import write_log

# _make_dialog/_dialog_content 定义在 dialogs.py 顶层，
# 此处为循环导入，满足两点即可安全：
# 1. dialogs.py 中这些函数定义在所有 import schedule_dialog 之前
# 2. 不在模块顶层调用，仅函数内使用
from .dialogs import _make_dialog, _dialog_content
from ._utils import lbl, is_dark

_WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _schedule_summary(app):
    """返回当前模板的摘要数据，支持多日期组
    返回: {"name": str, "groups": [{"days_str": str, "times": [str, ...]}, ...]}，错误时含 "error" 键
    """
    mac = _cfg.config.get("current_device_mac", "")
    provider = _cfg.config.get("current_brand_type", "broadlink")
    dev = _cfg.config.get("devices", {}).get(provider, {}).get(mac, {})
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
    provider = _cfg.config.get("current_brand_type", "broadlink")
    dev = _cfg.config.setdefault("devices", {}).setdefault(provider, {}).setdefault(mac, {})
    templates = _cfg.config.setdefault("schedule_templates", {})
    if not templates:
        templates["默认"] = {"groups": [{"days": [1,2,3,4,5], "slots": []}]}
    active = dev.get("active_template", list(templates.keys())[0] if templates else "")

    dlg = _make_dialog(app, "定时模板编辑", 500, 560)
    layout, swl = _dialog_content(dlg, title="定时模板编辑", bg_override="#383838")
    # 阴影
    outer = dlg.findChild(QtWidgets.QFrame)
    if outer:
        outer.setObjectName("schedule_outer")
        from ._utils import is_dark
        _dark2 = is_dark()
        _bg = "#383838" if _dark2 else "white"
        _bd = "#444" if _dark2 else "#DEDEDE"
        outer.setStyleSheet(f"QFrame#schedule_outer {{ background:{_bg}; border:1px solid {_bd}; border-radius:12px; }}")
        tb = outer.findChild(QtWidgets.QWidget)
        if tb:
            tb.setStyleSheet(f"background: transparent; border-bottom: 1px solid {_bd};")
            def _on_press(e):
                if e.button() == QtCore.Qt.LeftButton:
                    tb._drag_start = e.globalPosition().toPoint() - dlg.frameGeometry().topLeft()
            def _on_move(e):
                if hasattr(tb, '_drag_start'):
                    dlg.move(e.globalPosition().toPoint() - tb._drag_start)
            tb.mousePressEvent = _on_press
            tb.mouseMoveEvent = _on_move
        shadow = QtWidgets.QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 0)
        shadow.setColor(QtGui.QColor(0, 0, 0, 100))
        outer.setGraphicsEffect(shadow)
    swl.setSpacing(8)
    dlg.layout().setContentsMargins(10, 10, 10, 10)

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
            for provider_devs in _cfg.config.get("devices", {}).values():
                if not isinstance(provider_devs, dict):
                    continue
                for d in provider_devs.values():
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
        for provider, provider_devs in _cfg.config.get("devices", {}).items():
            if not isinstance(provider_devs, dict):
                continue
            for dmac, d in provider_devs.items():
                if d.get("active_template") == name:
                    if dmac == mac and provider == _cfg.config.get("current_brand_type"):
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
        frame.setObjectName("date_group_card")
        dark = is_dark()
        _bg = "#383838" if dark else "white"
        _label_color = "#CCC" if dark else "#555"
        frame.setStyleSheet(f"QFrame#date_group_card {{ background:{_bg}; border:2px solid {'#3A7BD5' if dark else '#B3D4FF'}; border-radius:8px; }}")
        fl = QtWidgets.QVBoxLayout(frame); fl.setContentsMargins(10, 8, 10, 8); fl.setSpacing(6)

        # 组标题
        header = QtWidgets.QWidget()
        hl = QtWidgets.QHBoxLayout(header); hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(lbl(f"日期组 {grp_idx + 1}", bold=True, size=11, color=_label_color))
        hl.addStretch()
        del_btn = QtWidgets.QPushButton("✕ 删除此组")
        _del_color = "#FF6B6B" if dark else "#E74C3C"
        del_btn.setStyleSheet(f"QPushButton {{ border:none; color:{_del_color}; font-size:11px; }} QPushButton:hover {{ text-decoration:underline; }}")
        hl.addWidget(del_btn)
        fl.addWidget(header)

        # 星期勾选
        day_checks = []
        dw = QtWidgets.QWidget()
        dwl = QtWidgets.QHBoxLayout(dw); dwl.setContentsMargins(0, 0, 0, 0); dwl.setSpacing(2)
        for i, name in enumerate(_WEEKDAYS):
            cb = QtWidgets.QCheckBox(name)
            _cb_color = "#EEE" if dark else "#333"
            cb.setStyleSheet(f"QCheckBox {{ color:{_cb_color}; spacing:4px; }}")
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
            sl = slots
            while slot_layout.count():
                w = slot_layout.takeAt(0).widget()
                if w:
                    w.hide()
                    w.setParent(None)  # 立即释放，不等 deleteLater
            for si, slot in enumerate(sl):
                # 时段行
                row = QtWidgets.QWidget()
                rl = QtWidgets.QHBoxLayout(row); rl.setContentsMargins(0, 2, 0, 2); rl.setSpacing(4)
                on_chk = QtWidgets.QCheckBox("开机")
                _chk_fg = "#EEE" if dark else "#333"
                on_chk.setStyleSheet(f"QCheckBox {{ color:{_chk_fg}; }}")
                on_chk.setChecked(slot.get("on_enabled", True))
                rl.addWidget(on_chk)
                on_h, on_m = slot["on"].split(":") if ":" in slot["on"] else ("08", "00")
                on_h_cb = QtWidgets.QComboBox(); on_h_cb.addItems(_HOURS); on_h_cb.setCurrentText(on_h); on_h_cb.setFixedWidth(50)
                rl.addWidget(on_h_cb)
                colon_on = QtWidgets.QLabel(":"); colon_on.setStyleSheet(f"color:{_chk_fg};")
                rl.addWidget(colon_on)
                on_m_cb = QtWidgets.QComboBox(); on_m_cb.addItems(_MINS); on_m_cb.setCurrentText(on_m); on_m_cb.setFixedWidth(50)
                rl.addWidget(on_m_cb)
                rl.addSpacing(12)
                off_chk = QtWidgets.QCheckBox("关机")
                off_chk.setStyleSheet(f"QCheckBox {{ color:{_chk_fg}; }}")
                off_chk.setChecked(slot.get("off_enabled", True) and bool(slot.get("off")))
                rl.addWidget(off_chk)
                off_h, off_m = (slot["off"].split(":") if slot.get("off") and ":" in slot["off"] else ("18", "00"))
                off_h_cb = QtWidgets.QComboBox(); off_h_cb.addItems(_HOURS); off_h_cb.setCurrentText(off_h); off_h_cb.setFixedWidth(50)
                rl.addWidget(off_h_cb)
                colon_off = QtWidgets.QLabel(":"); colon_off.setStyleSheet(f"color:{_chk_fg};")
                rl.addWidget(colon_off)
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
                    frame.updateGeometry()
                del_s_btn = QtWidgets.QPushButton("×")
                del_s_btn.setFixedSize(22, 22)
                _ds_bd = "#555" if dark else "#CCC"
                _ds_fg = "#AAA" if dark else "#999"
                _ds_hv = "#444" if dark else "#EEE"
                del_s_btn.setStyleSheet(f"QPushButton {{ border:1px solid {_ds_bd}; border-radius:3px; color:{_ds_fg}; }} QPushButton:hover {{ background:{_ds_hv}; }}")
                del_s_btn.clicked.connect(lambda checked=False: _del_grp_slot())
                rl.addWidget(del_s_btn)
                slot_layout.addWidget(row)
            slot_layout.activate()
            slot_list.adjustSize()
            frame.adjustSize()
        _rebuild_group_slots()
        fl.addWidget(slot_list)

        # 添加时段按钮
        add_s_btn = QtWidgets.QPushButton("+ 添加时段")
        _asb_bd = "#555" if dark else "#CCC"
        _asb_fg = "#AAA" if dark else "#888"
        add_s_btn.setStyleSheet(f"QPushButton {{ border:1px dashed {_asb_bd}; border-radius:4px; color:{_asb_fg}; background:transparent; padding:2px; }} QPushButton:hover {{ border-color:#2F80ED; color:#2F80ED; }}")
        def _add_grp_slot_clicked():
            slots.append({"on": "08:00", "on_enabled": True, "off": "18:00", "off_enabled": True})
            _rebuild_group_slots()
            frame.updateGeometry()
        add_s_btn.clicked.connect(_add_grp_slot_clicked)
        fl.addWidget(add_s_btn)

        # 删除组
        def _del_group(w=frame):
            w.hide()
            groups_layout.removeWidget(w)
            w.setParent(None)
        del_btn.clicked.connect(lambda checked=False, w=frame: _del_group(w))

        groups_layout.addWidget(frame)
        frame.updateGeometry()
        groups_widget.updateGeometry()

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
        from acnexus_core.scheduler import register_all_jobs
        with __import__("acnexus_core.scheduler", fromlist=["_sched_lock"])._sched_lock:
            register_all_jobs()
        app._ui(lambda: app._update_schedule_display())
        write_log("定时", f"已保存模板: {name}")
        dlg.accept()
    bl.addWidget(QtWidgets.QPushButton("保存", clicked=_save))
    bl.addStretch()
    layout.addWidget(btns); dlg.exec()
