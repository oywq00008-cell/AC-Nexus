"""故障诊断对话框 — 检测 Python 环境、依赖、设备连接、网络、API"""
import json
import socket
import ssl
import subprocess
import sys
import threading
import urllib.request

from PySide6 import QtCore, QtWidgets

import acnexus_core.config as _cfg
from acnexus_core.config import save_config
from acnexus_core.ac_control import discover_devices
from ._utils import lbl


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
        import platform

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
        from acnexus_core.config import get_current_device, add_or_update_device
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
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request("https://www.baidu.com", headers={"User-Agent": "AC-Nexus/5.0"})
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

        # ── 和风天气 API ──
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
                import gzip
                ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(url, headers={"User-Agent": "AC-Nexus/2.0"})
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
                ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(url, headers={"User-Agent": "AC-Nexus/2.0"})
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
