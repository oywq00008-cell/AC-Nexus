# 小米空调伴侣集成指南

## 文件结构

```
tests/xiaomi_backend/
├── token_manager.py     # Token 管理：扫码 + keyring 存取
├── ir_sender.py         # 红外发送：对接 python-miio
├── requirements.txt     # 新增依赖
└── integration_guide.md # 本文件
```

## 集成到主项目的步骤

### 1. 安装依赖

```bash
pip install -r tests/xiaomi_backend/requirements.txt
```

### 2. config.py 改动 — 设备类型字段

`config.json` 中米家设备示例：

```json
{
  "devices": {
    "mijia_ac_01": {
      "type": "xiaomi",           // ← 新增
      "did": "1058221161",        // ← 新增（米家设备 ID）
      "host": "192.168.8.100",
      "name": "卧室空调伴侣",
      "brand": "格力"
    }
  }
}
```

`DEVICE_KEYS` 加字段：

```python
# config.py 第 127 行附近
DEVICE_KEYS = ("host", "port", "mac", "model", "name", "brand", "fan",
               "schedule_enabled", "auto_adjust", "temp_rules",
               "type", "did")   # ← 新增
```

### 3. ac_control.py 改动 — 设备类型路由

`send_ac()` 函数在第 92 行附近，在发 IR 之前加路由：

```python
# --- 现有代码 ---
dev = _cfg.config.get("devices", {}).get(mac, {})
brand = _cfg.resolve_brand(dev.get("brand", "格力"))
# ... hvac_ir 算 durations ...

# --- 新增：设备类型路由 ---
dev_type = dev.get("type", "broadlink")

if dev_type == "xiaomi":
    from broadlinkac_desktop.pyside.xiaomi_ir import send_ac as xiaomi_send
    token = keyring.get_password("BroadlinkAC", f"mi_token_{dev.get('did', mac)}")
    if not token:
        raise NeedQRLogin(dev)  # 触发扫码弹窗
    result = xiaomi_send(dev["host"], token, durations,
                          power, mode, temp, fan, source)
    # ... 写日志 ...
    return result

# --- 原有 Broadlink 逻辑不变 ---
# data = pulses_to_data(durations)
# d = get_device(mac)
# d.send_data(data)
```

### 4. 扫描设备时识别类型

`_scan_devices()` 中，除了 Broadlink UDP 扫描，也可以从 config 中已有的米家设备读取 IP、检测是否在线：

```python
# 检查米家设备是否在线
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
online = s.connect_ex((ip, 54321)) == 0  # python-miio 默认端口
s.close()
```

### 5. 设置页面加米家选项

`dialogs.py` 的设置弹窗中加：

- **设备类型下拉框**：`博联RM` / `米家空调伴侣`
- **Token 状态**：显示「已保存」或「点击扫码获取」
- **扫码按钮**：调用 `token_manager.qr_login_gui(self.parent)`

### 6. SKILL.md 更新

在 `skills/broadlinkac/SKILL.md` 中加米家支持的说明。

## 安全说明

- Token 存储在系统钥匙串（Windows: 凭据管理器 / macOS: Keychain / Linux: libsecret）
- 不会写入 config.json 或任何明文文件
- 当前用户登录后才能解密
- 设备重新配对后 Token 失效，需要重新扫码
