"""米家设备选择弹窗 — 云拉取设备列表，勾选添加"""
import sys
import json
import time
import threading
import requests

from PySide6 import QtCore, QtGui, QtWidgets

from ._utils import lbl, is_dark


def _make_draggable(title_bar, dlg):
    """让标题栏可拖拽移动窗口"""
    def press(e):
        if e.button() == QtCore.Qt.LeftButton:
            title_bar._drag_start = e.globalPosition().toPoint() - dlg.frameGeometry().topLeft()
    def move(e):
        if hasattr(title_bar, '_drag_start'):
            dlg.move(e.globalPosition().toPoint() - title_bar._drag_start)
    title_bar.mousePressEvent = press
    title_bar.mouseMoveEvent = move


class _PickerSignals(QtCore.QObject):
    build = QtCore.Signal(list)
    error = QtCore.Signal(str)
    empty = QtCore.Signal()


def _fetch_cloud_devices(session_dict: dict) -> list[dict]:
    """用云 session 拉取设备列表 → [{did, name, ip, token, model, mac}, ...]"""
    import sys, traceback
    from acnexus_core.xiaomi_cloud import (
        generate_nonce, signed_nonce, encrypt_rc4, decrypt_rc4,
        generate_enc_signature,
    )
    ssecurity = session_dict["ssecurity"]
    serviceToken = session_dict["serviceToken"]
    userId = session_dict["userId"]

    sess = requests.Session()

    def call_encrypted(url, data_dict):
        millis = round(time.time() * 1000)
        nonce = generate_nonce(millis)
        snonce = signed_nonce(ssecurity, nonce)
        params = {"data": json.dumps(data_dict)}
        sign = generate_enc_signature(url, "POST", snonce, params)
        params["rc4_hash__"] = sign
        for k, v in params.items():
            params[k] = encrypt_rc4(snonce, v)
        fields = {
            **params,
            "signature": generate_enc_signature(url, "POST", snonce, params),
            "ssecurity": ssecurity,
            "_nonce": nonce,
        }
        print(f"[DEVFETCH] POST {url.split('/app')[-1]} data={json.dumps(data_dict)[:100]}", file=sys.stderr)
        r = sess.post(url, params=fields, headers={
            "Accept-Encoding": "identity",
            "User-Agent": "APP/com.xiaomi.mihome",
            "Content-Type": "application/x-www-form-urlencoded",
            "x-xiaomi-protocal-flag-cli": "PROTOCAL-HTTP2",
            "MIOT-ENCRYPT-ALGORITHM": "ENCRYPT-RC4",
        }, cookies={
            "userId": str(userId),
            "yetAnotherServiceToken": str(serviceToken),
            "serviceToken": str(serviceToken),
            "locale": "en_GB",
            "timezone": "GMT+02:00",
            "is_daylight": "1",
            "dst_offset": "3600000",
            "channel": "MI_APP_STORE",
        })
        dec = decrypt_rc4(signed_nonce(ssecurity, fields["_nonce"]), r.text)
        jr = json.loads(dec)
        code = jr.get("code", "?")
        dev_count = len(jr.get("result", {}).get("device_info", []))
        print(f"[DEVFETCH]   HTTP {r.status_code} code={code} devices={dev_count}", file=sys.stderr)
        if code != 0:
            print(f"[DEVFETCH]   resp={json.dumps(jr, ensure_ascii=False)[:300]}", file=sys.stderr)
        return jr

    # 拉取家庭列表
    api_base = "https://api.io.mi.com/app"
    homes_resp = call_encrypted(
        api_base + "/v2/homeroom/gethome",
        {"fg": True, "fetch_share": True, "fetch_share_dev": True, "limit": 300, "app_ver": 7},
    )
    home_list = homes_resp.get("result", {}).get("homelist", [])
    parts = homes_resp.get("result", {}).get("partition", [])
    if not home_list:
        home_list = [item for p in parts for item in p.get("homelist", [])]

    # 拉每个家庭的设备
    devices = []
    seen = set()
    for home in home_list:
        home_id = home.get("id") or home.get("home_id")
        if not home_id:
            continue
        resp = call_encrypted(
            api_base + "/v2/home/home_device_list",
            {
                "home_owner": userId,
                "home_id": home_id,
                "home_id": home_id,
                "limit": 200,
                "get_split_device": True,
                "support_smart_home": True,
            },
        )
        dev_list = resp.get("result", {}).get("device_info") or resp.get("result", {}).get("list") or []
        for dev in dev_list:
            did = str(dev.get("did", ""))
            if not did or did in seen:
                continue
            seen.add(did)
            devices.append({
                "did": did,
                "name": dev.get("name", ""),
                "ip": dev.get("localip", ""),
                "token": dev.get("token", ""),
                "model": dev.get("model", ""),
                "mac": dev.get("mac", ""),
            })
    return devices


