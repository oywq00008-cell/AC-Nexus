"""学习向导 v2 — 全局码库 + 自由组合学习"""

import sys

from PySide6 import QtCore, QtGui, QtWidgets

from acnexus_core.ir_learner import save_learned_codes

from ._utils import lbl, is_dark


LOGO_LIST = [
    ("无Logo", ""), ("格力", "gree"), ("美的", "midea"), ("海尔", "haier"),
    ("奥克斯", "aux_ac"), ("松下", "panasonic"), ("海信", "hisense"),
    ("大金", "daikin"), ("三菱", "mitsubishi"), ("日立", "hitachi"),
    ("富士通", "fujitsu"), ("小米", "midea"),
]

BUILTIN_BRANDS = {"格力", "美的", "海尔", "奥克斯", "松下", "海信", "大金", "三菱",
                  "日立", "富士通", "小米", "华凌", "巴鲁", "开利", "现代", "Fuego"}

MODES_LIST = ["制冷", "制热", "除湿", "送风"]
FANS_LIST = ["自动", "高", "中", "低"]
TEMP_RANGE = list(range(16, 31))


def _dialog_frame(parent, title, w, h):
    """创建统一样式的弹窗壳 — Windows 下自绘无边框圆角"""
    if sys.platform == "win32":
        dlg = QtWidgets.QDialog(parent, QtCore.Qt.FramelessWindowHint)
        dlg.setAttribute(QtCore.Qt.WA_TranslucentBackground)
    else:
        dlg = QtWidgets.QDialog(parent)
    dlg.setWindowModality(QtCore.Qt.WindowModal)
    dlg.resize(w, h)
    dlg.setWindowTitle(title)

    if sys.platform == "win32":
        dark = is_dark()
        outer_bg = "#2D2D2D" if dark else "white"
        outer_bd = "#444" if dark else "#DEDEDE"
        outer = QtWidgets.QFrame(dlg)
        outer.setObjectName("learn_outer")
        outer.setStyleSheet(f"QFrame#learn_outer {{ background:{outer_bg}; border:2px solid {outer_bd}; border-radius:12px; }}")
        ov = QtWidgets.QVBoxLayout(outer); ov.setContentsMargins(0, 0, 0, 0); ov.setSpacing(0)

        # 自绘标题栏
        tb = QtWidgets.QWidget(); tb.setFixedHeight(36)
        tb.setStyleSheet(f"background: transparent; border-bottom: 1px solid {outer_bd};")
        t_bl = QtWidgets.QHBoxLayout(tb); t_bl.setContentsMargins(16, 0, 8, 0)
        t_bl.addWidget(lbl(title, bold=True, size=13))
        t_bl.addStretch()
        close_btn = QtWidgets.QPushButton("✕"); close_btn.setFixedSize(28, 28); close_btn.setFlat(True)
        close_btn.setStyleSheet(f"QPushButton {{ font-size:14px; color:{'#AAA' if dark else '#888'}; border:none; background:transparent; }} QPushButton:hover {{ background:{'#444' if dark else '#F0F0F0'}; border-radius:4px; }}")
        close_btn.clicked.connect(dlg.reject); t_bl.addWidget(close_btn)
        ov.addWidget(tb)

        # 标题栏拖拽
        def move_window(event):
            if event.buttons() == QtCore.Qt.LeftButton:
                dlg.move(event.globalPosition().toPoint() - tb.property("drag_pos"))
        tb.mouseMoveEvent = move_window
        tb.mousePressEvent = lambda e: tb.setProperty("drag_pos", e.globalPosition().toPoint() - dlg.frameGeometry().topLeft())

        layout = QtWidgets.QVBoxLayout(); layout.setContentsMargins(12, 8, 12, 12)
        ov.addLayout(layout)
        full = QtWidgets.QVBoxLayout(dlg); full.setContentsMargins(0, 0, 0, 0); full.addWidget(outer)
    else:
        layout = QtWidgets.QVBoxLayout(dlg)
        layout.setContentsMargins(16, 12, 16, 12)
        dark = is_dark()
        dlg.setStyleSheet(f"QDialog {{ background:{'#2D2D2D' if dark else 'white'}; }}")

    return dlg, layout


