"""小米云认证模块 — 账号密码登录 + 扫码登录 + 凭据持久化（跨平台）

职责单一：只做登录和凭据存储，不包含 API 调用和设备控制。

用法:
    from acnexus_core.cloud_auth import login, login_qr, save_credentials, load_credentials
"""
import json
import hashlib
import random
import re
import time
from urllib.parse import parse_qs, urlparse

import keyring
import requests

SERVICE_NAME = "AC-Nexus"
KEY_USER = "xiaomi_cloud_user"
KEY_PASS = "xiaomi_cloud_pass"


# ── 凭据持久化（keyring 跨平台：Windows 凭据管理器 / macOS Keychain / Linux Secret Service）──

def save_credentials(username: str, password: str):
    keyring.set_password(SERVICE_NAME, KEY_USER, username)
    keyring.set_password(SERVICE_NAME, KEY_PASS, password)


def load_credentials() -> tuple[str, str] | tuple[None, None]:
    username = keyring.get_password(SERVICE_NAME, KEY_USER)
    password = keyring.get_password(SERVICE_NAME, KEY_PASS)
    return username, password


def clear_credentials():
    for key in (KEY_USER, KEY_PASS):
        try:
            keyring.delete_password(SERVICE_NAME, key)
        except keyring.errors.PasswordDeleteError:
            pass


# ── 内部工具 ──

def _agent() -> str:
    agent_id = "".join(chr(random.randint(65, 69)) for _ in range(13))
    random_text = "".join(chr(random.randint(97, 122)) for _ in range(18))
    return f"{random_text}-{agent_id} APP/com.xiaomi.mihome APPV/10.5.201"


def _device_id() -> str:
    return "".join(chr(random.randint(97, 122)) for _ in range(6))


def _to_json(text: str) -> dict:
    return json.loads(text.replace("&&&START&&&", ""))


# ── 自定义异常 ──

class CaptchaRequired(Exception):
    """需要图片验证码。调用方下载 url 后通过 captcha_code 参数重试"""
    def __init__(self, captcha_url: str):
        self.captcha_url = captcha_url


class TwoFactorRequired(Exception):
    """需要二步验证（手机短信或邮箱验证码）"""
    def __init__(self, info: dict):
        """
        info: {"type": "phone"|"email", "mask": "138****1234"|"xxx@xxx.com",
               "context": str, "ick": str}
        """
        self.info = info


# ── 登录 ──

