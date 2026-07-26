"""AC-Nexus Core — 日志"""

import re
import threading
from datetime import datetime, timedelta
from acnexus_core.config import LOG_DIR

_log_lock = threading.Lock()


def write_log(category: str, msg: str):
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"{date_str}.md"

    with _log_lock:
        if not log_file.exists():
            log_file.write_text(f"# {date_str} 操作日志\n\n", encoding="utf-8")

        now = datetime.now().strftime("%H:%M")
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")

        cat_titles = {"天气": "## 🌤️ 天气", "空调": "## 🎮 空调操作", "台风": "## 🌀 风暴监测", "系统": "## ⚙️ 系统"}
        head = cat_titles.get(category, f"## {category}")
        if head not in lines:
            lines.append("")
            lines.append(head)
            lines.append("| 时间 | 内容 |")
            lines.append("|------|------|")

        lines.append(f"| {now} | {msg} |")
        log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_log(date_str):
    log_file = LOG_DIR / f"{date_str}.md"
    if log_file.exists():
        return log_file.read_text(encoding="utf-8")
    return f"# {date_str}\n\n暂无记录。"


def get_log_dates():
    if not LOG_DIR.exists():
        return []
    dates = []
    for f in sorted(LOG_DIR.glob("*.md"), reverse=True):
        dates.append(f.stem)
    return dates


# 温度模式映射（用于日志解析）
_LOG_MODES = {"制冷": "cool", "制热": "heat", "除湿": "dry", "送风": "fan", "自动": "auto"}

# 设备标签：[设备名][MAC]，用于按设备隔离日志
_DEVICE_TAG_RE = re.compile(r"\[[^\]]+\]\s*\[[0-9a-fA-F]+\]")

# 精确动作词（带边界断言，杜绝 "关机失败" 等被误判为指令）
_ACTION_ON = [
    re.compile(r"手动开机(?=[\s→]|$)"),
    re.compile(r"定时开机(?=[\s→]|$)"),
    re.compile(r"自动调温开机(?=[\s→]|$)"),
    re.compile(r"自动调温\s*→\s*\S+\s+\d+°C"),   # 旧博联自动开机（无"开机"二字）兼容
]
_ACTION_OFF = [
    (re.compile(r"手动关机(?=[\s→]|$)"),    "manual"),
    (re.compile(r"定时关机(?=[\s→]|$)"),    "manual"),
    (re.compile(r"自动调温关机(?=[\s→]|$)"),"auto"),
    (re.compile(r"自动关机(?=[\s→]|$)"),    "auto"),   # 旧博联自动关机 兼容
]
_MODE_TEMP_RE  = re.compile(r"→\s*(制冷|制热|除湿|送风|自动)\s+(\d+)°C")
_MODE_TEMP_RE2 = re.compile(r"\((\w+)\s+(\d+)°C\)")    # 自定义品牌 → (cool 26°C)


def get_last_ac_state(mac=None):
    """往回逐天查找日志，直到找到最后一条 AC 操作记录。

    返回 {"power", "mode", "temp", "source"}：
      - power : "on" | "off" | "unknown"
      - source: "auto"（自动调温触发）| "manual"（手动/定时触发）；unknown 时无此键
    动作以精确 token 判定（见 _ACTION_ON / _ACTION_OFF），避免 "关机失败" 等误判。

    mac 作为检查点：若日志行带 [设备名][MAC] 标签，则只匹配属于该 mac 的记录；
    旧格式无标签的行不做过滤，保证升级前日志仍可读取。
    """
    dt = datetime.now()
    for _ in range(7):  # 最多往回找 7 天（定时模板最长周期为7天）
        date_str = dt.strftime("%Y-%m-%d")
        log_file = LOG_DIR / f"{date_str}.md"
        dt -= timedelta(days=1)

        if not log_file.exists():
            continue

        for line in reversed(log_file.read_text(encoding="utf-8").strip().split("\n")):
            if not re.search(r"\[\d{2}:\d{2}\]", line):
                continue
            if "不更改温度" in line:
                continue
            # MAC 检查点：带设备标签的行只认本设备；旧格式无标签行不过滤
            if mac and _DEVICE_TAG_RE.search(line) and mac not in line:
                continue
            # —— 精确判定关机 ——
            for rx, src in _ACTION_OFF:
                if rx.search(line):
                    return {"power": "off", "mode": "cool", "temp": 26, "source": src}
            # —— 精确判定开机 ——
            if any(rx.search(line) for rx in _ACTION_ON):
                mode, temp = "cool", 26
                mm = _MODE_TEMP_RE.search(line) or _MODE_TEMP_RE2.search(line)
                if mm:
                    if mm.re is _MODE_TEMP_RE:
                        mode = _LOG_MODES.get(mm.group(1), "cool")   # 中文 → 英文
                    else:
                        mode = mm.group(1)                            # 自定义品牌已是英文
                    temp = int(mm.group(2))
                return {"power": "on", "mode": mode, "temp": temp}
        # 文件存在但没匹配到 → 继续往前找

    return {"power": "unknown", "mode": "cool", "temp": 26}