def _combo(label_text, items, default=None):
    """创建标签+下拉框行"""
    w = QtWidgets.QWidget()
    l = QtWidgets.QHBoxLayout(w); l.setContentsMargins(0, 0, 0, 0)
    l.addWidget(QtWidgets.QLabel(label_text))
    cb = QtWidgets.QComboBox(); cb.addItems([str(i) for i in items])
    if default: cb.setCurrentText(str(default))
    l.addWidget(cb); l.addStretch()
    return w, cb


# ==================== 窗口 A：新增自定义遥控器 ====================
class NewRemoteDialog:
    def __init__(self, parent, edit_mode=False, edit_name="", edit_logo="", edit_codes=None):
        self.result = None
        self.edit_mode = edit_mode
        self.edit_name = edit_name
        self.edit_codes = edit_codes or {}
        title = f"编辑 {edit_name}" if edit_mode else "新增自定义遥控器"
        self.dlg, layout = _dialog_frame(parent, title, 450, 500)
        layout.setSpacing(8)

        dark = is_dark()
        tc = "#EEE" if dark else "#333"
        ibg = "#3D3D3D" if dark else "white"
        ibd = "#555" if dark else "#DEDEDE"
        hint_color = "#888" if dark else "gray"
        inp_qss = f"QLineEdit {{ padding:6px; border:1px solid {ibd}; border-radius:4px; color:{tc}; background:{ibg}; }}"
        cb_qss = f"QComboBox {{ padding:4px; border:1px solid {ibd}; border-radius:4px; color:{tc}; background:{ibg}; }} QComboBox QAbstractItemView {{ background:{ibg}; color:{tc}; selection-background-color:#2F80ED; }}"
        list_qss = f"QListWidget {{ border:1px solid {ibd}; border-radius:4px; color:{tc}; background:{ibg}; }} QListWidget::item {{ padding:4px; }}"
        add_btn_qss = f"QPushButton {{ color:#2F80ED; border:1px solid #2F80ED; border-radius:4px; padding:4px 8px; }} QPushButton:hover {{ background:{'#1E3A5F' if dark else '#E8F0FE'}; }}"

        layout.addWidget(lbl("设置设备名称、Logo，添加要学习的组合", color=hint_color, size=11))

        layout.addWidget(lbl("设备名称 *:", size=11))
        self.name_entry = QtWidgets.QLineEdit()
        self.name_entry.setPlaceholderText("例：卧室的格力空调")
        self.name_entry.setStyleSheet(inp_qss)
        if edit_mode:
            self.name_entry.setText(edit_name)
        layout.addWidget(self.name_entry)

        layout.addWidget(lbl("品牌Logo:", size=11))
        self.logo_combo = QtWidgets.QComboBox()
        self.logo_combo.addItems([l[0] for l in LOGO_LIST])
        self.logo_combo.setStyleSheet(cb_qss)
        if edit_mode and edit_logo:
            for i, l in enumerate(LOGO_LIST):
                if l[1] == edit_logo:
                    self.logo_combo.setCurrentIndex(i); break
        layout.addWidget(self.logo_combo)

        layout.addSpacing(4)
        layout.addWidget(lbl("学习组合列表 (关机自动添加):", bold=True, size=11))

        self.combo_list = QtWidgets.QListWidget()
        self.combo_list.setStyleSheet(list_qss)
        layout.addWidget(self.combo_list)

        # 编辑模式：加载已有组合
        if edit_mode:
            for key in edit_codes:
                if key != "关机":
                    self.combo_list.addItem(key)

        # 添加组合行：模式 + 温度 + 风速
        add_row = QtWidgets.QWidget()
        arl = QtWidgets.QHBoxLayout(add_row); arl.setContentsMargins(0, 0, 0, 0)
        _, self.mode_cb = _combo("模式:", MODES_LIST)
        arl.addWidget(_)
        _, self.temp_cb = _combo("温度:", TEMP_RANGE, 26)
        arl.addWidget(_)
        _, self.fan_cb = _combo("风速:", FANS_LIST, "自动")
        arl.addWidget(_)
        add_btn = QtWidgets.QPushButton("＋ 添加")
        add_btn.setStyleSheet(add_btn_qss)
        add_btn.clicked.connect(self._add_combo)
        arl.addWidget(add_btn)
        layout.addWidget(add_row)

        del_btn = QtWidgets.QPushButton("🗑 删除选中")
        del_btn.clicked.connect(lambda: self.combo_list.takeItem(self.combo_list.currentRow()))
        layout.addWidget(del_btn)

        layout.addStretch()
        btn_row = QtWidgets.QWidget(); brl = QtWidgets.QHBoxLayout(btn_row)
        brl.addStretch()
        cancel_btn = QtWidgets.QPushButton("取消")
        cancel_btn.setFixedHeight(30)
        cancel_btn.setStyleSheet(f"QPushButton {{ background:{'#555' if dark else 'white'}; color:{'#DDD' if dark else '#333'}; border:1px solid {'#666' if dark else '#DEDEDE'}; border-radius:6px; padding:0 16px; font-size:13px; }} QPushButton:hover {{ background:{'#666' if dark else '#F5F5F5'}; }}")
        cancel_btn.clicked.connect(self.dlg.reject)
        brl.addWidget(cancel_btn)

        if edit_mode:
            save_btn = QtWidgets.QPushButton("保存")
            save_btn.setFixedHeight(30)
            save_btn.setStyleSheet(f"QPushButton {{ background:{'#4CAF50' if dark else '#27AE60'}; color:white; border:none; border-radius:6px; padding:0 16px; font-size:13px; font-weight:500; }} QPushButton:hover {{ background:{'#388E3C' if dark else '#1E8E3E'}; }}")
            save_btn.clicked.connect(self._save_only)
            brl.addWidget(save_btn)

        self.start_btn = QtWidgets.QPushButton("开始学习")
        self.start_btn.setFixedHeight(30)
        self.start_btn.setStyleSheet(f"QPushButton {{ background:{'#2F80ED' if not dark else '#3B82F6'}; color:white; border:none; border-radius:6px; padding:0 16px; font-size:13px; font-weight:500; }} QPushButton:hover {{ background:{'#2569D4' if not dark else '#1D4ED8'}; }}")
        self.start_btn.clicked.connect(self._start_learn)
        brl.addWidget(self.start_btn)
        layout.addWidget(btn_row)

    def _add_combo(self):
        mode = self.mode_cb.currentText()
        temp = self.temp_cb.currentText()
        fan = self.fan_cb.currentText()
        label = f"开机_{mode}_{temp}°C_{fan}"
        for i in range(self.combo_list.count()):
            if self.combo_list.item(i).text() == label:
                return
        self.combo_list.addItem(label)

    def _save_only(self):
        """编辑模式：只保存元数据和删除操作，不学习新组合"""
        name = self.name_entry.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self.dlg, "提示", "请输入设备名称")
            return
        idx = self.logo_combo.currentIndex()
        logo = LOGO_LIST[idx][1] if 0 <= idx < len(LOGO_LIST) else ""

        current_combos = set()
        for i in range(self.combo_list.count()):
            current_combos.add(self.combo_list.item(i).text())
        old_combos = set(k for k in self.edit_codes if k != "关机")
        deleted = list(old_combos - current_combos)
        new_combos = list(current_combos - old_combos)
        if new_combos:
            QtWidgets.QMessageBox.warning(self.dlg, "提示",
                f"有 {len(new_combos)} 个新组合未学习，请点击「开始学习」或先删除它们")
            return

        self.result = {"name": name, "logo": logo,
                       "new_combos": [], "deleted_combos": deleted}
        self.dlg.accept()

    def _start_learn(self):
        name = self.name_entry.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self.dlg, "提示", "请输入设备名称")
            return
        if name in BUILTIN_BRANDS:
            from acnexus_core.config import AC_BRANDS
            if name in AC_BRANDS:
                QtWidgets.QMessageBox.warning(self.dlg, "提示", f"'{name}' 是内置品牌名，请换一个名称")
                return
        combos = []
        for i in range(self.combo_list.count()):
            combos.append(self.combo_list.item(i).text())
        if not combos:
            QtWidgets.QMessageBox.warning(self.dlg, "提示", "请至少添加一个学习组合")
            return
        idx = self.logo_combo.currentIndex()
        logo = LOGO_LIST[idx][1] if 0 <= idx < len(LOGO_LIST) else ""

        categories = {"关机": "请先打开遥控器，然后对准红外设备按遥控器的【关机】键"}
        for combo in combos:
            parts = combo.replace("开机_", "").replace("°C", "").split("_")
            if len(parts) >= 3:
                m, t, f = parts[0], parts[1], parts[2]
                categories[combo] = f"请在遥控器上设为：模式【{m}】、温度【{t}°C】、风速【{f}】。\n设好后关掉遥控器，对准红外设备按【开机】"

        if self.edit_mode:
            # 编辑模式：只学新增的组合
            old_keys = set(self.edit_codes.keys())
            new_combos_list = [c for c in combos if c not in old_keys]
            if not new_combos_list:
                QtWidgets.QMessageBox.information(self.dlg, "提示", "没有新增组合，无需学习")
                return
            # 计算删除的组合
            current_set = set(combos)
            deleted = list(old_keys - current_set - {"关机"})
            # Only learn NEW combos
            new_categories = {"关机": categories["关机"]}
            for combo in combos:
                if combo not in old_keys:
                    new_categories[combo] = categories[combo]
            self.result = {"name": name, "logo": logo,
                           "steps": list(new_categories.items()),
                           "new_combos": [c for c in combos if c not in old_keys],
                           "deleted_combos": deleted}
        else:
            self.result = {"name": name, "logo": logo, "steps": list(categories.items()),
                           "new_combos": combos, "deleted_combos": []}
        self.dlg.accept()

    def exec(self):
        self.dlg.exec()
        return self.result


