"""BroadlinkAC Core — 日志"""

import re
from datetime import datetime
from broadlinkac_core.config import LOG_DIR


def write_log(category: str, msg: str):
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"{date_str}.md"

    if not log_file.exists():
        log_file.write_text(f"# {date_str} 操作日志\n\n", encoding="utf-8")

    now = datetime.now().strftime("%H:%M")
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")

    cat_titles = {"天气": "## 🌤️ 天气", "空调": "## 🎮 空调操作", "台风": "## 🌀 台风监测", "系统": "## ⚙️ 系统"}
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


def get_last_ac_state():
    """读取今天日志，返回空调最后操作状态。精确匹配标准化日志格式。

    '手动开机' '定时开机' '自动调温' '开机' → on
    '手动关机' '定时关机' '自动关机' '关机' → off
    '不更改温度' → 跳过，继续往上找
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"{date_str}.md"
    if not log_file.exists():
        return {"power": "off", "mode": "cool", "temp": 26}

    ON_WORDS = ("手动开机", "定时开机", "自动调温", "开机")
    OFF_WORDS = ("手动关机", "定时关机", "自动关机", "关机")

    lines = log_file.read_text(encoding="utf-8").split("\n")
    for line in reversed(lines):
        # 只处理带 [HH:MM] 时间标记的 AC 操作行（系统设置不带）
        if not re.search(r"\[\d{2}:\d{2}\]", line):
            continue
        if "不更改温度" in line:
            continue
        if any(w in line for w in OFF_WORDS):
            return {"power": "off", "mode": "cool", "temp": 26}
        if any(w in line for w in ON_WORDS):
            mode = "cool"
            temp = 26
            m = re.search(r"→\s*(.+?)\s*(\d+)°C", line)
            if m:
                mode = _LOG_MODES.get(m.group(1), "cool")
                temp = int(m.group(2))
            return {"power": "on", "mode": mode, "temp": temp}
    return {"power": "off", "mode": "cool", "temp": 26}
