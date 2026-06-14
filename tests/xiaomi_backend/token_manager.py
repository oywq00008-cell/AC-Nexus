"""小米设备 Token 管理 — 扫码登录 + 钥匙串存储

集成到主项目后:
    from broadlinkac_core.xiaomi import token_manager
    token = token_manager.get_token(device_id)
    if not token:
        token = token_manager.qr_login()  # 弹窗/终端扫码
"""

import json
import threading
import time
import keyring
from pathlib import Path
from colorama import Fore, Style

SERVICE_NAME = "BroadlinkAC"
KEY_PREFIX = "mi_token_"

# ── Token 存取 ──

def get_token(device_id: str) -> str | None:
    """从系统钥匙串读取 token，没有则返回 None"""
    return keyring.get_password(SERVICE_NAME, f"{KEY_PREFIX}{device_id}")


def store_token(device_id: str, token: str):
    """保存 token 到系统钥匙串（Windows: 凭据管理器 / macOS: Keychain）"""
    keyring.set_password(SERVICE_NAME, f"{KEY_PREFIX}{device_id}", token)


def delete_token(device_id: str):
    """删除 token（设备解绑时调用）"""
    try:
        keyring.delete_password(SERVICE_NAME, f"{KEY_PREFIX}{device_id}")
    except keyring.errors.PasswordDeleteError:
        pass


def list_stored_devices() -> list[dict]:
    """列出钥匙串中已保存的米家设备
    注意：keyring 不直接支持列出所有凭据，这是跨平台近似实现
    """
    # 从 config.json 读取已配置的米家设备，检查是否有相应 token
    from broadlinkac_core.config import config
    result = []
    for mac, dev in config.get("devices", {}).items():
        if dev.get("type") == "xiaomi":
            did = dev.get("did", mac)
            token = get_token(did)
            result.append({
                "mac": mac, "did": did,
                "name": dev.get("name", mac[:8]),
                "has_token": token is not None,
            })
    return result


# ── 二维码登录 ──

def _get_connector():
    """延迟导入，避免主项目无依赖时崩溃"""
    from token_extractor import QrCodeXiaomiCloudConnector
    return QrCodeXiaomiCloudConnector()


def qr_login_gui(parent) -> dict:
    """GUI 模式：在 PySide6 弹窗中显示二维码
    parent: QMainWindow 实例
    返回: {device_id: {name, ip, token, model}}
    """
    from PySide6 import QtCore, QtGui, QtWidgets

    result = {}
    c = _get_connector()

    # Step 1: 获取二维码
    if not c.login_step_1():
        raise RuntimeError("无法获取二维码")

    img_bytes = c._session.get(c._qr_image_url).content

    # Step 2: 弹窗显示
    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle("米家扫码登录")
    dlg.setFixedSize(350, 420)
    dlg.setModal(True)

    layout = QtWidgets.QVBoxLayout(dlg)

    hint = QtWidgets.QLabel("请用米家 APP 扫描下方二维码")
    hint.setAlignment(QtCore.Qt.AlignCenter)
    hint.setStyleSheet("font-size:14px; font-weight:bold;")
    layout.addWidget(hint)

    qr_label = QtWidgets.QLabel()
    pix = QtGui.QPixmap()
    pix.loadFromData(img_bytes)
    qr_label.setPixmap(pix.scaled(280, 280, QtCore.Qt.KeepAspectRatio))
    qr_label.setAlignment(QtCore.Qt.AlignCenter)
    layout.addWidget(qr_label)

    status = QtWidgets.QLabel("等待扫码...")
    status.setAlignment(QtCore.Qt.AlignCenter)
    status.setStyleSheet("color:#E67E22;")
    layout.addWidget(status)

    dlg.show()

    # Step 3: 后台长轮询等扫码
    login_ok = threading.Event()
    login_error = threading.Event()

    def do_poll():
        try:
            if c.login_step_3() and c.login_step_4():
                login_ok.set()
            else:
                login_error.set()
        except Exception:
            login_error.set()

    threading.Thread(target=do_poll, daemon=True).start()

    # Step 4: 等结果（最长 5 分钟）
    timer = QtCore.QTimer()
    timer.setInterval(200)

    def check():
        if login_ok.is_set():
            timer.stop()
            status.setText("扫码成功！正在获取设备列表...")
            QtCore.QTimer.singleShot(300, lambda: _fetch_and_close(
                c, result, dlg, status))
        elif login_error.is_set():
            timer.stop()
            status.setText("登录失败，请重试")
            status.setStyleSheet("color:#E74C3C;")

    timer.timeout.connect(check)
    timer.start()

    dlg.exec()
    return result