def login(username: str, password: str,
          captcha_callback=None, twofa_callback=None) -> dict:
    """
    账号密码登录小米云。

    参数:
        username / password: 账号密码
        captcha_callback: fn(captcha_png: bytes) -> str|None
            需要图片验证码时调用，传入 PNG 图片字节数据，
            返回验证码字符串，None 表示取消。
        twofa_callback: fn(info: dict) -> str|None
            需要二步验证时调用，info={'type':'phone'|'email','mask':'138****1234'}
            返回收到的验证码字符串，None 表示取消。

    返回: {"ssecurity": str, "serviceToken": str, "userId": str}
    失败抛出 RuntimeError / CaptchaRequired / TwoFactorRequired。
    """
    session = requests.Session()
    ua = _agent()
    did = _device_id()

    session.cookies.set("sdkVersion", "accountsdk-18.8.15", domain="mi.com")
    session.cookies.set("sdkVersion", "accountsdk-18.8.15", domain="xiaomi.com")
    session.cookies.set("deviceId", did, domain="mi.com")
    session.cookies.set("deviceId", did, domain="xiaomi.com")

    headers = {"User-Agent": ua, "Content-Type": "application/x-www-form-urlencoded"}

    # ── Step 1: 获取 _sign ──
    r = session.get(
        "https://account.xiaomi.com/pass/serviceLogin",
        params={"sid": "xiaomiio", "_json": "true"},
        headers=headers,
        cookies={"userId": username},
        timeout=15,
    )
    if r.status_code != 200:
        raise RuntimeError(f"网络异常 (HTTP {r.status_code})")
    data = _to_json(r.text)
    _sign = data.get("_sign")
    if not _sign:
        raise RuntimeError("无法获取签名令牌，请检查网络")

    # ── Step 2: 提交登录（同一 session 内处理验证码重试）──
    fields = {
        "sid": "xiaomiio",
        "hash": hashlib.md5(password.encode()).hexdigest().upper(),
        "callback": "https://sts.api.io.mi.com/sts",
        "qs": "%3Fsid%3Dxiaomiio%26_json%3Dtrue",
        "user": username,
        "_sign": _sign,
        "_json": "true",
    }

    while True:
        r = session.post(
            "https://account.xiaomi.com/pass/serviceLoginAuth2",
            headers=headers,
            params=fields,
            allow_redirects=False,
            timeout=15,
        )
        if r.status_code != 200:
            raise RuntimeError(f"登录失败 (HTTP {r.status_code})")
        data = _to_json(r.text)

        # ── 图片验证码 ──
        if "captchaUrl" in data and data["captchaUrl"]:
            if not captcha_callback:
                raise CaptchaRequired(
                    _full_url(data["captchaUrl"])
                )
            captcha_url = _full_url(data["captchaUrl"])
            # 用同一 session 下载验证码图片
            img_resp = session.get(captcha_url, headers=headers, timeout=10)
            if img_resp.status_code != 200:
                raise RuntimeError(f"验证码下载失败 (HTTP {img_resp.status_code})")
            captcha_code = captcha_callback(img_resp.content)
            if not captcha_code:
                raise RuntimeError("已取消登录")
            fields["captCode"] = captcha_code
            continue

        # ── 直接成功（无需二步验证）──
        ssecurity = data.get("ssecurity", "")
        if ssecurity and len(str(ssecurity)) > 4:
            userId = data.get("userId", "")
            location = data.get("location", "")
            break

        # ── 二步验证 ──
        if "notificationUrl" in data:
            ssecurity, userId, location = _do_2fa(
                session, ua, data["notificationUrl"], twofa_callback
            )
            if not ssecurity:
                raise RuntimeError("二步验证失败")
            break

        raise RuntimeError(
            f"登录失败：{data.get('desc', '') or data.get('description', '')} "
            f"(code={data.get('code')})"
        )

    # ── Step 3: 获取 serviceToken ──
    r = session.get(
        location,
        headers=headers,
        timeout=15,
    )
    serviceToken = r.cookies.get("serviceToken")
    if not serviceToken:
        raise RuntimeError("无法获取 serviceToken")

    return {
        "ssecurity": str(ssecurity),
        "serviceToken": str(serviceToken),
        "userId": str(userId),
    }


# ── 二步验证内部实现 ──

def _full_url(url_or_path: str) -> str:
    if url_or_path.startswith("/"):
        return "https://account.xiaomi.com" + url_or_path
    return url_or_path


