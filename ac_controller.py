#!/usr/bin/env python3
"""
BroadlinkAC — 博联空调智能控制器 (macOS 桌面应用)
customtkinter + 和风天气 + 中央气象台台风网 + Broadlink RM 系列
"""

import json
import gzip
import math
import re
import sys
import time
import threading
import urllib.request
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
from tkinter import Menu, Toplevel, messagebox
from tkcalendar import Calendar

import broadlink
from broadlink.remote import pulses_to_data
import schedule as sch

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════
APP_NAME = "BroadlinkAC"
APP_DIR = Path.home() / ".ac_controller"
CONFIG_FILE = APP_DIR / "config.json"
LOG_DIR = APP_DIR / "logs"

QW_HOST = ""  # 从 config 加载，用户需在设置中填入个人 Host
NMC_HOST = "https://typhoon.nmc.cn/weatherservice"

MODES = {"制冷": "cool", "制热": "heat", "除湿": "dry", "送风": "fan", "自动": "auto", "关闭": "off"}
FANS = {"自动": "auto", "1 档": "1", "2 档": "2", "3 档": "3"}
MODE_KEYS = {v: k for k, v in MODES.items()}

DEFAULT_RULES = [
    (36, 99, 24, "cool"),
    (33, 35, 25, "cool"),
    (30, 32, 26, "cool"),
    (25, 29, 27, "cool"),
    (18, 24, 0, "off"),   # 不发送指令
    (0, 17, 28, "heat"),
]

# 运行时全局（从 config 加载）
LOCATION = {"lat": 39.90, "lon": 116.40, "name": "北京"}
QW_KEY = ""
AC_BRAND = "gree"  # 默认格力

# 品牌映射: 显示名 → 模块名
AC_BRANDS = {
    "格力": "gree", "美的": "midea", "海尔": "haier", "华凌": "midea",
    "奥克斯": "aux", "海信": "hisense", "大金": "daikin", "三菱": "mitsubishi",
    "小米": "midea", "松下": "panasonic",
}

# ═══════════════════════════════════════════
# 持久化
# ═══════════════════════════════════════════
def load_config():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {
        "trigger_time": "12:00",
        "schedule_enabled": True,
        "temp_rules": [list(r) for r in DEFAULT_RULES],
        "typhoon_alert_km": 800,
        "typhoon_alert_enabled": True,
        "api_key": "",
        "qw_host": "",
        "location": dict(LOCATION),
        "brand": "格力",
        "off_time": "22:00",
        "off_enabled": False,
    }

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))

config = None  # 由 init() 设置

def init(api_key=None, qw_host=None, location=None, brand=None):
    """初始化：加载配置、同步全局变量、启动后台定时任务。

       只有两种场景需要调用：
       1. 启动 GUI：if __name__ == '__main__' 时自动调用
       2. Agent 脚本：先 init()，再调用 send_ac / fetch_weather 等

       Agent 可直接传入配置，无需手动编辑 config.json：
           init(api_key="xxx", qw_host="https://xxx.re.qweatherapi.com",
                location={"lat": 22.54, "lon": 114.05, "name": "深圳"})
    """
    global config
    config = load_config()
    # Agent 传入的参数覆盖 config 并持久化
    changed = False
    if api_key:
        config["api_key"] = api_key
        changed = True
    if qw_host:
        config["qw_host"] = qw_host
        changed = True
    if location:
        config["location"] = location
        changed = True
    if brand:
        config["brand"] = brand
        changed = True
    if changed:
        save_config(config)
    apply_config()
    # 启动后台调度线程
    threading.Thread(target=scheduler_loop, daemon=True).start()

def apply_config():
    """将 config 同步到运行时全局变量"""
    global QW_KEY, QW_HOST, LOCATION, AC_BRAND
    QW_KEY = config.get("api_key", "")
    QW_HOST = config.get("qw_host", "")
    if QW_HOST and not QW_HOST.startswith("http"):
        QW_HOST = "https://" + QW_HOST
    LOCATION = config.get("location", {"lat": 39.90, "lon": 116.40, "name": "北京"})
    AC_BRAND = AC_BRANDS.get(config.get("brand", "格力"), "gree")

# ═══════════════════════════════════════════
# 天气
# ═══════════════════════════════════════════
def fetch_weather():
    url = f"{QW_HOST}/v7/weather/now?location={LOCATION['lon']},{LOCATION['lat']}&key={QW_KEY}"
    try:
        raw = urllib.request.urlopen(url, timeout=8).read()
        data = json.loads(gzip.decompress(raw))
        if data["code"] == "200":
            return data["now"]
    except Exception as e:
        print(f"[天气] {e}")
    return None

# 缓存的室外温度（UI 刷新时更新，定时任务直接读取）
_cached_temp = None

# ═══════════════════════════════════════════
# 城市搜索 (OpenStreetMap Nominatim → 坐标)
# ═══════════════════════════════════════════
def city_lookup(query: str):
    """OpenStreetMap 搜索 → [{name, display, lat, lon}, ...]"""
    import urllib.parse
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "q": query, "format": "json", "limit": 8,
        "accept-language": "zh", "countrycodes": "cn"
    })
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AC_Controller/1.0"})
        raw = urllib.request.urlopen(req, timeout=8).read()
        data = json.loads(raw)
        return [{
            "name": r.get("name", ""),
            "display": r.get("display_name", ""),
            "lat": float(r["lat"]), "lon": float(r["lon"]),
        } for r in data]
    except Exception as e:
        print(f"[Nominatim] {e}")
    return []

# ═══════════════════════════════════════════
# 台风
# ═══════════════════════════════════════════
def fetch_typhoons():
    year = datetime.now().year
    url = f"{NMC_HOST}/typhoon/jsons/list_{year}?callback=cb"
    try:
        resp = urllib.request.urlopen(url, timeout=8).read().decode("utf-8")
        # JSONP → JSON
        body = re.search(r'\((.*)\)', resp, re.DOTALL)
        if not body:
            return []
        data = json.loads(body.group(1))
        active = []
        for t in data.get("typhoonList", []):
            if t[7] == "start":  # status == start = active
                active.append({
                    "id": t[0], "eng": t[1], "cn": t[2],
                    "code": str(t[3]), "meaning": t[6] or ""
                })
        return active
    except Exception as e:
        print(f"[台风列表] {e}")
    return []

def fetch_typhoon_detail(tid):
    url = f"{NMC_HOST}/typhoon/jsons/view_{tid}?callback=cb"
    try:
        resp = urllib.request.urlopen(url, timeout=8).read().decode("utf-8")
        body = re.search(r'\((.*)\)', resp, re.DOTALL)
        if not body:
            return None
        data = json.loads(body.group(1))
        t = data.get("typhoon", [])
        if not t:
            return None
        # Latest track point
        pts = t[8]  # array of track points
        if not pts:
            return None
        latest = pts[-1]
        forecast_raw = latest[11]  # {"BABJ": [[...],...]}
        if not isinstance(forecast_raw, dict):
            forecast_raw = {}
        forecasts = []
        if "BABJ" in forecast_raw:
            for f in forecast_raw["BABJ"]:
                forecasts.append({
                    "hours": f[0], "lon": f[2], "lat": f[3],
                    "pressure": f[4], "wind": f[5], "cat": f[6]
                })

        def cat_name(c):
            return {"TD":"热带低压","TS":"热带风暴","STS":"强热带风暴",
                    "TY":"台风","STY":"强台风","SuperTY":"超强台风"}.get(c, c)

        return {
            "cn": t[2], "eng": t[1], "code": str(t[3]),
            "cat": cat_name(latest[3]),
            "lon": latest[4], "lat": latest[5],
            "pressure": latest[6], "wind": latest[7],
            "direction": latest[8], "speed": latest[9],
            "update_time": latest[1],
            "forecasts": forecasts,
        }
    except Exception as e:
        print(f"[台风详情] {e}")
    return None

