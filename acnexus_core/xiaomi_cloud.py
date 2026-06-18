"""小米云 MIoT 命令下发模块
基于 token_extractor 的认证逻辑，通过云 API 控制空调伴侣
"""
import time
import json
import hashlib
import hmac
import base64
import requests
from Crypto.Cipher import ARC4

# ── 从 token_extractor.py 复用的加密/认证工具 ──

def signed_nonce(ssecurity, nonce):
    h = hashlib.sha256(base64.b64decode(ssecurity) + base64.b64decode(nonce))
    return base64.b64encode(h.digest()).decode()

def generate_nonce(millis):
    """8字节随机 + 4字节分钟时间戳"""
    import random, os
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

# ── 云控制器 ──

class XiaomiCloudController:
    """登录小米云 → 下发 MIoT 命令"""

    def __init__(self, username: str, password: str, country: str = "cn"):
        self.username = username
        self.password = password
        self.country = country
        self.session = requests.Session()
        self._ssecurity = None
        self._serviceToken = None
        self.userId = None

    # ── 登录 (简化版，复用 token_extractor 思路) ──

    def login(self) -> bool:
        """用户名密码登录，获取 serviceToken"""
        agent = "AND-3.29.44 APP/com.xiaomi.mihome APPV/10.5.201"
        # Step 1: 获取 sign
        r = self.session.get(
            "https://account.xiaomi.com/pass/serviceLogin",
            params={"sid": "xiaomiio", "_json": "true"},
            headers={"User-Agent": agent}
        )
        data = json.loads(r.text.replace("&&&START&&&", ""))
        self._sign = data.get("_sign")
        if not self._sign:
            return False

        # Step 2: 登录
        r = self.session.post(
            "https://account.xiaomi.com/pass/serviceLoginAuth2",
            data={
                "sid": "xiaomiio",
                "hash": hashlib.md5(self.password.encode()).hexdigest().upper(),
                "user": self.username,
                "_sign": self._sign,
                "_json": "true",
            },
            headers={"User-Agent": agent}
        )
        data = json.loads(r.text.replace("&&&START&&&", ""))
        self._ssecurity = data.get("ssecurity")
        self._location = data.get("location")
        self.userId = str(data.get("userId", ""))
        if not self._ssecurity or not self._location:
            return False

        # Step 3: 获取 serviceToken
        r = self.session.get(self._location, headers={"User-Agent": agent})
        self._serviceToken = r.cookies.get("serviceToken")
        if not self._serviceToken:
            return False

        # 装 cookie
        for d in [".api.io.mi.com", ".io.mi.com", ".mi.com"]:
            self.session.cookies.set("serviceToken", self._serviceToken, domain=d)
        return True

    # ── 云 API 调用 ──

    def _api_url(self, path: str) -> str:
        prefix = "" if self.country == "cn" else self.country + "."
        return f"https://{prefix}api.io.mi.com/app{path}"

    def _call_encrypted(self, url: str, data: dict) -> dict:
        """带 RC4 加密的云 API 请求"""
        millis = round(time.time() * 1000)
        nonce = generate_nonce(millis)
        snonce = signed_nonce(self._ssecurity, nonce)

        params = {"data": json.dumps(data)}
        sign = generate_enc_signature(url, "POST", snonce, params)
        params["rc4_hash__"] = sign
        for k, v in params.items():
            params[k] = encrypt_rc4(snonce, v)

        fields = {
            **params,
            "signature": generate_enc_signature(url, "POST", snonce, params),
            "ssecurity": self._ssecurity,
            "_nonce": nonce,
        }

        headers = {
            "User-Agent": "AND-3.29.44 APP/com.xiaomi.mihome APPV/10.5.201",
            "Content-Type": "application/x-www-form-urlencoded",
            "x-xiaomi-protocal-flag-cli": "PROTOCAL-HTTP2",
            "MIOT-ENCRYPT-ALGORITHM": "ENCRYPT-RC4",
        }
        cookies = {
            "userId": self.userId,
            "serviceToken": self._serviceToken,
            "locale": "zh_CN",
        }

        r = self.session.post(url, headers=headers, cookies=cookies, params=fields)
        if r.status_code == 200:
            return json.loads(decrypt_rc4(signed_nonce(self._ssecurity, fields["_nonce"]), r.text))
        raise Exception(f"API error: {r.status_code} {r.text[:200]}")

    def set_properties(self, did: str, props: list) -> dict:
        """
        通过云 API 设置 MIoT 属性
        props: [{"siid": 2, "piid": 1, "value": False}, ...]
        siid/piid 映射见 miio2miot_specs:
          空调控制 (siid=2):
            piid=1: power  (True/False)
            piid=2: mode   (0=auto, 1=cool, 2=dry, 3=heat, 4=wind)
            piid=3: tar_temp (16-30)
          风扇 (siid=3):
            piid=1: fan_level (0=auto_fan, 1=small_fan, 2=medium_fan, 3=large_fan)
        """
        url = self._api_url("/miotspec/prop/set")
        return self._call_encrypted(url, {"params": [{"did": did, **p} for p in props]})

    def get_properties(self, did: str, props: list) -> dict:
        """读取 MIoT 属性"""
        url = self._api_url("/miotspec/prop/get")
        return self._call_encrypted(url, {"params": [{"did": did, **p} for p in props]})


# ── AC 控制快捷方法 ──

def build_ac_command(power: bool = None, mode: int = None,
                     temp: int = None, fan: int = None) -> list:
    """构建空调控制指令列表"""
    cmds = []
    if power is not None:
        cmds.append({"siid": 2, "piid": 1, "value": power})
    if mode is not None:
        cmds.append({"siid": 2, "piid": 2, "value": mode})
    if temp is not None:
        cmds.append({"siid": 2, "piid": 3, "value": temp})
    if fan is not None:
        cmds.append({"siid": 3, "piid": 1, "value": fan})
    return cmds
