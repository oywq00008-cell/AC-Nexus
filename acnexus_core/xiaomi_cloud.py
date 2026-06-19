"""小米云模块 — 扫码登录 + 云 API 加密工具 + 设备列表拉取

用法:
    # 扫码登录
    from acnexus_core.xiaomi_cloud import login_qr
    session = login_qr()

    # 云 API 加密
    from acnexus_core.xiaomi_cloud import signed_nonce, generate_nonce
"""

import json
import hashlib
import hmac
import base64
import random
import time
import requests
from Crypto.Cipher import ARC4


# ── 加密/认证工具（供 xiaomi_device_picker 拉设备列表用）──

def signed_nonce(ssecurity, nonce):
    h = hashlib.sha256(base64.b64decode(ssecurity) + base64.b64decode(nonce))
    return base64.b64encode(h.digest()).decode()


def generate_nonce(millis):
    """8字节随机 + 4字节分钟时间戳"""
    import os
    nonce_bytes = os.urandom(8) + (int(millis / 60000)).to_bytes(4, byteorder='big')
    return base64.b64encode(nonce_bytes).decode()


def encrypt_rc4(password_b64, payload):
    r = ARC4.new(base64.b64decode(password_b64))
    r.encrypt(bytes(1024))
    return base64.b64encode(r.encrypt(payload.encode())).decode()


def decrypt_rc4(password_b64, payload):
    r = ARC4.new(base64.b64decode(password_b64))
    r.encrypt(bytes(1024))
    return r.encrypt(base64.b64decode(payload)).decode()


def generate_enc_signature(url, method, signed_nonce, params):
    sig = [method.upper(), url.split("com")[1].replace("/app/", "/")]
    for k, v in params.items():
        sig.append(f"{k}={v}")
    sig.append(signed_nonce)
    return base64.b64encode(
        hashlib.sha1("&".join(sig).encode("utf-8")).digest()
    ).decode()


# ── 扫码登录内部工具 ──

def _agent() -> str:
    agent_id = "".join(chr(random.randint(65, 69)) for _ in range(13))
    random_text = "".join(chr(random.randint(97, 122)) for _ in range(18))
    return f"{random_text}-{agent_id} APP/com.xiaomi.mihome APPV/10.5.201"


def _to_json(text: str) -> dict:
    return json.loads(text.replace("&&&START&&&", ""))


def _print_qr_terminal(url: str):
    """在终端打印 ASCII 二维码，供无 GUI 环境（Agent/SSH）扫码"""
    try:
        import qrcode
        qr = qrcode.QRCode()
        qr.add_data(url)
        print("\n📱 请用米家 App 扫描下方二维码登录：\n")
        qr.print_ascii(invert=True)
        print(f"\n（如终端不支持二维码，请浏览器打开：{url}）\n")
    except ImportError:
        print(f"\n📱 请用米家 App 扫码登录。打开浏览器访问：\n{url}\n")


# ── 扫码登录 ──

def login_qr(qr_callback=None) -> dict:
    """
    扫码登录小米云（无需密码/验证码）。

    参数:
        qr_callback: fn(qr_png: bytes|None, login_url: str) -> None

    返回: {"ssecurity": str, "serviceToken": str, "userId": str}
    失败抛出 RuntimeError。
    """
    session = requests.Session()

    # Step 1: 获取二维码 URL 和长轮询 URL
    r = session.get(
        "https://account.xiaomi.com/longPolling/loginUrl",
        params={
            "_qrsize": "480",
            "qs": "%3Fsid%3Dxiaomiio%26_json%3Dtrue",
            "callback": "https://sts.api.io.mi.com/sts",
            "_hasLogo": "false",
            "sid": "xiaomiio",
            "serviceParam": "",
            "_locale": "en_GB",
            "_dc": str(int(time.time() * 1000)),
        },
        timeout=15,
    )
    if r.status_code != 200:
        raise RuntimeError(f"QR Step1 失败 (HTTP {r.status_code})")
    data = _to_json(r.text)
    login_page_url = data.get("loginUrl")
    long_poll_url = data.get("lp")
    timeout_sec = data.get("timeout", 600)

    if not long_poll_url:
        raise RuntimeError("QR 登录初始化失败")

    # 展示链接 / 终端二维码
    if qr_callback:
        qr_callback(None, login_page_url or "")
    elif login_page_url:
        _print_qr_terminal(login_page_url)

    # Step 2: 长轮询等待扫码
    headers = {"User-Agent": _agent()}
    start = time.time()
    while True:
        try:
            r = session.get(long_poll_url, headers=headers, timeout=20)
        except requests.exceptions.Timeout:
            if time.time() - start > timeout_sec:
                raise RuntimeError("扫码超时，请重试")
            continue
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"轮询异常: {e}")

        if r.status_code == 200:
            break
        if time.time() - start > timeout_sec:
            raise RuntimeError("扫码超时，请重试")

    resp = _to_json(r.text)
    ssecurity = resp.get("ssecurity", "")
    userId = resp.get("userId", "")
    location_url = resp.get("location", "")

    if not ssecurity:
        raise RuntimeError("扫码登录失败：未获取到凭证")

    # Step 4: 获取 serviceToken
    r = session.get(location_url, headers=headers, timeout=15)
    serviceToken = r.cookies.get("serviceToken")
    if not serviceToken:
        raise RuntimeError("QR Step4 失败：无法获取 serviceToken")

    return {
        "ssecurity": str(ssecurity),
        "serviceToken": str(serviceToken),
        "userId": str(userId),
    }