def _do_2fa(session, ua: str, notification_url: str, twofa_callback) -> tuple:
    """执行二步验证流程，返回 (ssecurity, userId, location)"""
    headers = {"User-Agent": ua, "Content-Type": "application/x-www-form-urlencoded"}

    # 2FA-1: GET authStart
    session.get(notification_url, headers=headers, timeout=15)

    # 2FA-2: GET identity/list
    context = parse_qs(urlparse(notification_url).query)["context"][0]
    r = session.get(
        "https://account.xiaomi.com/identity/list",
        params={"sid": "xiaomiio", "context": context, "_locale": "en_US"},
        headers=headers,
        timeout=15,
    )
    list_data = _to_json(r.text)
    options = list_data.get("options", [])
    use_phone = 4 in options  # option=4 表示手机，否则假设邮箱

    # 2FA-3: 发送验证码
    send_params = {
        "_dc": str(int(time.time() * 1000)),
        "sid": "xiaomiio",
        "context": context,
        "mask": "0",
        "_locale": "en_US",
    }
    send_data = {
        "retry": "0",
        "icode": "",
        "_json": "true",
        "ick": session.cookies.get("ick", ""),
    }
    endpoint = "sendPhoneTicket" if use_phone else "sendEmailTicket"
    r = session.post(
        f"https://account.xiaomi.com/identity/auth/{endpoint}",
        params=send_params,
        data=send_data,
        headers=headers,
        timeout=15,
    )
    jr = _to_json(r.text)
    if jr.get("code") != 0:
        raise RuntimeError(f"发送验证码失败：{jr.get('desc','')} (code={jr.get('code')})")

    # 2FA-4: 回调获取验证码
    if not twofa_callback:
        raise TwoFactorRequired({
            "type": "phone" if use_phone else "email",
            "mask": "手机" if use_phone else "邮箱",
            "context": context,
            "ick": session.cookies.get("ick", ""),
        })

    mask = list_data.get("externalId", "") or ""
    twofa_code = twofa_callback({
        "type": "phone" if use_phone else "email",
        "mask": mask,
        "context": context,
        "ick": session.cookies.get("ick", ""),
    })
    if not twofa_code:
        raise RuntimeError("已取消验证")

    # 2FA-5: 验证
    verify_params = {
        "_flag": "8",
        "_json": "true",
        "sid": "xiaomiio",
        "context": context,
        "mask": "0",
        "_locale": "en_US",
    }
    verify_data = {
        "_flag": "8",
        "ticket": twofa_code,
        "trust": "false",
        "_json": "true",
        "ick": session.cookies.get("ick", ""),
    }
    v_endpoint = "verifyPhone" if use_phone else "verifyEmail"
    r = session.post(
        f"https://account.xiaomi.com/identity/auth/{v_endpoint}",
        params=verify_params,
        data=verify_data,
        headers=headers,
        timeout=15,
    )
    if r.status_code != 200:
        raise RuntimeError(f"验证失败 (HTTP {r.status_code})")
    try:
        jr = r.json() if r.text.strip().startswith("{") else _to_json(r.text)
        finish_loc = jr.get("location")
    except Exception:
        finish_loc = r.headers.get("Location")

    # Fallback: result/check
    if not finish_loc:
        r = session.get(
            "https://account.xiaomi.com/identity/result/check",
            params={"sid": "xiaomiio", "context": context, "_locale": "en_US"},
            headers=headers,
            allow_redirects=False,
            timeout=15,
        )
        finish_loc = r.headers.get("Location")

    if not finish_loc:
        raise RuntimeError("验证后无法获取跳转地址，可能验证码错误")

    # 2FA-6: 跳转到 Auth2/end
    if "identity/result/check" in finish_loc:
        r = session.get(finish_loc, headers=headers, allow_redirects=False)
        end_url = r.headers.get("Location", finish_loc)
    else:
        end_url = finish_loc

    # 获取 ssecurity（优先从 extension-pragma header）
    r = session.get(end_url, headers=headers, allow_redirects=False)
    if "Xiaomi Account - Tips" in r.text:
        r = session.get(end_url, headers=headers, allow_redirects=False)

    ssecurity = None
    ext_prag = r.headers.get("extension-pragma")
    if ext_prag:
        try:
            ep = json.loads(ext_prag)
            ssecurity = ep.get("ssecurity")
        except Exception:
            pass

    if not ssecurity:
        try:
            bd = _to_json(r.text) if "&&&" in r.text else r.json()
            ssecurity = bd.get("ssecurity")
        except Exception:
            pass

    if not ssecurity:
        raise RuntimeError("二步验证后无法获取登录凭证")

    # 提取 userId 和 STS location
    userId = list_data.get("externalId", "")
    sts_url = r.headers.get("Location")
    if not sts_url and r.text:
        idx = r.text.find("https://sts.api.io.mi.com/sts")
        if idx != -1:
            end = r.text.find('"', idx)
            sts_url = r.text[idx:end] if end != -1 else r.text[idx:idx+300]

    location = sts_url
    if not location:
        # 从原始响应 body 提取
        try:
            bd = _to_json(r.text) if "&&&" in r.text else r.json()
            location = bd.get("location", "")
        except Exception:
            pass

    if not location:
        raise RuntimeError("无法获取 STS 跳转地址")

    return str(ssecurity), userId, location


# ── 扫码登录 ──

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

def login_qr(qr_callback=None) -> dict:
    """
    扫码登录小米云（无需密码/验证码）。

    参数:
        qr_callback: fn(qr_png: bytes|None, login_url: str) -> None，用于展示二维码

    返回: {"ssecurity": str, "serviceToken": str, "userId": str}
    失败抛出 RuntimeError。
    """
    session = requests.Session()
    # QR 登录不需要预设 cookies（与 token_extractor 一致）

    # QR Step 1: 获取二维码 URL 和长轮询 URL
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

    # QR Step 2: 长轮询等待扫码
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

    # QR Step 4: 获取 serviceToken
    r = session.get(location_url, headers=headers, timeout=15)
    serviceToken = r.cookies.get("serviceToken")
    if not serviceToken:
        raise RuntimeError("QR Step4 失败：无法获取 serviceToken")

    return {
        "ssecurity": str(ssecurity),
        "serviceToken": str(serviceToken),
        "userId": str(userId),
    }