def open_xiaomi_device_picker(parent, session_dict: dict) -> list[str]:
    """
    弹出设备选择弹窗，返回用户选中的 [did, ...] 列表。
    session_dict: 来自 login() 的 {ssecurity, serviceToken, userId}
    """
    import acnexus_core.config as _cfg

    dlg = QtWidgets.QDialog(parent, QtCore.Qt.FramelessWindowHint if sys.platform == "win32" else QtCore.Qt.Dialog)
    if sys.platform == "win32":
        dlg.setAttribute(QtCore.Qt.WA_TranslucentBackground)
    dlg.setWindowModality(QtCore.Qt.WindowModal)
    dlg.setWindowTitle("选择米家设备")
    dlg.resize(440, 420)  # 额外空间给阴影

    dark = is_dark()
    bg = "#2D2D2D" if dark else "white"
    bd = "#444" if dark else "#DEDEDE"
    fg = "#EEE" if dark else "#333"

    outer = QtWidgets.QFrame(dlg)
    outer.setObjectName("xiaomi_picker_outer")
    outer.setStyleSheet(f"QFrame#xiaomi_picker_outer {{ background:{bg}; border:1px solid {bd}; border-radius:12px; }}")
    if sys.platform == "win32":
        shadow = QtWidgets.QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 2)
        shadow.setColor(QtGui.QColor(0, 0, 0, 80))
        outer.setGraphicsEffect(shadow)
    ov = QtWidgets.QVBoxLayout(outer); ov.setContentsMargins(0, 0, 0, 0); ov.setSpacing(0)

    # 标题栏
    tb = QtWidgets.QWidget(); tb.setFixedHeight(36)
    tb.setStyleSheet(f"background: transparent; border-bottom: 1px solid {bd};")
    tl = QtWidgets.QHBoxLayout(tb); tl.setContentsMargins(16, 0, 8, 0)
    tl.addWidget(lbl("选择米家设备", bold=True, size=13)); tl.addStretch()
    close = QtWidgets.QPushButton("✕"); close.setFixedSize(28, 28); close.setFlat(True)
    close.setStyleSheet(
        f"QPushButton {{ font-size:14px; color:{'#AAA' if dark else '#888'}; "
        f"border:none; background:transparent; }} "
        f"QPushButton:hover {{ background:{'#444' if dark else '#F0F0F0'}; border-radius:4px; }}")
    close.clicked.connect(dlg.reject)
    tl.addWidget(close)
    _make_draggable(tb, dlg)
    ov.addWidget(tb)

    # 内容区
    body = QtWidgets.QVBoxLayout(); body.setContentsMargins(20, 12, 20, 12); body.setSpacing(8)

    # 加载提示
    loading = QtWidgets.QLabel("正在获取设备列表...")
    loading.setStyleSheet(f"color: {'#AAA' if dark else '#888'}; font-size: 13px;")
    loading.setAlignment(QtCore.Qt.AlignCenter)
    body.addWidget(loading)

    # 设备列表区域（滚动）
    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
    scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    scroll_widget = QtWidgets.QWidget()
    scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)
    scroll_layout.setSpacing(4)
    scroll_layout.setContentsMargins(0, 0, 0, 0)
    scroll.setWidget(scroll_widget)
    scroll.setVisible(False)
    body.addWidget(scroll)

    # 全选/取消
    toggle_row = QtWidgets.QHBoxLayout()
    toggle_row.setContentsMargins(0, 0, 0, 0)
    toggle_btn = QtWidgets.QPushButton("全选")
    toggle_btn.setFlat(True)
    toggle_btn.setStyleSheet(f"QPushButton {{ color: #1677FF; font-size: 12px; border: none; }}")
    toggle_row.addWidget(toggle_btn)
    toggle_row.addStretch()
    txt_hint = QtWidgets.QLabel("已添加的设备默认勾选")
    txt_hint.setStyleSheet(f"color: {'#AAA' if dark else '#888'}; font-size: 11px;")
    toggle_row.addWidget(txt_hint)
    toggle_widget = QtWidgets.QWidget()
    toggle_widget.setLayout(toggle_row)
    toggle_widget.setVisible(False)
    body.addWidget(toggle_widget)

    body.addStretch()

    # 错误提示
    error_label = QtWidgets.QLabel("")
    error_label.setStyleSheet("color: #E74C3C; font-size: 12px;")
    error_label.setVisible(False)
    error_label.setWordWrap(True)
    body.addWidget(error_label)

    # 确定按钮
    btn_row = QtWidgets.QHBoxLayout(); btn_row.addStretch()
    ok_btn = QtWidgets.QPushButton("添加到 AC-Nexus")
    ok_btn.setFixedSize(160, 34)
    ok_btn.setStyleSheet("""
        QPushButton {
            background: #1677FF; color: white; border: none; border-radius: 6px;
            font-size: 13px; font-weight: bold;
        }
        QPushButton:hover { background: #4096FF; }
        QPushButton:disabled { background: #7EB8FF; }
    """)
    ok_btn.setVisible(False)
    btn_row.addWidget(ok_btn); btn_row.addStretch()
    body.addLayout(btn_row)

    ov.addLayout(body)
    full = QtWidgets.QVBoxLayout(dlg); full.setContentsMargins(10 if sys.platform == "win32" else 0, 10 if sys.platform == "win32" else 0, 10 if sys.platform == "win32" else 0, 10 if sys.platform == "win32" else 0); full.addWidget(outer)

    # ── 状态 ──
    checkboxes = []          # [(QCheckBox, device_dict), ...]
    result_dids = []         # 选中的 did 列表

    def build_device_list(devices):
        """设备列表填到 UI"""
        nonlocal checkboxes
        for cb, _ in checkboxes:
            cb.deleteLater()
        checkboxes.clear()

        # 先清空 scroll 内所有控件
        while scroll_layout.count():
            item = scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        existed = set(device_id for device_id, _ in _cfg.get_device_list(brand_type="xiaomi_cloud"))

        for dev in devices:
            row = QtWidgets.QCheckBox()
            info_parts = [dev["name"]]
            if dev["model"]:
                info_parts.append(dev["model"])
            if dev["ip"]:
                info_parts.append(dev["ip"])
            row.setText("  │  ".join(info_parts))
            row.setStyleSheet(f"""
                QCheckBox {{ color: {fg}; font-size: 13px; spacing: 8px; padding: 4px 0; }}
                QCheckBox::indicator {{ width: 16px; height: 16px; }}
            """)
            if dev["did"] in existed:
                row.setChecked(True)
                row.setEnabled(False)
                row.setText(row.text() + "  (已添加)")
            checkboxes.append((row, dev))
            scroll_layout.addWidget(row)

        scroll_layout.addStretch()
        loading.setVisible(False)
        scroll.setVisible(True)
        toggle_widget.setVisible(True)
        ok_btn.setVisible(True)

    def on_toggle():
        all_checked = all(cb.isChecked() for cb, _ in checkboxes if cb.isEnabled())
        new_state = not all_checked
        for cb, _ in checkboxes:
            if cb.isEnabled():
                cb.setChecked(new_state)
        toggle_btn.setText("取消全选" if new_state else "全选")

    def on_ok():
        nonlocal result_dids
        result_dids = [dev["did"] for cb, dev in checkboxes if cb.isChecked()]
        for dev in (d for _, d in checkboxes if d["did"] in result_dids):
            _cfg.add_or_update_device(dev["did"], {
                "did": dev["did"],
                "host": dev["ip"],
                "mac": dev["mac"],
                "model": dev["model"],
                "name": dev["name"],
                "brand": "格力",
                "token": dev.get("token", ""),
            })
        _cfg.save_config(_cfg.config, sync_device=False)
        dlg.accept()

    toggle_btn.clicked.connect(on_toggle)
    ok_btn.clicked.connect(on_ok)

    signals = _PickerSignals()

    def fetch_worker():
        try:
            devices = _fetch_cloud_devices(session_dict)
            if not devices:
                signals.empty.emit()
                return
            signals.build.emit(devices)
        except Exception as e:
            import traceback, sys
            print(f"[PICKER] {traceback.format_exc()}", file=sys.stderr)
            signals.error.emit(str(e))

    signals.build.connect(build_device_list)
    signals.empty.connect(lambda: (
        loading.setVisible(False),
        error_label.setText("未发现任何设备，请确认账号下已绑定米家设备"),
        error_label.setVisible(True),
    ))
    signals.error.connect(lambda msg: (
        loading.setVisible(False),
        error_label.setText(f"获取失败：{msg}"),
        error_label.setVisible(True),
    ))

    threading.Thread(target=fetch_worker, daemon=True).start()

    dlg.exec()
    return result_dids