def _fetch_and_close(c, result, dlg, status):
    """扫码后拉取设备列表并存入钥匙串"""
    try:
        for srv in ["cn"]:
            homes = c.get_homes(srv)
            if not homes:
                continue
            for h in homes.get("result", {}).get("homelist", []):
                devs = c.get_devices(srv, h["id"], c.userId)
                info = devs.get("result", {}).get("device_info", []) if devs else []
                for d in info:
                    did = d.get("did", "?")
                    token = d.get("token", "")
                    if token:
                        store_token(did, token)
                        result[did] = {
                            "name": d.get("name", "?"),
                            "ip": d.get("localip", ""),
                            "token": token,
                            "model": d.get("model", "?"),
                            "mac": d.get("mac", ""),
                        }
        status.setText(f"✅ 已保存 {len(result)} 个设备的 Token")
        status.setStyleSheet("color:#27AE60; font-size:14px;")
    except Exception as e:
        status.setText(f"获取设备列表失败: {e}")
        status.setStyleSheet("color:#E74C3C;")
    finally:
        QtCore.QTimer.singleShot(1500, dlg.accept)


def qr_login_terminal() -> dict:
    """终端模式：ASCII 二维码（Agent / SSH / 无 GUI 环境）
    返回: {device_id: {name, ip, token, model}}
    """
    from io import BytesIO
    import qrcode, qrcode_terminal

    print(f"\n{Fore.YELLOW}=== 米家扫码登录 ==={Style.RESET_ALL}\n")

    c = _get_connector()
    if not c.login_step_1():
        raise RuntimeError("无法获取二维码")

    # 终端画 ASCII 二维码
    img_bytes = c._session.get(c._qr_image_url).content
    qr_img = qrcode.make(c._login_url)
    qrcode_terminal.draw(qr_img)

    print(f"{Fore.CYAN}如果二维码不清晰，请用浏览器打开:{Style.RESET_ALL}")
    print(f"  {c._login_url}\n")
    print(f"{Fore.YELLOW}用米家 APP 扫码，等待确认...{Style.RESET_ALL}")

    if not c.login_step_3():
        print(f"{Fore.RED}登录失败{Style.RESET_ALL}")
        return {}
    if not c.login_step_4():
        print(f"{Fore.RED}获取 token 失败{Style.RESET_ALL}")
        return {}

    print(f"{Fore.GREEN}✅ 登录成功！正在拉取设备...{Style.RESET_ALL}\n")

    result = {}
    for srv in ["cn"]:
        homes = c.get_homes(srv)
        if not homes:
            continue
        for h in homes.get("result", {}).get("homelist", []):
            devs = c.get_devices(srv, h["id"], c.userId)
            info = devs.get("result", {}).get("device_info", []) if devs else []
            for d in info:
                did = d.get("did", "?")
                token = d.get("token", "")
                if token:
                    store_token(did, token)
                    result[did] = {
                        "name": d.get("name", "?"),
                        "ip": d.get("localip", ""),
                        "token": token,
                        "model": d.get("model", "?"),
                        "mac": d.get("mac", ""),
                    }
                    print(f"  {Fore.CYAN}{d.get('name','?')}{Style.RESET_ALL}")
                    print(f"    Token: {Fore.GREEN}{token}{Style.RESET_ALL} → 已存钥匙串")

    print(f"\n{Fore.GREEN}共 {len(result)} 个设备已保存到系统钥匙串{Style.RESET_ALL}")
    return result