def calc_distance(lat1, lon1, lat2, lon2):
    """Haversine 距离 (km)"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

# ═══════════════════════════════════════════
# 设备缓存
# ═══════════════════════════════════════════
DEVICE_CACHE = APP_DIR / "device.json"

def load_device_cache():
    if DEVICE_CACHE.exists():
        return json.loads(DEVICE_CACHE.read_text())
    return None

def save_device_cache(device):
    """保存设备信息以便下次直连"""
    info = {
        "host": device.host[0],
        "port": device.host[1],
        "mac": device.mac.hex() if isinstance(device.mac, bytes) else str(device.mac),
        "model": device.model,
        "name": device.name,
        "devtype": device.devtype,
    }
    DEVICE_CACHE.write_text(json.dumps(info, indent=2))

def get_device():
    """获取博联设备: 优先缓存直连, 失败则重新扫描并更新缓存"""
    # 尝试从缓存直连
    cached = load_device_cache()
    if cached:
        try:
            d = broadlink.hello(cached["host"])
            d.auth()
            return d
        except Exception:
            pass  # 缓存失效, 重新扫描

    # 全网络扫描
    devices = broadlink.discover(timeout=5)
    if not devices:
        raise Exception("未发现博联设备")
    d = devices[0]
    d.auth()
    save_device_cache(d)
    return d

# ═══════════════════════════════════════════
# 空调控制
# ═══════════════════════════════════════════
def send_ac(power: str, mode: str, temp: int, fan: str):
    """发红外码，自动根据当前品牌选择协议"""
    brand = AC_BRAND
    t = min(max(temp, 16), 30)

    if brand in ("gree", "midea", "hisense", "daikin", "mitsubishi"):
        # hvac_ir 品牌 — 按需导入
        mod = __import__(f"hvac_ir.{brand}", fromlist=[brand])
        cls_name = brand.capitalize()
        sender = getattr(mod, cls_name)()
        mode_map = {"auto": sender.MODE_AUTO, "cool": sender.MODE_COOL,
                    "dry": sender.MODE_DRY, "fan": sender.MODE_FAN,
                    "heat": sender.MODE_HEAT}
        fan_map = {"auto": sender.FAN_AUTO, "1": sender.FAN_1,
                   "2": sender.FAN_2, "3": sender.FAN_3}
        pwr = sender.POWER_ON if power == "on" else sender.POWER_OFF
        m = mode_map.get(mode, sender.MODE_COOL)
        f = fan_map.get(fan, sender.FAN_AUTO)
        vsw = getattr(sender, "VDIR_SWING", None)
        hsw = getattr(sender, "HDIR_SWING", None)
        sender.send(pwr, m, f, t, vsw, hsw, False)
    else:
        # 自定义协议 — 每个品牌有独立模式和风速值
        mod = __import__(f"protocols.{brand}", fromlist=[brand])
        cls_map = {"haier": "Haier", "aux": "AUX", "panasonic": "Panasonic"}
        cls_name = cls_map.get(brand, brand.capitalize())
        sender = getattr(mod, cls_name)()
        # 模式映射：各品牌模式值不同
        mode_maps = {
            "haier": {"auto": 0x00, "cool": 0x01, "dry": 0x02, "fan": 0x04, "heat": 0x03},
            "aux":   {"auto": 0, "cool": 1, "dry": 2, "fan": 6, "heat": 4},
            "panasonic": {"auto": 0, "cool": 3, "dry": 2, "fan": 6, "heat": 4},
        }
        # 风速映射: "1档"→HIGH, "2档"→MED, "3档"→LOW
        fan_maps = {
            "haier": {"auto": 0x00, "1": 0x01, "2": 0x02, "3": 0x03},
            "aux":   {"auto": 5, "1": 1, "2": 2, "3": 3},
            "panasonic": {"auto": 7, "1": 3, "2": 2, "3": 1},
        }
        mode_map = mode_maps.get(brand, {"auto": 0, "cool": 1, "dry": 2, "fan": 3, "heat": 4})
        fan_map = fan_maps.get(brand, {"auto": 7, "1": 0, "2": 1, "3": 2})
        pwr = mod.POWER_ON if power == "on" else mod.POWER_OFF
        m = mode_map.get(mode, mode_map["cool"])
        f = fan_map.get(fan, fan_map["auto"])
        sender.send(pwr, m, f, t)

    data = pulses_to_data(sender.get_durations())

    d = get_device()
    d.send_data(data)

    now = datetime.now()
    action = "开机" if power == "on" else "关机"
    if power == "on":
        return f"[{now:%H:%M}] {action} → {MODE_KEYS.get(mode, mode)} {temp}°C 风{fan}"
    return f"[{now:%H:%M}] {action}"

def decide_ac(outdoor):
    for low, high, target, mode in config["temp_rules"]:
        if low <= outdoor <= high:
            return target, mode
    return 26, "cool"

# ═══════════════════════════════════════════
# 日志
# ═══════════════════════════════════════════
def write_log(category: str, msg: str):
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"{date_str}.md"

    if not log_file.exists():
        log_file.write_text(f"# {date_str} 操作日志\n\n", encoding="utf-8")

    now = datetime.now().strftime("%H:%M")
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")

    # 确保有对应分类标题
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

# ═══════════════════════════════════════════
# 定时任务
# ═══════════════════════════════════════════
_sched_lock = threading.Lock()
def scheduled_job():
    if _cached_temp is None:
        w = fetch_weather()
        if not w:
            return None
        outdoor = float(w["temp"])
    else:
        outdoor = _cached_temp

    target, mode = decide_ac(outdoor)
    if mode == "off":
        write_log("空调", f"⏰ 定时触发: 室外 {outdoor}°C → 关闭，不发送指令")
        return None

    try:
        result = send_ac("on", mode, target, "auto")
        write_log("空调", f"⏰ 定时触发: 室外 {outdoor}°C → {MODE_KEYS.get(mode,mode)} {target}°C")
        return result
    except Exception as e:
        write_log("系统", f"定时发送失败: {e}")
    return None

def scheduled_off_job():
    """定时关机"""
    try:
        result = send_ac("off", "cool", 26, "auto")
        write_log("空调", f"⏰ 定时关机: {result}")
        return result
    except Exception as e:
        write_log("系统", f"定时关机失败: {e}")
    return None

def scheduler_loop():
    sch.every().day.at(config["trigger_time"]).do(scheduled_job)
    if config.get("off_enabled"):
        sch.every().day.at(config["off_time"]).do(scheduled_off_job)
    # 每30分钟刷新台风
    sch.every(30).minutes.do(refresh_typhoon_silent)
    while True:
        with _sched_lock:
            sch.run_pending()
        time.sleep(15)

def refresh_typhoon_silent():
    """后台静默刷新台风，记录日志"""
    try:
        typhoons = fetch_typhoons()
        for t in typhoons:
            detail = fetch_typhoon_detail(t["id"])
            if detail:
                dist = calc_distance(LOCATION["lat"], LOCATION["lon"], detail["lat"], detail["lon"])
                status = "⚠️ 预警" if dist < config["typhoon_alert_km"] else "✅ 安全"
                write_log("台风", f"{detail['cn']} ({detail['eng']}) {detail['cat']} 距{dist}km {status}")
    except Exception as e:
        print(f"[台风后台] {e}")

threading_running = False  # 由 init() 设置为 True

# ═══════════════════════════════════════════
# 开机自启 (macOS LaunchAgent)
# ═══════════════════════════════════════════
LAUNCH_AGENT = Path.home() / "Library/LaunchAgents/com.local.ac-controller.plist"

def check_autostart():
    return LAUNCH_AGENT.exists()

def enable_autostart():
    import plistlib
    plist = {
        "Label": "com.local.ac-controller",
        "ProgramArguments": [sys.executable, str(Path(__file__).resolve())],
        "RunAtLoad": True,
    }
    LAUNCH_AGENT.parent.mkdir(parents=True, exist_ok=True)
    plistlib.dump(plist, LAUNCH_AGENT.open("wb"))

def disable_autostart():
    if LAUNCH_AGENT.exists():
        LAUNCH_AGENT.unlink()

# ═══════════════════════════════════════════
# UI
# ═══════════════════════════════════════════
ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME + "  v2")
        self.geometry("860x700")
        self.minsize(760, 620)

        # Mac 菜单栏
        self._build_menu()

        # Tab
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(12, 0))
        self.tab_ac = self.tabview.add("🎮 空调控制")
        self.tab_ty = self.tabview.add("🌀 台风监测")

        self._build_ac_tab()
        self._build_ty_tab()

        # 启动天气自动刷新 (立即刷新 + 10 分钟周期)
        self._wx_timer_id = None
        self._auto_wx_refresh()
        self.after(800, self._refresh_typhoon)

    # ── 菜单栏 ──
    def _build_menu(self):
        menubar = Menu(self)

        file_menu = Menu(menubar, tearoff=0)
        file_menu.add_command(label="退出", command=self.quit)
        menubar.add_cascade(label="文件", menu=file_menu)

        log_menu = Menu(menubar, tearoff=0)
        log_menu.add_command(label="查看日志...", command=self._open_log_dialog)
        menubar.add_cascade(label="日志", menu=log_menu)

        settings_menu = Menu(menubar, tearoff=0)
        settings_menu.add_command(label="⚙️ 设置...", command=self._open_settings)
        menubar.add_cascade(label="设置", menu=settings_menu)

        help_menu = Menu(menubar, tearoff=0)
        help_menu.add_command(label="About BroadlinkAC", command=lambda: messagebox.showinfo(
            "About",
            "BroadlinkAC\n\n"
            "Smart AC controller for Broadlink RM series\n"
            "Multi-brand IR control + weather + typhoon monitor\n\n"
            "by Hermes Agent / 欧阳小白\n\n"
            "github.com/oywq00008-cell/BroadlinkAC"))
        help_menu.add_command(label="View on GitHub", command=lambda: __import__("webbrowser").open(
            "https://github.com/oywq00008-cell/BroadlinkAC"))
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def _open_log_dialog(self):
        dates = get_log_dates()
        if not dates:
            messagebox.showinfo("日志", "暂无日志记录。")
            return

        dlg = Toplevel(self)
        dlg.title("📅 选择日期")
        dlg.geometry("300x320")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="选择日期查看日志", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))

        cal = Calendar(dlg, selectmode="day", date_pattern="yyyy-mm-dd",
                       firstweekday="monday")
        cal.pack(padx=20, pady=10)

        # 标记有日志的日期
        for d in dates:
            try:
                cal.calevent_create(datetime.strptime(d, "%Y-%m-%d"), "", "log")
                cal.tag_config("log", background="#4A90D9", foreground="white")
            except:
                pass

        def on_open():
            date = cal.get_date()
            dlg.destroy()
            self._show_log_window(date)

        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(pady=(5, 10))
        ctk.CTkButton(btn_frame, text="取消", fg_color="gray", command=dlg.destroy).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="打开日志", command=on_open).pack(side="left", padx=5)

    def _show_log_window(self, date_str):
        win = Toplevel(self)
        win.title(f"📜 {date_str} 操作日志")
        win.geometry("640x500")
        win.transient(self)

        content = read_log(date_str)

        text = ctk.CTkTextbox(win, font=ctk.CTkFont(size=13), wrap="word")
        text.pack(fill="both", expand=True, padx=10, pady=10)
        text.insert("1.0", content)
        text.configure(state="disabled")

    # ── 设置窗口 ──
    def _open_settings(self):
        dlg = Toplevel(self)
        dlg.title("⚙️ 设置")
        dlg.geometry("480x460")
        dlg.transient(self)
        dlg.grab_set()

        # ── API Key ──
        ctk.CTkLabel(dlg, text="┌─ 和风 API Key", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#888").pack(anchor="w", padx=20, pady=(15, 2))
        api_entry = ctk.CTkEntry(dlg, width=400, show="*")
        api_entry.insert(0, QW_KEY)
        api_entry.pack(padx=20)

        # ── 个人 Host ──
        ctk.CTkLabel(dlg, text="┌─ 和风个人 Host", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#888").pack(anchor="w", padx=20, pady=(10, 2))
        host_entry = ctk.CTkEntry(dlg, width=400, placeholder_text="https://xxx.re.qweatherapi.com")
        host_entry.insert(0, QW_HOST)
        host_entry.pack(padx=20)
        ctk.CTkLabel(dlg, text="💡 免费订阅的和风 API 需填入个人 Host 地址", font=ctk.CTkFont(size=10), text_color="gray").pack(anchor="w", padx=20)

        # ── 开机自启 ──
        auto_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        auto_frame.pack(fill="x", padx=20, pady=(10, 2))
        auto_switch = ctk.CTkSwitch(auto_frame, text="开机自启动")
        auto_switch.pack(side="left")
        if check_autostart():
            auto_switch.select()

        # ── 空调品牌 ──
        brand_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        brand_frame.pack(fill="x", padx=20, pady=(10, 2))
        ctk.CTkLabel(brand_frame, text="空调品牌:").pack(side="left")
        brand_combo = ctk.CTkComboBox(brand_frame, values=list(AC_BRANDS.keys()), width=120)
        brand_combo.set(config.get("brand", "格力"))
        brand_combo.pack(side="left", padx=5)

        # ── 城市设置 ──
        ctk.CTkLabel(dlg, text="📍 城市设置", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=20, pady=(15, 5))

        loc_info = ctk.CTkLabel(dlg, text=f"当前: {LOCATION['name']} ({LOCATION['lat']}°N, {LOCATION['lon']}°E)",
                                font=ctk.CTkFont(size=12), text_color="#27AE60")
        loc_info.pack(anchor="w", padx=20)

        # 自动定位
        ctk.CTkButton(dlg, text="📍 自动定位", fg_color="#555", width=120,
                      command=lambda: self._auto_locate(loc_info)).pack(anchor="w", padx=20, pady=(5, 2))
        ctk.CTkLabel(dlg, text="💡 自动定位基于网络 IP，可能有偏差，建议手动输入",
                     font=ctk.CTkFont(size=10), text_color="gray").pack(anchor="w", padx=20)

        # 手动搜索
        search_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        search_frame.pack(fill="x", padx=20, pady=(5, 0))
        city_entry = ctk.CTkEntry(search_frame, width=230, placeholder_text="输入城市/镇/村名搜索")
        city_entry.pack(side="left")

        def do_search():
            query = city_entry.get().strip()
            if not query:
                messagebox.showwarning("提示", "请输入城市名称")
                return
            city_entry.configure(state="disabled")
            search_btn.configure(text="⏳", state="disabled")
            search_frame.update()
            results = city_lookup(query)
            city_entry.configure(state="normal")
            search_btn.configure(text="🔍 搜索", state="normal")
            if not results:
                messagebox.showinfo("未找到", f"未找到 '{query}'，请尝试其他关键词")
                return
            # 弹窗选结果
            pick_dlg = Toplevel(dlg)
            pick_dlg.title("🔍 选择城市")
            pick_dlg.geometry("440x400")
            pick_dlg.transient(dlg)
            pick_dlg.grab_set()
            ctk.CTkLabel(pick_dlg, text=f"搜索 '{query}' 找到 {len(results)} 个结果:",
                         font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(10, 5))

            import tkinter as tk
            radio_var = tk.IntVar(value=0)

            for i, r in enumerate(results):
                row = ctk.CTkFrame(pick_dlg, fg_color="transparent")
                row.pack(fill="x", padx=15, pady=2)
                rb = ctk.CTkRadioButton(row, text="", variable=radio_var, value=i)
                rb.pack(side="left")
                ctk.CTkLabel(row, text=f"{r['name']}  {r['display'][:50]}",
                             font=ctk.CTkFont(size=12)).pack(side="left", padx=5)
                ctk.CTkLabel(row, text=f"{r['lat']:.2f}°N, {r['lon']:.2f}°E",
                             font=ctk.CTkFont(size=11), text_color="gray").pack(side="right")

            def confirm():
                idx = radio_var.get()
                r = results[idx]
                loc_info.configure(text=f"当前: {r['name']} ({r['lat']:.2f}°N, {r['lon']:.2f}°E)",
                                   text_color="#27AE60")
                dlg._picked_loc = {"lat": r["lat"], "lon": r["lon"], "name": r["name"]}
                pick_dlg.destroy()

            btn_f = ctk.CTkFrame(pick_dlg, fg_color="transparent")
            btn_f.pack(pady=(5, 10))
            ctk.CTkButton(btn_f, text="取消", fg_color="gray", command=pick_dlg.destroy).pack(side="left", padx=5)
            ctk.CTkButton(btn_f, text="✅ 确认", command=confirm).pack(side="left", padx=5)

        search_btn = ctk.CTkButton(search_frame, text="🔍 搜索", width=70, command=do_search)
        search_btn.pack(side="left", padx=5)

        ctk.CTkLabel(dlg, text="💡 可直接搜索你所在的位置", font=ctk.CTkFont(size=10), text_color="gray").pack(anchor="w", padx=20, pady=(2, 0))

        # ── 保存 ──
        def save_settings():
            config["api_key"] = api_entry.get().strip()
            config["qw_host"] = host_entry.get().strip()
            config["brand"] = brand_combo.get()
            if hasattr(dlg, "_picked_loc"):
                config["location"] = dlg._picked_loc
            save_config(config)
            apply_config()
            # 开机自启
            if auto_switch.get():
                enable_autostart()
            else:
                disable_autostart()
            # 刷新天气显示
            self._weather_card_label.configure(text=f"🌤️ {LOCATION['name']}天气")
            # 更新控制卡片标题
            self._ctrl_card_label.configure(text=f"🎮 {config['brand']}空调控制")
            self._refresh_weather()
            dlg.destroy()
            self.send_status.configure(text="✅ 设置已保存", text_color="#27AE60")
            self.after(2000, lambda: self.send_status.configure(text=""))

        btn_f = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_f.pack(pady=(15, 10))
        ctk.CTkButton(btn_f, text="取消", fg_color="gray", width=80, command=dlg.destroy).pack(side="left", padx=5)
        ctk.CTkButton(btn_f, text="💾 保存", width=80, command=save_settings).pack(side="left", padx=5)

    def _auto_locate(self, info_label):
        """IP 定位获取大致位置"""
        info_label.configure(text="⏳ 定位中...", text_color="#E67E22")
        try:
            resp = urllib.request.urlopen("http://ip-api.com/json/", timeout=5)
            data = json.loads(resp.read())
            if data.get("status") == "success":
                info_label.configure(
                    text=f"当前: {data['city']} ({data['lat']:.2f}°N, {data['lon']:.2f}°E)",
                    text_color="#27AE60")
                # 暂存到设置窗口
                for w in self.winfo_children():
                    if isinstance(w, Toplevel) and w.title() == "⚙️ 设置":
                        w._picked_loc = {"lat": data["lat"], "lon": data["lon"], "name": data["city"]}
                        break
                return
        except Exception as e:
            info_label.configure(text=f"定位失败: {e}", text_color="#E74C3C")
            return
        info_label.configure(text="定位失败: 未知错误", text_color="#E74C3C")

    # ── Tab 1: 空调控制 ──
    def _build_ac_tab(self):
        # 专用网格容器（不直接放 tab 帧上，避免与 CTkTabview 的 pack 冲突）
        grid_frame = ctk.CTkFrame(self.tab_ac, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # 2x2 等分网格
        grid_frame.grid_columnconfigure(0, weight=1, uniform="col")
        grid_frame.grid_columnconfigure(1, weight=1, uniform="col")
        grid_frame.grid_rowconfigure(0, weight=1, uniform="row")
        grid_frame.grid_rowconfigure(1, weight=1, uniform="row")

        # ═══════════ 左上: 天气 ═══════════
        weather_card = ctk.CTkFrame(grid_frame)
        weather_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        weather_card.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        self._weather_card_label = ctk.CTkLabel(weather_card, text=f"🌤️ {LOCATION['name']}天气",
                                                 font=ctk.CTkFont(size=14, weight="bold"))
        self._weather_card_label.pack(anchor="center", padx=12, pady=(10, 2))
        self.wx_temp = ctk.CTkLabel(weather_card, text="—°C", font=ctk.CTkFont(size=36, weight="bold"))
        self.wx_temp.pack(pady=(5, 0))
        self.wx_info = ctk.CTkLabel(weather_card, text="点击刷新", font=ctk.CTkFont(size=12))
        self.wx_info.pack()
        self.wx_obs = ctk.CTkLabel(weather_card, text="", font=ctk.CTkFont(size=10), text_color="gray")
        self.wx_obs.pack(pady=(0, 5))
        ctk.CTkButton(weather_card, text="🔄 刷新天气", fg_color="#4A90D9",
                      command=self._auto_wx_refresh).pack(pady=(5, 10))

        # ═══════════ 右上: 控制 ═══════════
        ctrl_card = ctk.CTkFrame(grid_frame)
        ctrl_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        ctrl_card.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        self._ctrl_card_label = ctk.CTkLabel(ctrl_card, text=f"🎮 {config.get('brand', '格力')}空调控制",
                                             font=ctk.CTkFont(size=14, weight="bold"))
        self._ctrl_card_label.pack(anchor="center", padx=12, pady=(10, 5))

        row1 = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(row1, text="电源:", width=45).pack(side="left")
        self.power_switch = ctk.CTkSwitch(row1, text="")
        self.power_switch.pack(side="left")
        self.power_switch.select()

        row2 = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(row2, text="模式:", width=45).pack(side="left")
        self.mode_combo = ctk.CTkComboBox(row2, values=[k for k in MODES if k != "关闭"], width=100)
        self.mode_combo.set("制冷")
        self.mode_combo.pack(side="left")

        row3 = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        row3.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(row3, text="温度:", width=45).pack(side="left")
        self._temp_val = 26
        def temp_down():
            if self._temp_val > 16:
                self._temp_val -= 1
                self.temp_label.configure(text=f"{self._temp_val}°C")
        def temp_up():
            if self._temp_val < 30:
                self._temp_val += 1
                self.temp_label.configure(text=f"{self._temp_val}°C")
        ctk.CTkButton(row3, text="−", width=28, fg_color="#555", command=temp_down).pack(side="left")
        self.temp_label = ctk.CTkLabel(row3, text="26°C", width=50, font=ctk.CTkFont(size=16, weight="bold"))
        self.temp_label.pack(side="left")
        ctk.CTkButton(row3, text="+", width=28, fg_color="#555", command=temp_up).pack(side="left")

        row4 = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        row4.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(row4, text="风速:", width=45).pack(side="left")
        self.fan_combo = ctk.CTkComboBox(row4, values=list(FANS.keys()), width=100)
        self.fan_combo.set("自动")
        self.fan_combo.pack(side="left")

        ctk.CTkButton(ctrl_card, text="📡 发送指令", fg_color="#2E7D32", height=32,
                      command=self._on_send_click).pack(pady=(10, 3), padx=12, fill="x")
        self.send_status = ctk.CTkLabel(ctrl_card, text="", font=ctk.CTkFont(size=11))
        self.send_status.pack(pady=(0, 5))

        # ═══════════ 左下: 定时 ═══════════
        sched_card = ctk.CTkFrame(grid_frame)
        sched_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        sched_card.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        ctk.CTkLabel(sched_card, text="⏰ 定时设置", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="center", padx=12, pady=(10, 5))

        trigger_parts = config["trigger_time"].split(":")
        trig_h = trigger_parts[0] if len(trigger_parts) > 0 else "12"
        trig_m = trigger_parts[1] if len(trigger_parts) > 1 else "00"

        srow = ctk.CTkFrame(sched_card, fg_color="transparent")
        srow.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(srow, text="每天", width=35).pack(side="left")
        hours = [f"{h:02d}" for h in range(24)]
        self.hour_combo = ctk.CTkComboBox(srow, values=hours, width=55)
        self.hour_combo.set(trig_h)
        self.hour_combo.pack(side="left", padx=2)
        ctk.CTkLabel(srow, text="时").pack(side="left", padx=(0, 4))
        minutes = [f"{m:02d}" for m in range(0, 60, 5)]
        self.min_combo = ctk.CTkComboBox(srow, values=minutes, width=55)
        self.min_combo.set(trig_m)
        self.min_combo.pack(side="left", padx=2)
        ctk.CTkLabel(srow, text="分").pack(side="left")

        srow2 = ctk.CTkFrame(sched_card, fg_color="transparent")
        srow2.pack(fill="x", padx=12, pady=2)
        self.sched_switch = ctk.CTkSwitch(srow2, text="启用定时")
        self.sched_switch.pack(side="left")
        if config["schedule_enabled"]:
            self.sched_switch.select()

        self.sched_status = ctk.CTkLabel(sched_card, text="", font=ctk.CTkFont(size=10))
        self.sched_status.pack(anchor="center", padx=12, pady=(1, 0))
        self._update_sched_status()

        # ── 定时关机 ──
        ctk.CTkLabel(sched_card, text="── 定时关机 ──", font=ctk.CTkFont(size=10), text_color="#888").pack(anchor="center", pady=(8, 2))

        off_parts = config.get("off_time", "22:00").split(":")
        off_h = off_parts[0] if len(off_parts) > 0 else "22"
        off_m = off_parts[1] if len(off_parts) > 1 else "00"

        off_row = ctk.CTkFrame(sched_card, fg_color="transparent")
        off_row.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(off_row, text="每天", width=35).pack(side="left")
        self.off_hour_combo = ctk.CTkComboBox(off_row, values=hours, width=55)
        self.off_hour_combo.set(off_h)
        self.off_hour_combo.pack(side="left", padx=2)
        ctk.CTkLabel(off_row, text="时").pack(side="left", padx=(0, 4))
        self.off_min_combo = ctk.CTkComboBox(off_row, values=minutes, width=55)
        self.off_min_combo.set(off_m)
        self.off_min_combo.pack(side="left", padx=2)
        ctk.CTkLabel(off_row, text="分").pack(side="left")

        off_row2 = ctk.CTkFrame(sched_card, fg_color="transparent")
        off_row2.pack(fill="x", padx=12, pady=2)
        self.off_switch = ctk.CTkSwitch(off_row2, text="启用关机定时")
        self.off_switch.pack(side="left")
        if config.get("off_enabled"):
            self.off_switch.select()

        self.off_status = ctk.CTkLabel(sched_card, text="", font=ctk.CTkFont(size=10))
        self.off_status.pack(anchor="center", padx=12, pady=(1, 0))
        self._update_off_status()

        btn_row = ctk.CTkFrame(sched_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(5, 10))
        ctk.CTkButton(btn_row, text="💾 保存", width=65, fg_color="#666",
                      command=self._save_schedule).pack(side="left", padx=(0, 5))
        ctk.CTkButton(btn_row, text="▶ 立即执行", width=85, fg_color="#E67E22",
                      command=self._trigger_now).pack(side="left")

        # ═══════════ 右下: 规则 ═══════════
        rule_card = ctk.CTkFrame(grid_frame)
        rule_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        rule_card.grid(row=1, column=1, sticky="nsew", padx=2, pady=2)
        ctk.CTkLabel(rule_card, text="📋 温度规则", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="center", padx=12, pady=(10, 5))

        self.rules_frame = ctk.CTkFrame(rule_card, fg_color="transparent")
        self.rules_frame.pack(fill="both", expand=True, padx=12, pady=(0, 5))
        self._refresh_rules_display()

        ctk.CTkButton(rule_card, text="✏️ 编辑规则", width=80, fg_color="#555",
                      command=self._edit_rules).pack(pady=(0, 10), padx=12, anchor="e")

    def _refresh_rules_display(self):
        for w in self.rules_frame.winfo_children():
            w.destroy()
        for low, high, target, mode in config["temp_rules"]:
            if mode == "off":
                text = f"  室外 {low}-{high}°C → 关闭"
            else:
                text = f"  室外 {low}-{high}°C → {MODE_KEYS.get(mode, mode)} {target}°C"
            label = ctk.CTkLabel(self.rules_frame,
                text=text,
                font=ctk.CTkFont(size=12), anchor="center")
            label.pack(fill="x", pady=1)

    def _update_sched_status(self):
        if config["schedule_enabled"]:
            t = config["trigger_time"]
            self.sched_status.configure(text=f"✅ 开机定时已开启 · 每天 {t}", text_color="#27AE60")
        else:
            self.sched_status.configure(text="⏸️ 开机定时已关闭", text_color="gray")

    def _update_off_status(self):
        if config.get("off_enabled"):
            t = config.get("off_time", "22:00")
            self.off_status.configure(text=f"✅ 关机定时已开启 · 每天 {t}", text_color="#E67E22")
        else:
            self.off_status.configure(text="⏸️ 关机定时已关闭", text_color="gray")

    def _edit_rules(self):
        dlg = Toplevel(self)
        dlg.title("✏️ 编辑温度规则")
        dlg.geometry("450x400")
        dlg.transient(self)
        dlg.grab_set()

        entries = []
        scroll = ctk.CTkScrollableFrame(dlg, height=280)
        scroll.pack(fill="both", expand=True, padx=15, pady=(15, 5))

        for i, (low, high, target, mode) in enumerate(config["temp_rules"]):
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=f"规则{i+1}:", width=50).pack(side="left")
            el = ctk.CTkEntry(row, width=40)
            el.insert(0, str(low))
            el.pack(side="left", padx=2)
            ctk.CTkLabel(row, text="~").pack(side="left")
            eh = ctk.CTkEntry(row, width=40)
            eh.insert(0, str(high))
            eh.pack(side="left", padx=2)
            ctk.CTkLabel(row, text="°C →").pack(side="left")
            em = ctk.CTkComboBox(row, values=list(MODES.keys()), width=80)
            em.set(MODE_KEYS.get(mode, "制冷"))
            em.pack(side="left", padx=2)
            et = ctk.CTkEntry(row, width=40)
            et.insert(0, str(target))
            et.pack(side="left", padx=2)
            ctk.CTkLabel(row, text="°C").pack(side="left")
            entries.append((el, eh, em, et, mode))

        def save():
            new_rules = []
            errors = []
            for i, (el, eh, em, et, _) in enumerate(entries):
                try:
                    l, h, t = int(el.get()), int(eh.get()), int(et.get())
                    m = MODES[em.get()]
                    new_rules.append([l, h, t, m])
                except Exception:
                    errors.append(f"第{i+1}条 — 请输入合法数字和模式")
            if errors:
                messagebox.showwarning("规则格式错误", "\n".join(errors), parent=dlg)
                return
            if new_rules:
                config["temp_rules"] = new_rules
                save_config(config)
                self._refresh_rules_display()
            dlg.destroy()

        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(pady=(5, 10))
        ctk.CTkButton(btn_frame, text="取消", fg_color="gray", command=dlg.destroy).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="💾 保存", command=save).pack(side="left", padx=5)

    # ── Tab 2: 台风监测 ──
    def _build_ty_tab(self):
        top = ctk.CTkFrame(self.tab_ty, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(top, text="🌀 西北太平洋台风监测", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        ctk.CTkLabel(top, text="数据: 中央气象台", font=ctk.CTkFont(size=11), text_color="gray").pack(side="left", padx=10)

        self.ty_list = ctk.CTkScrollableFrame(self.tab_ty, height=350)
        self.ty_list.pack(fill="both", expand=True, padx=10, pady=5)

        ctk.CTkLabel(self.ty_list, text="点击 [刷新数据] 获取台风信息", font=ctk.CTkFont(size=13), text_color="gray").pack(pady=20)

        # 底部设置
        bot = ctk.CTkFrame(self.tab_ty, fg_color="transparent")
        bot.pack(fill="x", padx=10, pady=(5, 10))

        ctk.CTkLabel(bot, text="预警距离:").pack(side="left")
        self.ty_alert_km = ctk.CTkEntry(bot, width=60)
        self.ty_alert_km.insert(0, str(config.get("typhoon_alert_km", 800)))
        self.ty_alert_km.pack(side="left", padx=5)
        ctk.CTkLabel(bot, text="km").pack(side="left", padx=(0, 15))

        self.ty_alert_switch = ctk.CTkSwitch(bot, text="弹窗提醒")
        self.ty_alert_switch.pack(side="left")
        if config.get("typhoon_alert_enabled", True):
            self.ty_alert_switch.select()

        ctk.CTkButton(bot, text="💾 保存", width=70, fg_color="#666",
                      command=self._save_ty_settings).pack(side="left", padx=10)

        self.ty_time_label = ctk.CTkLabel(bot, text="", font=ctk.CTkFont(size=11), text_color="gray")
        self.ty_time_label.pack(side="right")

        ctk.CTkButton(bot, text="🔄 刷新数据", fg_color="#4A90D9",
                      command=self._refresh_typhoon).pack(side="right", padx=5)
        ctk.CTkButton(bot, text="🌍 卫星云图", fg_color="#555",
                      command=self._open_zoom_earth).pack(side="right", padx=5)

    def _save_ty_settings(self):
        try:
            config["typhoon_alert_km"] = int(self.ty_alert_km.get())
        except:
            config["typhoon_alert_km"] = 800
        config["typhoon_alert_enabled"] = bool(self.ty_alert_switch.get())
        save_config(config)
        write_log("系统", f"台风预警设置已更新")

    # ── zoom.earth 卫星云图 ──
    def _open_zoom_earth(self):
        """在默认浏览器打开 zoom.earth"""
        import webbrowser
        lat, lon = LOCATION["lat"], LOCATION["lon"]
        url = f"https://zoom.earth/#view={lat},{lon},8z"
        webbrowser.open(url)
        self.send_status.configure(text="🌍 卫星云图已在浏览器打开", text_color="#27AE60")
        self.after(2000, lambda: self.send_status.configure(text=""))

    # ── 空调操作 ──
    def _schedule_wx_refresh(self):
        """启动/重置天气自动刷新定时器"""
        WX_INTERVAL = 10 * 60 * 1000  # 10 分钟 (毫秒)
        if self._wx_timer_id:
            self.after_cancel(self._wx_timer_id)
        self._wx_timer_id = self.after(WX_INTERVAL, self._auto_wx_refresh)

    def _auto_wx_refresh(self):
        """定时自动刷新或手动触发 → 刷新后调度下一次"""
        self._refresh_weather()
        self._schedule_wx_refresh()

    def _refresh_weather(self):
        global _cached_temp
        w = fetch_weather()
        if w:
            _cached_temp = float(w["temp"])
            self.wx_temp.configure(text=f"{w['temp']}°C")
            info = f"{w['text']}  |  体感 {w['feelsLike']}°C  |  湿度 {w['humidity']}%  |  {w['windDir']} {w['windScale']}级"
            self.wx_info.configure(text=info)
            self.wx_obs.configure(text=f"观测时间: {w['obsTime']}")
            write_log("天气", f"{w['temp']}°C {w['text']} 湿度{w['humidity']}% {w['windDir']}{w['windScale']}级")
        else:
            self.wx_info.configure(text="获取失败")

    # ── 发送指令 (异步, 不卡 UI) ──
    def _on_send_click(self):
        self.send_status.configure(text="⏳ 发送中...", text_color="#E67E22")
        threading.Thread(target=self._do_send, daemon=True).start()

    def _do_send(self):
        try:
            power = "on" if self.power_switch.get() else "off"
            mode = MODES[self.mode_combo.get()]
            temp = self._temp_val
            fan = FANS[self.fan_combo.get()]
            result = send_ac(power, mode, temp, fan)
            write_log("空调", result)
            self.after(0, lambda: self.send_status.configure(text=f"✅ {result}", text_color="#27AE60"))
        except Exception as e:
            err_msg = str(e)
            write_log("系统", f"发送失败: {err_msg}")
            self.after(0, lambda: self.send_status.configure(text=f"❌ {err_msg}", text_color="#E74C3C"))
            # 弹窗询问修复
            self.after(0, lambda: self._ask_repair(err_msg))
        # 成功后 2 秒清除
        self.after(2000, lambda: self.send_status.configure(text=""))

    def _ask_repair(self, err_msg):
        if messagebox.askyesno("发送失败", f"{err_msg}\n\n是否进入修复程序？"):
            self._repair_dialog()

    # ── 修复 / 故障诊断 ──
    def _repair_dialog(self):
        dlg = Toplevel(self)
        dlg.title("🔧 故障诊断")
        dlg.geometry("520x460")
        dlg.transient(self)

        ctk.CTkLabel(dlg, text="🔧 故障诊断", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))

        result_frame = ctk.CTkScrollableFrame(dlg, height=300)
        result_frame.pack(fill="both", expand=True, padx=15, pady=(5, 0))

        def add_line(text, color="#FFFFFF"):
            lbl = ctk.CTkLabel(result_frame, text=text, font=ctk.CTkFont(size=12),
                               text_color=color, anchor="center")
            lbl.pack(fill="x", pady=1)
            return lbl

        def run_diagnosis():
            for w in result_frame.winfo_children():
                w.destroy()
            all_ok = True

            # 1. Python 环境
            add_line("┌─ Python 环境 ────────", "#888")
            ver = sys.version.split()[0]
            add_line(f"│ ✅ Python {ver}", "#27AE60")
            add_line(f"│    {sys.executable}", "#888")
            add_line("└──────────────────────", "#888")

            # 2. 依赖库 (缺失的显示修复按钮)
            add_line("┌─ 依赖库 ─────────────", "#888")
            for pkg_name in ["broadlink", "hvac_ir", "customtkinter", "schedule", "tkcalendar"]:
                try:
                    mod = __import__(pkg_name)
                    ver_str = getattr(mod, "__version__", "OK")
                    add_line(f"│ ✅ {pkg_name} {ver_str}", "#27AE60")
                except Exception:
                    # 缺失: 显示安装按钮
                    row = ctk.CTkFrame(result_frame, fg_color="transparent")
                    row.pack(fill="x", pady=1)
                    label = ctk.CTkLabel(row, text=f"│ ❌ {pkg_name} 未安装",
                                         font=ctk.CTkFont(size=12), text_color="#E74C3C", anchor="center")
                    label.pack(side="left")
                    def make_fix_btn(pkg, r, lbl, nm):
                        return lambda: fix_pip(pkg, r, lbl, nm)
                    ctk.CTkButton(row, text="📦 安装", width=60, height=22,
                                   font=ctk.CTkFont(size=10), fg_color="#E67E22",
                                   command=make_fix_btn(pkg_name, row, label, pkg_name)
                                   ).pack(side="right", padx=(10, 0))
                    all_ok = False
            add_line("└──────────────────────", "#888")

            # 3. 博联设备
            add_line("┌─ 博联设备扫描 ───────", "#888")
            add_line("│ 🔍 扫描局域网...", "#E67E22")
            result_frame.update()
            device_found = True

            old_cache = load_device_cache()
            old_ip = old_cache["host"] if old_cache else None

            try:
                devices = broadlink.discover(timeout=5)
                if devices:
                    d = devices[0]
                    new_ip = d.host[0]
                    ip_changed = old_ip and new_ip != old_ip

                    add_line(f"│ ✅ {d.model} ({d.name})", "#27AE60")
                    add_line(f"│    IP: {new_ip}:{d.host[1]}", "#AAA")
                    mac_hex = d.mac.hex() if isinstance(d.mac, bytes) else str(d.mac)
                    add_line(f"│    MAC: {mac_hex}", "#AAA")
                    if ip_changed:
                        add_line(f"│    ⚠️ IP 已变更: {old_ip} → {new_ip}", "#E67E22")

                    try:
                        d.auth()
                        add_line("│    认证: ✅ 通过", "#27AE60")
                        # 更新缓存
                        save_device_cache(d)
                        if ip_changed:
                            add_line("│    📝 缓存已更新", "#27AE60")
                    except Exception as ae:
                        add_line(f"│    认证: ❌ {ae}", "#E74C3C")
                        device_found = False
                else:
                    dev_row = ctk.CTkFrame(result_frame, fg_color="transparent")
                    dev_row.pack(fill="x", pady=1)
                    ctk.CTkLabel(dev_row, text="│ ❌ 未发现设备",
                                 font=ctk.CTkFont(size=12), text_color="#E74C3C").pack(side="left")
                    ctk.CTkButton(dev_row, text="🔍 排查指南", width=80, height=22,
                                   font=ctk.CTkFont(size=10), fg_color="#E67E22",
                                   command=self._device_guide).pack(side="right", padx=(10, 0))
                    device_found = False
            except Exception as de:
                add_line(f"│ ❌ 扫描异常: {de}", "#E74C3C")
                device_found = False
            if not device_found:
                all_ok = False
            add_line("└──────────────────────", "#888")

            # 4. 和风天气
            add_line("┌─ 和风天气 API ───────", "#888")
            w = fetch_weather()
            if w:
                add_line(f"│ ✅ {w['temp']}°C {w['text']} (观测 {w['obsTime']})", "#27AE60")
            else:
                add_line("│ ❌ API 无响应 (请检查网络连接)", "#E74C3C")
                all_ok = False
            add_line("└──────────────────────", "#888")

            # 汇总
            add_line("")
            if all_ok:
                add_line("📊 诊断结果: ✅ 全部正常", "#27AE60")
            else:
                add_line("📊 诊断结果: ❌ 存在问题，请按上方按钮修复", "#E74C3C")

        def fix_pip(pkg, row, label, name):
            import subprocess
            label.configure(text=f"│ ⏳ 安装 {name}...", text_color="#E67E22")
            for w in row.winfo_children():
                if isinstance(w, ctk.CTkButton):
                    w.configure(state="disabled", text="⏳")
            result_frame.update()
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", pkg],
                              check=True, capture_output=True, timeout=60)
                mod = __import__(pkg)
                ver_str = getattr(mod, "__version__", "OK")
                label.configure(text=f"│ ✅ {name} {ver_str}", text_color="#27AE60")
                for w in row.winfo_children():
                    if isinstance(w, ctk.CTkButton):
                        w.destroy()
            except Exception as e:
                label.configure(text=f"│ ❌ {name} 安装失败", text_color="#E74C3C")
                for w in row.winfo_children():
                    if isinstance(w, ctk.CTkButton):
                        w.configure(state="normal", text="📦 重试")

        # 按钮
        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(pady=(8, 10))
        ctk.CTkButton(btn_frame, text="🔄 重新检测", fg_color="#4A90D9",
                      command=run_diagnosis).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="关闭", fg_color="#666",
                      command=dlg.destroy).pack(side="left", padx=5)

        run_diagnosis()

    def _device_guide(self):
        """设备排查指南"""
        cached = load_device_cache()
        ip = cached["host"] if cached else "未知"
        mac = cached["mac"] if cached else "未知"
        model = cached.get("model", "Broadlink RM") if cached else "Broadlink RM"
        guide = (
            "🔧 博联设备排查指南\n\n"
            "1. 确认设备电源指示灯是否亮起\n"
            "2. 确认设备已连接路由器 WiFi\n"
            "   （指示灯常亮 = 已连接）\n"
            "3. 确认电脑与设备在同一局域网\n"
            "4. 尝试拔掉设备电源，10 秒后重插\n"
            "5. 如果路由器有 AP 隔离功能，请关闭\n"
            "6. 检查路由器管理页能否看到该设备\n"
            "\n"
            f"📟 已知设备信息:\n"
            f"   型号: {model}\n"
            f"   上次 IP: {ip}\n"
            f"   MAC: {mac}\n"
            "\n"
            "如以上均无效，请用「博联智能」App\n"
            "重新配网后再试。"
        )
        messagebox.showinfo("🔧 设备排查指南", guide)

    def _save_schedule(self):
        h = self.hour_combo.get()
        m = self.min_combo.get()
        t = f"{h}:{m}"
        config["trigger_time"] = t
        config["schedule_enabled"] = bool(self.sched_switch.get())

        oh = self.off_hour_combo.get()
        om = self.off_min_combo.get()
        config["off_time"] = f"{oh}:{om}"
        config["off_enabled"] = bool(self.off_switch.get())

        save_config(config)
        with _sched_lock:
            sch.clear()
            # 重新注册台风刷新
            sch.every(30).minutes.do(refresh_typhoon_silent)
            if config["schedule_enabled"]:
                sch.every().day.at(t).do(scheduled_job)
            if config.get("off_enabled"):
                sch.every().day.at(config["off_time"]).do(scheduled_off_job)
        write_log("系统", f"定时已更新: 开机 {t} {'(启用)' if config['schedule_enabled'] else '(停用)'}  关机 {config['off_time']} {'(启用)' if config.get('off_enabled') else '(停用)'}")
        self._update_sched_status()
        self._update_off_status()

    def _trigger_now(self):
        try:
            result = scheduled_job()
            if result:
                self.send_status.configure(text=f"✅ {result}", text_color="#27AE60")
            else:
                self.send_status.configure(text="❌ 天气获取失败", text_color="#E74C3C")
                write_log("系统", "手动触发失败: 天气获取失败")
        except Exception as e:
            self.send_status.configure(text=f"❌ {e}", text_color="#E74C3C")
            write_log("系统", f"手动触发失败: {e}")
        self.after(3000, lambda: self.send_status.configure(text=""))

    # ── 台风操作 ──
    def _refresh_typhoon(self):
        for w in self.ty_list.winfo_children():
            w.destroy()

        typhoons = fetch_typhoons()
        if not typhoons:
            ctk.CTkLabel(self.ty_list, text="西北太平洋当前无活跃台风 ✅",
                         font=ctk.CTkFont(size=14)).pack(pady=30)
            self.ty_time_label.configure(text=f"上次更新: {datetime.now():%H:%M}")
            return

        for t in typhoons:
            detail = fetch_typhoon_detail(t["id"])
            if not detail:
                continue

            dist = calc_distance(LOCATION["lat"], LOCATION["lon"], detail["lat"], detail["lon"])
            alert = dist < config.get("typhoon_alert_km", 800)
            status = "⚠️ 预警" if alert else "✅ 安全"
            status_color = "#E74C3C" if alert else "#27AE60"

            card = ctk.CTkFrame(self.ty_list)
            card.pack(fill="x", padx=5, pady=5, ipady=5)

            # 标题行
            title_row = ctk.CTkFrame(card, fg_color="transparent")
            title_row.pack(fill="x", padx=10, pady=(5, 3))
            ctk.CTkLabel(title_row, text=f"🌀 {detail['cn']}  {detail['eng']}",
                         font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
            ctk.CTkLabel(title_row, text=f"#{detail['code']}",
                         font=ctk.CTkFont(size=12), text_color="gray").pack(side="left", padx=8)
            ctk.CTkLabel(title_row, text=status, text_color=status_color,
                         font=ctk.CTkFont(size=12, weight="bold")).pack(side="right")

            # 详情
            d1 = ctk.CTkFrame(card, fg_color="transparent")
            d1.pack(fill="x", padx=10)
            ctk.CTkLabel(d1, text=f"等级: {detail['cat']}  |  气压: {detail['pressure']}hPa  |  风速: {detail['wind']}m/s").pack(anchor="center")
            ctk.CTkLabel(d1, text=f"位置: {detail['lat']}°N, {detail['lon']}°E  |  移向: {detail['direction']}  |  移速: {detail['speed']}km/h").pack(anchor="center")
            ctk.CTkLabel(d1, text=f"距{ LOCATION['name']}: {dist}km").pack(anchor="center")

            # 预报
            if detail["forecasts"]:
                d2 = ctk.CTkFrame(card, fg_color="transparent")
                d2.pack(fill="x", padx=10, pady=(3, 8))
                ctk.CTkLabel(d2, text="路径预报:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="center")
                for fc in detail["forecasts"][:4]:
                    ctk.CTkLabel(d2, text=f"  +{fc['hours']}h → {fc['lat']}°N, {fc['lon']}°E  {fc['pressure']}hPa  {fc['wind']}m/s  {fc['cat']}",
                                 font=ctk.CTkFont(size=11)).pack(anchor="center")

            self.ty_time_label.configure(text=f"更新时间: {detail['update_time']}")

            # 弹窗提醒
            if alert and config.get("typhoon_alert_enabled", True):
                messagebox.showwarning("台风预警",
                    f"{detail['cn']} ({detail['cat']})\n距{ LOCATION['name']}仅 {dist}km\n请关注中央气象台最新预报")

            write_log("台风", f"{detail['cn']} {detail['cat']} {detail['lat']}N,{detail['lon']}E 距{dist}km {status}")

        self.ty_time_label.configure(text=f"上次更新: {datetime.now():%H:%M}")


# ═══════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════
if __name__ == "__main__":
    init()
    app = App()
    app.mainloop()