# ==================== 窗口 B：N步学习向导 ====================
class LearnWizard:
    def __init__(self, parent, device_name, logo, steps):
        self.parent = parent
        self.device_name = device_name
        self.logo = logo
        self.steps = steps  # [(label, instruction), ...]
        self.codes = {}
        self.current_step = 0
        self.capturing = False
        self.host = None

        self.dlg, self.layout = _dialog_frame(parent, f"学习向导 (1/{len(steps)})", 450, 330)
        self.layout.setSpacing(10)
        self._build_step()

    def _resolve_host(self):
        import acnexus_core.config as _cfg
        dev = _cfg.get_current_device()
        host = dev.get("host", "")
        if not host:
            QtWidgets.QMessageBox.warning(self.dlg, "错误", "请先在主界面连接红外设备")
            return None
        return host

    def _build_step(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        dark = is_dark()
        tc = "#EEE" if dark else "#333"
        hint = "#AAA" if dark else "#555"
        dim = "#888" if dark else "#888"

        label, instruction = self.steps[self.current_step]
        total = len(self.steps)
        self.dlg.setWindowTitle(f"学习向导 ({self.current_step + 1}/{total})")

        self.layout.addWidget(lbl(label.replace("开机_", ""), bold=True, size=14, color=tc), alignment=QtCore.Qt.AlignCenter)
        self.layout.addWidget(lbl(instruction, color=hint, size=11))
        self.layout.addSpacing(6)

        self.status_label = lbl("如果你准备好了，请点击开始捕获", color=dim, size=11)
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.layout.addWidget(self.status_label)

        self.timer_label = lbl("", color="#E67E22", size=18)
        self.timer_label.setAlignment(QtCore.Qt.AlignCenter)
        self.layout.addWidget(self.timer_label)

        self.layout.addStretch()

        btn_row = QtWidgets.QWidget(); brl = QtWidgets.QHBoxLayout(btn_row)
        brl.addStretch()
        cancel_btn = QtWidgets.QPushButton("取消")
        cancel_btn.setStyleSheet(f"QPushButton {{ background:{'#555' if dark else 'white'}; color:{'#DDD' if dark else '#333'}; border:1px solid {'#666' if dark else '#DEDEDE'}; border-radius:6px; padding:4px 14px; }} QPushButton:hover {{ background:{'#666' if dark else '#F5F5F5'}; }}")
        cancel_btn.clicked.connect(self.dlg.reject)
        brl.addWidget(cancel_btn)
        self.capture_btn = QtWidgets.QPushButton("🎯 开始捕获")
        self.capture_btn.setStyleSheet(f"QPushButton {{ background:{'#2F80ED' if not dark else '#3B82F6'}; color:white; padding:6px 16px; border-radius:4px; font-weight:bold; }} QPushButton:hover {{ background:{'#2569D4' if not dark else '#1D4ED8'}; }} QPushButton:disabled {{ background:#888; }}")
        self.capture_btn.clicked.connect(self._start_capture)
        brl.addWidget(self.capture_btn)
        self.layout.addWidget(btn_row)

    def _start_capture(self):
        if self.capturing: return
        host = self._resolve_host()
        if not host: return
        self.host = host
        self.capturing = True
        self.capture_btn.setEnabled(False)
        self.status_label.setText("学习模式已启动，请对准红外设备按下遥控器按键...")
        self.status_label.setStyleSheet("color:#2F80ED;")
        import broadlink
        try:
            self._device = broadlink.hello(self.host)
            self._device.auth()
            self._device.enter_learning()
        except Exception as e:
            self.status_label.setText(f"设备连接失败: {e}")
            self.status_label.setStyleSheet("color:#E74C3C;")
            self.capturing = False
            self.capture_btn.setEnabled(True)
            return
        self._start_timer(45)
        self._poll_learn()

    def _poll_learn(self):
        if not self.capturing: return
        try:
            data = self._device.check_data()
            if data:
                self.codes[self.steps[self.current_step][0]] = data.hex()
                self._on_success()
                return
        except Exception:
            pass
        QtCore.QTimer.singleShot(500, self._poll_learn)

    def _on_success(self):
        self.capturing = False
        label = self.steps[self.current_step][0]
        self.status_label.setText(f"✓ {label.replace('开机_','')} — 捕获成功!")
        self.status_label.setStyleSheet("color:#27AE60;")
        self.capture_btn.setText("➡ 下一步" if self.current_step < len(self.steps) - 1 else "✅ 完成学习")
        self.capture_btn.setEnabled(True)
        self.capture_btn.clicked.disconnect()
        self.capture_btn.clicked.connect(self._next_step)
        self.timer_label.setText("")

    def _on_timeout(self):
        self.capturing = False
        self.status_label.setText("✗ 超时，请重试")
        self.status_label.setStyleSheet("color:#E74C3C;")
        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("🔄 重新捕获")
        self.capture_btn.clicked.disconnect()
        self.capture_btn.clicked.connect(self._start_capture)
        self.timer_label.setText("")

    def _next_step(self):
        if self.current_step >= len(self.steps) - 1:
            self._finish()
            return
        self.current_step += 1
        self._build_step()

    def _finish(self):
        save_learned_codes(self.device_name, self.logo, self.codes)
        user_count = len(self.codes) - (1 if "关机" in self.codes else 0)
        mb = QtWidgets.QMessageBox(self.dlg)
        mb.setWindowTitle("学习完成")
        mb.setText(f"已保存 {user_count} 个组合到 '{self.device_name}'")
        cont_btn = mb.addButton("继续学习下一组", QtWidgets.QMessageBox.AcceptRole)
        mb.addButton("关闭", QtWidgets.QMessageBox.RejectRole)
        mb.exec()
        self._continue = (mb.clickedButton() == cont_btn)
        self.dlg.accept()

    def _start_timer(self, seconds):
        self._count = seconds
        self.timer_label.setText(f"{self._count}s")
        self._update_timer()

    def _update_timer(self):
        if self._count <= 0:
            self.timer_label.setText("")
            if self.capturing:
                self._on_timeout()
            return
        self.timer_label.setText(f"{self._count}s")
        self._count -= 1
        QtCore.QTimer.singleShot(1000, self._update_timer)

    def exec(self):
        self._continue = False
        self.dlg.exec()
        return self._continue
