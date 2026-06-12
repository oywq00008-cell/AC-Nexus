"""BroadlinkAC Desktop — PySide6 版本"""

import sys, platform, threading, os, json
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

import broadlinkac_core.config as _cfg
from broadlinkac_core.config import (
    get_current_device, get_device_list, switch_device, save_config,
    add_or_update_device,
)
from broadlinkac_core.ac_control import send_ac, discover_devices, FANS, MODES
from broadlinkac_core.scheduler import register_all_jobs
from broadlinkac_core.weather import fetch_weather, fetch_weather_alerts
from broadlinkac_core.typhoon import fetch_and_cache, judge_and_shutdown
from broadlinkac_core.logger import write_log

from .pyside.ac_tab import build_ac_tab, update_brand_logo
from .pyside.ty_tab import (
    build_ty_tab, render_weather, render_typhoon, render_alerts,
    _do_render_typhoon, _do_render_alerts,
)
from .pyside.dialogs import (
    open_settings, open_repair, open_log_dialog, edit_rules, edit_ty_alert,
    apply_theme,
)
from .pyside._utils import lbl

APP_NAME = "BroadlinkAC"
IS_MAC = platform.system() == "Darwin"
IS_WIN = platform.system() == "Windows"
_sched_lock = threading.Lock()


class App(QtWidgets.QMainWindow):
    _ui_signal = QtCore.Signal(object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME + "  v5.0")
        self.resize(865, 780)
        self.setMinimumSize(760, 650)

        self._ui_signal.connect(lambda fn: fn())

        self._temp_val = 26
        self._weather_data = None; self._alerts_data = []; self._alerts_provider = "baidu"
        self._ty_data = []; self._ty_page = 0; self._alert_page = 0
        self._ty_alert_muted = False; self._ty_ac_off_sent = False
        self._wx_timer_id = None; self._ty_timer_id = None

        self._build_menu_bar()
        self._setup_tray()

        central = QtWidgets.QWidget()
        central.setObjectName("central_bg")
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(12, 6, 12, 0); root.setSpacing(6)

        root.addLayout(self._build_device_bar())
        self._tab_widget = QtWidgets.QStackedWidget()
        self._tab_widget.addWidget(build_ac_tab(self))
        self._tab_widget.addWidget(build_ty_tab(self))
        root.addWidget(self._tab_widget, 1)

        # 底部自定义 Tab 栏
        self._build_bottom_tab_bar(root)
        self._build_status_bar()

        self._refresh_device_list()
        update_brand_logo(self)
        self._update_schedule_display()
        threading.Thread(target=self._init_data, daemon=True).start()
        QtCore.QTimer.singleShot(2000, self._scan_devices)
        QtCore.QTimer.singleShot(500, self._ty_fetch)

    def _ui(self, fn):
        """线程安全：将 fn 投递到主线程执行"""
        self._ui_signal.emit(fn)

    _GLOBAL_QSS = """
        * { font-family: "HarmonyOS Sans SC"; }
        QMainWindow { background: #F5F8FC; }
        QFrame#card {
            background: white;
            border: 1px solid #E5E7EB;
            border-radius: 12px;
        }
        QPushButton#primary {
            background: #2F80ED;
            color: white;
            border: none;
            border-radius: 12px;
            min-height: 36px;
            font-weight: bold;
            padding: 0 20px;
        }
        QPushButton#primary:hover { background: #3A8FFF; }
        QPushButton#primary:pressed { background: #1E6FD9; }
        QMenuBar {
            background: white;
            border-bottom: 1px solid #E5E7EB;
        }
        QMenuBar::item:selected {
            background: #E8F0FE;
        }
        QPushButton {
            min-height: 34px;
            border-radius: 12px;
            padding: 4px 14px;
            border: 1px solid #DEDEDE;
            background: #FAFAFA;
            color: #333;
        }
        QPushButton:hover {
            background: #F0F0F0;
            border-color: #CCC;
        }
        QPushButton:pressed {
            background: #E5E5E5;
        }
        QComboBox {
            min-height: 34px;
            border-radius: 10px;
            padding: 4px 12px;
            border: 1px solid #DEDEDE;
            background: #FAFAFA;
            color: #333;
        }
        QComboBox:hover {
            border-color: #BBB;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 28px;
            border-left: 1px solid #E5E7EB;
            border-top-right-radius: 10px;
            border-bottom-right-radius: 10px;
        }
        QComboBox QAbstractItemView {
            border: 1px solid #DEDEDE;
            border-radius: 10px;
            padding: 4px;
            background: white;
            selection-background-color: #E8F0FE;
            selection-color: #2F80ED;
            outline: none;
        }
    """

    # ===== 菜单 / 托盘 =====
    def _build_menu_bar(self):
        mb = self.menuBar()
        m = mb.addMenu("文件"); m.addAction("退出", self._on_exit)
        m = mb.addMenu("日志"); m.addAction("查看日志...", lambda: open_log_dialog(self))
        m = mb.addMenu("诊断"); m.addAction("故障诊断...", lambda: open_repair(self))
        m = mb.addMenu("设置"); m.addAction("设置...", lambda: open_settings(self))
        m = mb.addMenu("帮助")
        m.addAction("使用文档", self._open_docs)
        m.addSeparator()
        m.addAction("关于 BroadlinkAC", self._show_about)
        m.addAction("GitHub 主页", lambda: QtGui.QDesktopServices.openUrl(
            QtCore.QUrl("https://github.com/oywq00008-cell/BroadlinkAC-For-Agent")))

    def _setup_tray(self):
        if IS_MAC: return
        try:
            import pystray; from PIL import Image
            img = Image.open(self._get_asset("broadlink.png"))
            menu = pystray.Menu(
                pystray.MenuItem("显示", self._restore_from_tray, default=True),
                pystray.MenuItem("退出", self._quit_from_tray),
            )
            self._tray = pystray.Icon(APP_NAME, img, APP_NAME, menu)
            threading.Thread(target=self._tray.run, daemon=True).start()
        except: self._tray = None

    def _get_asset(self, filename):
        if getattr(sys, 'frozen', False): return Path(sys._MEIPASS) / filename
        return Path(__file__).resolve().parent.parent / filename

    def closeEvent(self, event):
        if IS_MAC: event.accept()
        else: self.hide(); event.ignore()

    def _restore_from_tray(self): self.show(); self.raise_(); self.activateWindow()
    def _quit_from_tray(self):
        import os, threading
        if hasattr(self, '_tray') and self._tray:
            self._tray.stop()
            self._tray = None
        # 0.3 秒后硬退 — 用 threading.Timer 避免依赖 Qt 事件循环
        threading.Timer(0.3, lambda: os._exit(0)).start()
    def _on_exit(self):
        if IS_MAC: self.close()
        else: self._quit_from_tray()

    # ===== 数据拉取 + 渲染 =====
    def _init_data(self):
        self._fetch_all()
        self._ui(self._render_all)
        self._ui(self._schedule_refresh)

    def _fetch_all(self):
        try:
            self._weather_data = fetch_weather()
            if self._weather_data:
                try: _cfg._cached_temp = float(self._weather_data["temp"])
                except: pass
            self._alerts_data, self._alerts_provider = fetch_weather_alerts()
        except Exception:
            self._weather_data = None; self._alerts_data, self._alerts_provider = [], "baidu"

    def _render_all(self):
        try: render_weather(self)
        except Exception as e: print(f"[渲染天气] {e}")
        try: render_alerts(self)
        except Exception as e: print(f"[渲染预警] {e}")
        try: self._update_alert_source()
        except Exception as e: print(f"[更新预警源] {e}")

    def _fetch_weather_all(self):
        threading.Thread(target=self._do_fetch_weather_all, daemon=True).start()

    def _do_fetch_weather_all(self):
        try:
            self._weather_data = fetch_weather()
            if self._weather_data:
                try: _cfg._cached_temp = float(self._weather_data["temp"])
                except: pass
            self._alerts_data, self._alerts_provider = fetch_weather_alerts()
        except Exception as e:
            print(f"[拉取天气] {e}")
        self._ui(lambda: render_weather(self))
        self._ui(lambda: render_alerts(self))
        self._ui(self._update_alert_source)
        self._ui(self._schedule_refresh)

    def _ty_fetch(self):
        threading.Thread(target=self._do_ty_fetch, daemon=True).start()

    def _do_ty_fetch(self):
        try:
            fetch_and_cache()
            from broadlinkac_core.typhoon import get_cached
            self._ty_data = get_cached()
        except: pass
        self._ui(self._ty_cycle_render)

    def _ty_cycle_render(self):
        try:
            render_typhoon(self)
            alerts, self._ty_ac_off_sent = judge_and_shutdown(
                write_log, self._ty_alert_muted, self._ty_ac_off_sent)
            for detail, dist in alerts: self._show_ty_alert(detail, dist)
        except Exception as e:
            write_log("系统", f"[台风周期] 异常: {e}")
        finally:
            self._schedule_ty_next()

    def _fetch_typhoon_all(self): self._ty_fetch()

    def _schedule_refresh(self):
        if self._wx_timer_id: self._wx_timer_id.stop()
        self._wx_timer_id = QtCore.QTimer.singleShot(
            10 * 60 * 1000, lambda: threading.Thread(target=self._init_data, daemon=True).start())

    def _schedule_ty_next(self):
        if self._ty_timer_id: self._ty_timer_id.stop()
        self._ty_timer_id = QtCore.QTimer.singleShot(30 * 60 * 1000, self._ty_fetch)

    # ===== 顶部工具栏 =====
    def _icon(self, name):
        """SVG 图标完整路径"""
        return str(Path(__file__).resolve().parent.parent / "icons" / name)

    def _build_device_bar(self):
        """返回 QHBoxLayout，直接铺在主窗口背景上（无独立容器）"""
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(8)

        # 设备图标 + 标签 + 选择器
        dev_icon = QtWidgets.QLabel()
        dev_icon.setPixmap(QtGui.QIcon(self._icon("device.svg")).pixmap(22, 22))
        layout.addWidget(dev_icon)
        layout.addWidget(QtWidgets.QLabel("设备:"))
        self._dev_combo = QtWidgets.QComboBox()
        self._dev_combo.setMinimumWidth(180)
        self._dev_combo.setFixedHeight(26)
        self._dev_combo.currentIndexChanged.connect(self._on_device_switch)
        layout.addWidget(self._dev_combo)

        # 重命名 / 删除 (纯图标按钮，无描边)
        btn = QtWidgets.QPushButton()
        btn.setIcon(QtGui.QIcon(self._icon("edit.svg")))
        btn.setIconSize(QtCore.QSize(20, 20))
        btn.setFixedSize(26, 26)
        btn.setFlat(True)
        btn.setToolTip("重命名设备")
        btn.setStyleSheet("""
            QPushButton { border:none; background:transparent; }
            QPushButton:hover { background:#E8F0FE; border-radius:4px; }
        """)
        btn.clicked.connect(self._rename_device)
        layout.addWidget(btn, alignment=QtCore.Qt.AlignTop)

        btn = QtWidgets.QPushButton()
        btn.setIcon(QtGui.QIcon(self._icon("delete_black.svg")))
        btn.setIconSize(QtCore.QSize(20, 20))
        btn.setFixedSize(26, 26)
        btn.setFlat(True)
        btn.setToolTip("删除设备")
        btn.setStyleSheet("""
            QPushButton { border:none; background:transparent; }
            QPushButton:hover { background:#E8F0FE; border-radius:4px; }
        """)
        btn.clicked.connect(self._delete_device)
        layout.addWidget(btn, alignment=QtCore.Qt.AlignTop)

        # 扫描按钮（纯图标）
        scan_btn = QtWidgets.QPushButton()
        scan_btn.setIcon(QtGui.QIcon(self._icon("scan.svg")))
        scan_btn.setIconSize(QtCore.QSize(20, 20))
        scan_btn.setFixedSize(26, 26)
        scan_btn.setFlat(True)
        scan_btn.setToolTip("扫描设备")
        scan_btn.setStyleSheet("""
            QPushButton { border:none; background:transparent; }
            QPushButton:hover { background:#E8F0FE; border-radius:4px; }
        """)
        scan_btn.clicked.connect(self._scan_devices)
        layout.addWidget(scan_btn, alignment=QtCore.Qt.AlignTop)

        layout.addStretch()

        # 连接状态
        self._conn_status = QtWidgets.QLabel("● 已连接")
        self._conn_status.setStyleSheet("""
            QLabel { color:#27AE60; font-weight:medium; border:1px solid #27AE60; border-radius:8px; padding:0px 8px; font-size:13px; max-height:17px; }
        """)
        layout.addWidget(self._conn_status)

        layout.addSpacing(20)

        # 最后更新时间
        from datetime import datetime
        self._update_time_lbl = QtWidgets.QLabel(f"最后更新：{datetime.now().strftime('%H:%M')}")
        self._update_time_lbl.setStyleSheet("color: #AAA;")
        layout.addWidget(self._update_time_lbl)

        # 刷新按钮
        refresh_btn = QtWidgets.QPushButton()
        refresh_btn.setIcon(QtGui.QIcon(self._icon("refresh.svg")))
        refresh_btn.setToolTip("全局刷新")
        refresh_btn.setFixedSize(30, 30)
        refresh_btn.clicked.connect(self._refresh_all_data)
        layout.addWidget(refresh_btn)

        return layout

    def _refresh_all_data(self):
        """一键刷新：天气 + 设备 + 台风"""
        self._update_time_lbl.setText("最后更新：⏳...")
        self._fetch_weather_all()
        self._scan_devices()
        self._ty_fetch()
        self._ui(lambda: self._update_time_lbl.setText(
            f"最后更新：{__import__('datetime').datetime.now().strftime('%H:%M')}"))

    def _build_bottom_tab_bar(self, root_layout):
        """底部自定义 Tab 栏（两个按钮填满整行）"""
        bar = QtWidgets.QWidget()
        bl = QtWidgets.QHBoxLayout(bar)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(4)

        TAB_QSS = """
            QPushButton {
                padding: 6px 0px;
                font-size: 14px;
                font-weight: 500;
                border: 1px solid #E5E7EB;
                border-radius: 10px;
                background: #F1F5F9;
                color: #666;
            }
            QPushButton:checked {
                background: white;
                color: #2F80ED;
                font-weight: bold;
                border: 1px solid #2F80ED;
            }
        """

        self._tab_btns = []
        for i, text in enumerate(["🎮  空调控制", "⚠  预警信息"]):
            btn = QtWidgets.QPushButton(text)
            btn.setObjectName("tab_btn")
            btn.setCheckable(True)
            btn.setStyleSheet(TAB_QSS)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i: self._switch_tab(idx))
            bl.addWidget(btn)
            self._tab_btns.append(btn)
        self._tab_btns[0].setChecked(True)
        root_layout.addWidget(bar)

    def _switch_tab(self, idx):
        self._tab_widget.setCurrentIndex(idx)
        for i, btn in enumerate(self._tab_btns):
            btn.setChecked(i == idx)

    def _build_status_bar(self):
        """底部状态栏：● 运行正常 | 版本号"""
        sb = self.statusBar()
        sb.setObjectName("status_bar")
        sb.setStyleSheet("QStatusBar { background:#F8FAFC; border-top:1px solid #E5E7EB; }")
        status_label = QtWidgets.QLabel("● 运行正常")
        status_label.setStyleSheet("color:#27AE60; font-weight:bold;")
        status_label.setProperty("status_label_kind", "ok")
        self._status_label = status_label
        sb.addWidget(status_label)
        self._version_label = QtWidgets.QLabel("当前版本：v5.0")
        self._version_label.setStyleSheet("color:#999;")
        self._version_label.setProperty("status_label_kind", "version")
        sb.addPermanentWidget(self._version_label)

    # ===== 温度 / 发送 =====
    def _temp_down(self):
        if self._temp_val > 16: self._temp_val -= 1; self._temp_lbl.setText(f"{self._temp_val}°C")
    def _temp_up(self):
        if self._temp_val < 30: self._temp_val += 1; self._temp_lbl.setText(f"{self._temp_val}°C")

    def _on_send_click(self):
        self._status_label.setText("⏳ 发送中...")
        self._status_label.setStyleSheet("color:#E67E22; font-weight:bold;")
        power = "on" if self._power_sw.isChecked() else "off"
        mode = MODES[self._mode_cb.currentText()]
        fan = FANS[self._fan_cb.currentText()]
        temp = self._temp_val
        threading.Thread(target=lambda: self._do_send(power, mode, temp, fan), daemon=True).start()

    def _do_send(self, power, mode, temp, fan):
        def _restore():
            self._status_label.setText("● 运行正常")
            self._status_label.setStyleSheet("color:#27AE60; font-weight:bold;")
        try:
            result = send_ac(power, mode, temp, fan, source="手动")
            write_log("空调", result)
            self._ui(lambda: self._status_label.setText(f"✅ {result}"))
        except Exception as e:
            err = str(e)
            write_log("系统", f"发送失败: {err}")
            self._ui(lambda: [self._status_label.setText(f"❌ {err}"),
                              self._status_label.setStyleSheet("color:#E74C3C; font-weight:bold;"),
                              QtCore.QTimer.singleShot(500, lambda: self._ask_repair(err))])
        self._ui(lambda: QtCore.QTimer.singleShot(2000, _restore))

    def _ask_repair(self, err_msg):
        if QtWidgets.QMessageBox.question(self, "发送失败",
            f"{err_msg}\n\n是否进入修复程序？") == QtWidgets.QMessageBox.Yes:
            open_repair(self)

    def _update_schedule_display(self):
        from .pyside.ac_tab import _update_schedule_display
        _update_schedule_display(self)

    def _save_adjust(self):
        _cfg.config["auto_adjust"] = self._adjust_sw.isChecked()
        save_config(_cfg.config)
        with _sched_lock: register_all_jobs()
        write_log("系统", f"自动调温: {'已开启' if _cfg.config['auto_adjust'] else '已关闭'}")
        status = "✅ 自动调温: 已开启" if _cfg.config['auto_adjust'] else "❌ 自动调温: 已关闭"
        self.statusBar().showMessage(status, 2000)

    # ===== 规则 =====
    def _refresh_rules_display(self):
        from broadlinkac_core.ac_control import MODE_KEYS
        rules = _cfg.config.get("temp_rules", [
            [36,99,24,"cool"],[33,35,25,"cool"],[30,32,26,"cool"],
            [25,29,27,"cool"],[18,24,0,"off"],[0,17,28,"heat"]
        ])
        self._rules_table.setRowCount(len(rules))
        for i, (low, high, target, mode) in enumerate(rules):
            range_item = QtWidgets.QTableWidgetItem(f"{low}°C ~ {high}°C")
            range_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self._rules_table.setItem(i, 0, range_item)
            if mode == "off":
                action_item = QtWidgets.QTableWidgetItem("⚡ 关闭")
            else:
                action_item = QtWidgets.QTableWidgetItem(
                    f"{'❄️' if mode=='cool' else '🔥'} {MODE_KEYS.get(mode,mode)} {target}°C")
            action_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self._rules_table.setItem(i, 1, action_item)
    def _edit_rules(self): edit_rules(self)

    # ===== 设备管理 =====
    def _refresh_device_list(self):
        self._dev_combo.blockSignals(True); self._dev_combo.clear()
        for mac, name in get_device_list():
            label = name + (" (离线)" if _cfg._online_macs and mac not in _cfg._online_macs else "")
            self._dev_combo.addItem(label, userData=mac)
        cur = _cfg.config.get("current_device_mac","")
        for i in range(self._dev_combo.count()):
            if self._dev_combo.itemData(i) == cur: self._dev_combo.setCurrentIndex(i); break
        self._dev_combo.blockSignals(False)

    def _on_device_switch(self, idx):
        if idx < 0: return
        mac = self._dev_combo.itemData(idx)
        if mac and hasattr(self, '_ctrl_title'):
            switch_device(mac); save_config(_cfg.config); self._refresh_device_ui()
            dev = get_current_device()
            write_log("系统", f"切换设备 → {dev.get('name', mac[:8])}")

    def _refresh_device_ui(self):
        dev = get_current_device()
        update_brand_logo(self)
        self._fan_cb.setCurrentText({v:k for k,v in FANS.items()}.get(dev.get("fan","auto"),"自动"))
        self._adjust_sw.setChecked(dev.get("auto_adjust",True))
        self._update_schedule_display()

    def _scan_devices(self):
        self._conn_status.setText("● 扫描中")
        self._conn_status.setStyleSheet(
            "QLabel { color:#E67E22; font-weight:medium; border:1px solid #E67E22; border-radius:8px; padding:0px 8px; font-size:13px; max-height:17px; }")
        threading.Thread(target=self._do_scan_devices, daemon=True).start()

    def _do_scan_devices(self):
        try:
            devices = discover_devices(timeout=5)
        except Exception as e:
            write_log("系统", f"设备扫描异常: {e}")
            self._ui(lambda: self._conn_status.setText("● 未连接"))
            self._ui(lambda: self._conn_status.setStyleSheet(
                "QLabel { color:#E74C3C; font-weight:bold; border:1px solid #E74C3C; border-radius:7px; padding:0px 8px; font-size:12px; max-height:16px; }"))
            self._ui(lambda: self.statusBar().showMessage(f"❌ 扫描异常: {e}", 4000))
            return
        if not devices:
            write_log("系统", "设备扫描: 未发现设备")
            _cfg._online_macs = set()
            self._ui(lambda: self._conn_status.setText("● 未连接"))
            self._ui(lambda: self._conn_status.setStyleSheet(
                "QLabel { color:#E74C3C; font-weight:bold; border:1px solid #E74C3C; border-radius:7px; padding:0px 8px; font-size:12px; max-height:16px; }"))
            self._ui(self._refresh_device_list)
            self._ui(lambda: self.statusBar().showMessage("❌ 未发现设备", 4000))
            return
        online = set()
        for d in devices:
            mac = d.mac.hex() if isinstance(d.mac, bytes) else str(d.mac)
            online.add(mac)
            add_or_update_device(mac, {
                "host": d.host[0] if isinstance(d.host, tuple) else str(d.host),
                "port": d.host[1] if isinstance(d.host, tuple) and len(d.host) > 1 else 80,
                "mac": mac, "model": d.model, "name": d.model or d.name,
            })
        save_config(_cfg.config)
        _cfg._online_macs = online
        count = len(devices)
        write_log("系统", f"设备扫描完成: 发现 {count} 个设备")
        self._ui(self._refresh_device_list)
        self._ui(self._refresh_device_ui)
        self._ui(register_all_jobs)
        self._ui(lambda: self._conn_status.setText("● 已连接"))
        self._ui(lambda: self._conn_status.setStyleSheet(
            "QLabel { color:#27AE60; font-weight:medium; border:1px solid #27AE60; border-radius:8px; padding:0px 8px; font-size:13px; max-height:17px; }"))
        self._ui(lambda: self.statusBar().showMessage(f"✅ 发现 {count} 个设备", 4000))

    def _rename_device(self):
        mac = _cfg.config.get("current_device_mac","")
        if not mac: return
        dev = get_current_device(); old = dev.get("name",mac[:8])
        from .pyside.dialogs import open_rename_device
        new_name = open_rename_device(self, old, mac)
        if new_name and new_name != old:
            _cfg.config.setdefault("devices",{}).setdefault(mac,{})["name"] = new_name
            _cfg.config["name"] = new_name; save_config(_cfg.config); self._refresh_device_list()
            write_log("系统", f"设备重命名: {old} → {new_name}")

    def _delete_device(self):
        mac=_cfg.config.get("current_device_mac","")
        devs=_cfg.config.get("devices",{})
        name = devs.get(mac,{}).get('name', mac[:8])
        if not mac or len(devs)<=1:
            from .pyside.dialogs import open_delete_device
            open_delete_device(self, allow=False); return
        from .pyside.dialogs import open_delete_device
        if open_delete_device(self, name=name):
            del devs[mac]; _cfg.config["current_device_mac"]=next(iter(devs))
            switch_device(_cfg.config["current_device_mac"]); save_config(_cfg.config)
            self._refresh_device_list(); self._refresh_device_ui(); register_all_jobs()
            write_log("系统", f"已删除设备: {name}")

    # ===== 台风/预警 UI 更新 =====
    def _update_alert_source(self):
        self._alert_source_label.setText(
            "数据: 百度天气" if self._alerts_provider=="baidu" else "数据: 和风天气")
    def _update_ty_source_label(self):
        provider=_cfg.config.get("typhoon_provider","nmc")
        if provider=="nhc":
            self._ty_source_label.setText("数据: 美国国家飓风中心 (NHC)")
            self._ty_provider_cb.setCurrentText("北大西洋飓风")
        else:
            self._ty_source_label.setText("数据: 中国中央气象台 (NMC)")
            self._ty_provider_cb.setCurrentText("西北太平洋台风")
    def _on_ty_provider_change(self, txt):
        _cfg.config["typhoon_provider"]="nhc" if "飓风" in txt else "nmc"
        save_config(_cfg.config,sync_device=False); self._update_ty_source_label(); self._ty_fetch()
    def _ty_prev_page(self):
        if self._ty_page>0: self._ty_page-=1; _do_render_typhoon(self)
    def _ty_next_page(self): self._ty_page+=1; _do_render_typhoon(self)
    def _alert_prev_page(self):
        if self._alert_page>0: self._alert_page-=1; _do_render_alerts(self)
    def _alert_next_page(self): self._alert_page+=1; _do_render_alerts(self)
    def _show_ty_alert(self, detail, dist):
        QtWidgets.QMessageBox.warning(self,"⚠️ 台风预警",
            f"{detail}\n\n距离约 {dist}km\n\n请密切关注风暴动态！")
        self._ty_alert_muted = True
        write_log("台风", "预警已静音")
    def _edit_ty_alert(self): edit_ty_alert(self)
    def _update_ty_status(self):
        km=_cfg.config.get("typhoon_alert_km",800)
        self._ty_status_label.setText(
            f"风暴预警距离 {km}km 生效中" if _cfg.config.get("typhoon_alert_enabled",True)
            else f"风暴预警距离 {km}km (提醒已关)")
    def _on_ac_off_toggle(self):
        if self._ty_ac_off_sw.isChecked():
            _cfg.config["typhoon_ac_off"]=True; save_config(_cfg.config)
            write_log("台风", "风暴自动关空调: 已开启")
        else:
            if QtWidgets.QMessageBox.question(self,"⚠️ 安全警示",
                "当风暴<100km时，说明你可能正处于风暴的核心影响圈，\n"
                "此时大风可能会让空调外机倒转导致烧毁，\n"
                "雷暴有可能击毁正在运行的空调硬件。\n\n"
                "When the storm is within 100km, you may be in its core impact zone.\n"
                "Strong winds can cause the outdoor unit to reverse and burn out,\n"
                "and thunderstorms may damage running AC hardware.\n\n"
                "确定关闭吗？ / Confirm to disable?"
            )!=QtWidgets.QMessageBox.Yes:
                self._ty_ac_off_sw.setChecked(True); return
            _cfg.config["typhoon_ac_off"]=False; save_config(_cfg.config)
            write_log("台风", "风暴自动关空调: 已关闭")
    def _open_zoom_earth(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(
            f"https://zoom.earth/#view={_cfg.LOCATION['lat']},{_cfg.LOCATION['lon']},8z"))

    # ===== 帮助 =====
    def _open_docs(self):
        doc = self._get_asset("使用文档.md")
        if os.name=="nt": os.startfile(str(doc))
        else: __import__("subprocess").run(["open",str(doc)])
    def _show_about(self):
        from .pyside.dialogs import open_about
        open_about(self)


def main():
    from broadlinkac_core import init; init()
    app = QtWidgets.QApplication(sys.argv); app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    # 加载内置字体
    fonts_dir = Path(__file__).resolve().parent.parent / "fonts"
    for fname in ["HarmonyOS_Sans_SC_Regular.ttf", "NotoColorEmoji-Regular.ttf"]:
        fp = fonts_dir / fname
        if fp.exists():
            QtGui.QFontDatabase.addApplicationFont(str(fp))
    apply_theme()
    win = App(); win.show()
    apply_theme()  # 第二次调用：刷新已创建的 widgets（central_bg 等）
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
