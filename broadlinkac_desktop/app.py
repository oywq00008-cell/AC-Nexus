"""BroadlinkAC Desktop — macOS GUI"""

import json
import sys
import threading
import urllib.request
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
from tkinter import Menu, Toplevel, messagebox
from tkcalendar import Calendar

import broadlink

import broadlinkac_core.config as _cfg

from broadlinkac_core.config import (
    APP_DIR, CONFIG_FILE, LOG_DIR,
    AC_BRANDS, save_config, apply_config,
)
from broadlinkac_core.ac_control import (
    MODES, FANS, MODE_KEYS,
    load_device_cache, save_device_cache, send_ac,
)
from broadlinkac_core.weather import fetch_weather, city_lookup, fetch_weather_alerts
from broadlinkac_core.typhoon import fetch_typhoons, fetch_typhoon_detail, calc_distance
from broadlinkac_core.logger import write_log, read_log, get_log_dates
from broadlinkac_core.scheduler import (
    _sched_lock, scheduled_job, register_all_jobs,
)

APP_NAME = "BroadlinkAC"

# ── 开机自启 (macOS LaunchAgent) ──
LAUNCH_AGENT = Path.home() / "Library/LaunchAgents/com.local.ac-controller.plist"


def check_autostart():
    return LAUNCH_AGENT.exists()


def enable_autostart():
    import plistlib
    plist = {
        "Label": "com.local.ac-controller",
        "ProgramArguments": [sys.executable, str(Path(__file__).resolve().parent.parent / "ac_controller.py")],
        "RunAtLoad": True,
    }
    LAUNCH_AGENT.parent.mkdir(parents=True, exist_ok=True)
    plistlib.dump(plist, LAUNCH_AGENT.open("wb"))


def disable_autostart():
    if LAUNCH_AGENT.exists():
        LAUNCH_AGENT.unlink()


# ── UI ──
ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME + "  v2")
        self.geometry("860x700")
        self.minsize(760, 620)

        self._build_menu()

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(12, 0))
        self.tab_ac = self.tabview.add("🎮 空调控制")
        self.tab_ty = self.tabview.add("⚠️ 预警信息")

        self._build_ac_tab()
        self._build_ty_tab()

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

        cal = Calendar(dlg, selectmode="day", date_pattern="yyyy-mm-dd", firstweekday="monday")
        cal.pack(padx=20, pady=10)

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
        dlg.geometry("480x540")
        dlg.transient(self)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="┌─ 和风 API Key", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#888").pack(anchor="w", padx=20, pady=(15, 2))
        api_entry = ctk.CTkEntry(dlg, width=400, show="*")
        api_entry.insert(0, _cfg.QW_KEY)
        api_entry.pack(padx=20)

        ctk.CTkLabel(dlg, text="┌─ 和风个人 Host", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#888").pack(anchor="w", padx=20, pady=(10, 2))
        host_entry = ctk.CTkEntry(dlg, width=400, placeholder_text="https://xxx.re.qweatherapi.com")
        host_entry.insert(0, _cfg.QW_HOST)
        host_entry.pack(padx=20)
        ctk.CTkLabel(dlg, text="💡 免费订阅的和风 API 需填入个人 Host 地址",
                     font=ctk.CTkFont(size=10), text_color="gray").pack(anchor="w", padx=20)

        auto_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        auto_frame.pack(fill="x", padx=20, pady=(10, 2))
        auto_switch = ctk.CTkSwitch(auto_frame, text="开机自启动")
        auto_switch.pack(side="left")
        if check_autostart():
            auto_switch.select()

        brand_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        brand_frame.pack(fill="x", padx=20, pady=(10, 2))
        ctk.CTkLabel(brand_frame, text="空调品牌:").pack(side="left")
        brand_combo = ctk.CTkComboBox(brand_frame, values=list(AC_BRANDS.keys()), width=120)
        brand_combo.set(_cfg.config.get("brand", "格力"))
        brand_combo.pack(side="left", padx=5)

        ctk.CTkLabel(dlg, text="📍 城市设置", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=20, pady=(15, 5))

        loc_info = ctk.CTkLabel(dlg, text=f"当前: {_cfg.LOCATION['name']} ({_cfg.LOCATION['lat']}°N, {_cfg.LOCATION['lon']}°E)",
                                font=ctk.CTkFont(size=12), text_color="#27AE60")
        loc_info.pack(anchor="w", padx=20)

        ctk.CTkButton(dlg, text="📍 自动定位", fg_color="#555", width=120,
                      command=lambda: self._auto_locate(loc_info)).pack(anchor="w", padx=20, pady=(5, 2))
        ctk.CTkLabel(dlg, text="💡 自动定位基于网络 IP，可能有偏差，建议手动输入",
                     font=ctk.CTkFont(size=10), text_color="gray").pack(anchor="w", padx=20)

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

        ctk.CTkLabel(dlg, text="💡 可直接搜索你所在的位置",
                     font=ctk.CTkFont(size=10), text_color="gray").pack(anchor="w", padx=20, pady=(2, 0))

        def save_settings():
            _cfg.config["api_key"] = api_entry.get().strip()
            _cfg.config["qw_host"] = host_entry.get().strip()
            _cfg.config["brand"] = brand_combo.get()
            if hasattr(dlg, "_picked_loc"):
                _cfg.config["location"] = dlg._picked_loc
            save_config(_cfg.config)
            apply_config()
            if auto_switch.get():
                enable_autostart()
            else:
                disable_autostart()
            self._weather_card_label.configure(text=f"🌤️ {_cfg.LOCATION['name']}天气")
            self._ctrl_card_label.configure(text=f"🎮 {_cfg.config['brand']}空调控制")
            self._refresh_weather()
            dlg.destroy()
            self.send_status.configure(text="✅ 设置已保存", text_color="#27AE60")
            self.after(2000, lambda: self.send_status.configure(text=""))

        btn_f = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_f.pack(pady=(15, 10))
        ctk.CTkButton(btn_f, text="取消", fg_color="gray", width=80, command=dlg.destroy).pack(side="left", padx=5)
        ctk.CTkButton(btn_f, text="💾 保存", width=80, command=save_settings).pack(side="left", padx=5)

    def _auto_locate(self, info_label):
        info_label.configure(text="⏳ 定位中...", text_color="#E67E22")
        try:
            resp = urllib.request.urlopen("http://ip-api.com/json/", timeout=5)
            data = json.loads(resp.read())
            if data.get("status") == "success":
                info_label.configure(
                    text=f"当前: {data['city']} ({data['lat']:.2f}°N, {data['lon']:.2f}°E)",
                    text_color="#27AE60")
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
        grid_frame = ctk.CTkFrame(self.tab_ac, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=5, pady=5)

        grid_frame.grid_columnconfigure(0, weight=1, uniform="col")
        grid_frame.grid_columnconfigure(1, weight=1, uniform="col")
        grid_frame.grid_rowconfigure(0, weight=1, uniform="row")
        grid_frame.grid_rowconfigure(1, weight=1, uniform="row")

        # 左上: 天气
        weather_card = ctk.CTkFrame(grid_frame)
        weather_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        weather_card.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        self._weather_card_label = ctk.CTkLabel(weather_card, text=f"🌤️ {_cfg.LOCATION['name']}天气",
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

        # 右上: 控制
        ctrl_card = ctk.CTkFrame(grid_frame)
        ctrl_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        ctrl_card.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        self._ctrl_card_label = ctk.CTkLabel(ctrl_card, text=f"🎮 {_cfg.config.get('brand', '格力')}空调控制",
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

        # 左下: 定时
        sched_card = ctk.CTkFrame(grid_frame)
        sched_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        sched_card.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        ctk.CTkLabel(sched_card, text="⏰ 定时设置", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="center", padx=12, pady=(10, 5))

        trigger_parts = _cfg.config["trigger_time"].split(":")
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
        if _cfg.config.get("schedule_enabled"):
            self.sched_switch.select()

        self.sched_status = ctk.CTkLabel(sched_card, text="", font=ctk.CTkFont(size=10))
        self.sched_status.pack(anchor="center", padx=12, pady=(1, 0))
        self._update_sched_status()

        ctk.CTkLabel(sched_card, text="── 定时关机 ──", font=ctk.CTkFont(size=10), text_color="#888").pack(
            anchor="center", pady=(8, 2))

        off_parts = _cfg.config.get("off_time", "22:00").split(":")
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
        if _cfg.config.get("off_enabled"):
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

        # 右下: 规则
        rule_card = ctk.CTkFrame(grid_frame)
        rule_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        rule_card.grid(row=1, column=1, sticky="nsew", padx=2, pady=2)
        ctk.CTkLabel(rule_card, text="📋 温度规则", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="center", padx=12, pady=(10, 5))

        self.rules_frame = ctk.CTkFrame(rule_card, fg_color="transparent")
        self.rules_frame.pack(fill="both", expand=True, padx=12, pady=(0, 5))
        self._refresh_rules_display()

        ctk.CTkButton(rule_card, text="✏️ 编辑规则", width=80, fg_color="#555",
                      command=self._edit_rules).pack(pady=(0, 10), padx=12, anchor="e")

        # 自动调温开关
        adjust_row = ctk.CTkFrame(rule_card, fg_color="transparent")
        adjust_row.pack(fill="x", padx=12, pady=(0, 8))
        self.adjust_switch = ctk.CTkSwitch(adjust_row, text="自动调温",
                                            command=self._save_adjust)
        self.adjust_switch.pack(side="left")
        if _cfg.config.get("auto_adjust", True):
            self.adjust_switch.select()
        ctk.CTkLabel(adjust_row, text="每2小时根据室外温度自动调整",
                     font=ctk.CTkFont(size=10), text_color="gray").pack(side="left", padx=8)

    def _refresh_rules_display(self):
        for w in self.rules_frame.winfo_children():
            w.destroy()
        for low, high, target, mode in _cfg.config["temp_rules"]:
            if mode == "off":
                text = f"  室外 {low}-{high}°C → 关闭"
            else:
                text = f"  室外 {low}-{high}°C → {MODE_KEYS.get(mode, mode)} {target}°C"
            label = ctk.CTkLabel(self.rules_frame, text=text, font=ctk.CTkFont(size=12), anchor="center")
            label.pack(fill="x", pady=1)

    def _update_sched_status(self):
        if _cfg.config.get("schedule_enabled"):
            t = _cfg.config["trigger_time"]
            self.sched_status.configure(text=f"✅ 开机定时已开启 · 每天 {t}", text_color="#27AE60")
        else:
            self.sched_status.configure(text="⏸️ 开机定时已关闭", text_color="gray")

    def _update_off_status(self):
        if _cfg.config.get("off_enabled"):
            t = _cfg.config.get("off_time", "22:00")
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

        for i, (low, high, target, mode) in enumerate(_cfg.config["temp_rules"]):
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=f"规则{i + 1}:", width=50).pack(side="left")
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
                    errors.append(f"第{i + 1}条 — 请输入合法数字和模式")
            if errors:
                messagebox.showwarning("规则格式错误", "\n".join(errors), parent=dlg)
                return
            if new_rules:
                _cfg.config["temp_rules"] = new_rules
                save_config(_cfg.config)
                self._refresh_rules_display()
            dlg.destroy()

        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(pady=(5, 10))
        ctk.CTkButton(btn_frame, text="取消", fg_color="gray", command=dlg.destroy).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="💾 保存", command=save).pack(side="left", padx=5)

    # ── Tab 2: 预警信息 ──
    def _build_ty_tab(self):
        # 使用网格容器，左右两列
        grid = ctk.CTkFrame(self.tab_ty, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=5, pady=5)
        grid.grid_columnconfigure(0, weight=1, uniform="tycol")
        grid.grid_columnconfigure(1, weight=1, uniform="tycol")
        grid.grid_rowconfigure(0, weight=1)

        # ── 左列: 台风 ──
        left = ctk.CTkFrame(grid)
        left.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        ctk.CTkLabel(left, text="🌀 西北太平洋台风", font=ctk.CTkFont(size=13, weight="bold")).pack(
            anchor="w", padx=10, pady=(8, 2))
        ctk.CTkLabel(left, text="数据: 中央气象台", font=ctk.CTkFont(size=10), text_color="gray").pack(
            anchor="w", padx=10)

        self.ty_list = ctk.CTkScrollableFrame(left, height=280)
        self.ty_list.pack(fill="both", expand=True, padx=8, pady=5)
        ctk.CTkLabel(self.ty_list, text="点击 [刷新数据] 获取台风信息",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(pady=20)

        ctk.CTkButton(left, text="🔄 刷新台风", fg_color="#4A90D9", height=26,
                      command=self._refresh_typhoon).pack(pady=(0, 8))

        # ── 右列: 当地预警 ──
        right = ctk.CTkFrame(grid)
        right.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)

        ctk.CTkLabel(right, text="🌤️ 当地天气预警", font=ctk.CTkFont(size=13, weight="bold")).pack(
            anchor="w", padx=10, pady=(8, 2))
        ctk.CTkLabel(right, text="数据: 和风天气", font=ctk.CTkFont(size=10), text_color="gray").pack(
            anchor="w", padx=10)

        self.alert_list = ctk.CTkScrollableFrame(right, height=280)
        self.alert_list.pack(fill="both", expand=True, padx=8, pady=5)
        ctk.CTkLabel(self.alert_list, text="点击 [刷新预警] 获取当地预警",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(pady=20)

        ctk.CTkButton(right, text="🔄 刷新预警", fg_color="#E67E22", height=26,
                      command=self._refresh_alerts).pack(pady=(0, 8))

        # ── 底部: 共享设置栏 ──
        bot = ctk.CTkFrame(self.tab_ty, fg_color="transparent")
        bot.pack(fill="x", padx=10, pady=(5, 10))
        ctk.CTkLabel(bot, text="台风预警距离:").pack(side="left")
        self.ty_alert_km = ctk.CTkEntry(bot, width=55)
        self.ty_alert_km.insert(0, str(_cfg.config.get("typhoon_alert_km", 800)))
        self.ty_alert_km.pack(side="left", padx=5)
        ctk.CTkLabel(bot, text="km").pack(side="left", padx=(0, 10))
        self.ty_alert_switch = ctk.CTkSwitch(bot, text="弹窗提醒")
        self.ty_alert_switch.pack(side="left")
        if _cfg.config.get("typhoon_alert_enabled", True):
            self.ty_alert_switch.select()
        ctk.CTkButton(bot, text="💾 保存", width=60, fg_color="#666",
                      command=self._save_ty_settings).pack(side="left", padx=8)
        ctk.CTkButton(bot, text="🌍 卫星云图", fg_color="#555", width=80,
                      command=self._open_zoom_earth).pack(side="right", padx=3)
        self.ty_time_label = ctk.CTkLabel(bot, text="", font=ctk.CTkFont(size=11), text_color="gray")
        self.ty_time_label.pack(side="right", padx=10)

    def _refresh_alerts(self):
        """刷新当地天气预警"""
        for w in self.alert_list.winfo_children():
            w.destroy()

        alerts = fetch_weather_alerts()
        if not alerts:
            ctk.CTkLabel(self.alert_list, text="✅ 暂无预警信息",
                         font=ctk.CTkFont(size=13), text_color="#27AE60").pack(pady=30)
            return

        # 按严重程度排序: 红>橙>黄>蓝
        sev_order = {"extreme": 0, "severe": 1, "moderate": 2, "minor": 3}
        alerts.sort(key=lambda a: sev_order.get(a.get("severity", ""), 99))

        sev_cn = {"extreme": "红色", "severe": "橙色", "moderate": "黄色", "minor": "蓝色"}
        sev_color = {"extreme": "#E74C3C", "severe": "#E67E22", "moderate": "#F1C40F", "minor": "#3498DB"}

        for a in alerts:
            sev = a.get("severity", "minor")
            card = ctk.CTkFrame(self.alert_list)
            card.pack(fill="x", padx=3, pady=3, ipady=4)

            # 标题行: 颜色条 + 等级 + 标题
            title_row = ctk.CTkFrame(card, fg_color="transparent")
            title_row.pack(fill="x", padx=8, pady=(4, 2))
            sev_label = sev_cn.get(sev, sev)
            color = sev_color.get(sev, "#888")
            sev_icon = {"extreme": "🔴", "severe": "🟠", "moderate": "🟡", "minor": "🔵"}.get(sev, "⚪")
            ctk.CTkLabel(title_row, text=f"{sev_icon} {sev_label}预警",
                         text_color=color, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
            ctk.CTkLabel(title_row, text=a.get("headline", ""),
                         font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=6)

            # 发布机构
            sender = a.get("senderName", "")
            if sender:
                ctk.CTkLabel(card, text=sender,
                             font=ctk.CTkFont(size=10), text_color="gray").pack(anchor="w", padx=8)

            # 描述（截取前 120 字）
            desc = a.get("description", "")
            if desc:
                ctk.CTkLabel(card, text=desc[:120], wraplength=340,
                             font=ctk.CTkFont(size=11), anchor="w", justify="left").pack(
                    anchor="w", padx=8, pady=(2, 0))

            # 时间
            eff = a.get("effectiveTime", "")[:16].replace("T", " ")
            exp = a.get("expireTime", "")[:16].replace("T", " ")
            if eff and exp:
                ctk.CTkLabel(card, text=f"📅 {eff} → {exp}",
                             font=ctk.CTkFont(size=10), text_color="gray").pack(anchor="w", padx=8, pady=(2, 4))

    def _save_ty_settings(self):
        try:
            _cfg.config["typhoon_alert_km"] = int(self.ty_alert_km.get())
        except:
            _cfg.config["typhoon_alert_km"] = 800
        _cfg.config["typhoon_alert_enabled"] = bool(self.ty_alert_switch.get())
        save_config(_cfg.config)
        write_log("系统", "台风预警设置已更新")

    def _save_adjust(self):
        """保存自动调温开关状态"""
        _cfg.config["auto_adjust"] = bool(self.adjust_switch.get())
        save_config(_cfg.config)
        with _sched_lock:
            register_all_jobs()
        write_log("系统", f"自动调温: {'已开启' if _cfg.config['auto_adjust'] else '已关闭'}")

    def _open_zoom_earth(self):
        import webbrowser
        lat, lon = _cfg.LOCATION["lat"], _cfg.LOCATION["lon"]
        url = f"https://zoom.earth/#view={lat},{lon},8z"
        webbrowser.open(url)
        self.send_status.configure(text="🌍 卫星云图已在浏览器打开", text_color="#27AE60")
        self.after(2000, lambda: self.send_status.configure(text=""))

    def _schedule_wx_refresh(self):
        WX_INTERVAL = 10 * 60 * 1000
        if self._wx_timer_id:
            self.after_cancel(self._wx_timer_id)
        self._wx_timer_id = self.after(WX_INTERVAL, self._auto_wx_refresh)

    def _auto_wx_refresh(self):
        self._refresh_weather()
        self._schedule_wx_refresh()

    def _refresh_weather(self):
        w = fetch_weather()
        if w:
            _cfg._cached_temp = float(w["temp"])
            self.wx_temp.configure(text=f"{w['temp']}°C")
            info = f"{w['text']}  |  体感 {w['feelsLike']}°C  |  湿度 {w['humidity']}%  |  {w['windDir']} {w['windScale']}级"
            self.wx_info.configure(text=info)
            self.wx_obs.configure(text=f"观测时间: {w['obsTime']}")
            write_log("天气", f"{w['temp']}°C {w['text']} 湿度{w['humidity']}% {w['windDir']}{w['windScale']}级")
        else:
            self.wx_info.configure(text="获取失败")
        # 同时刷新预警信息（共用天气 API Host，省调用次数）
        self._refresh_alerts()

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
            self.after(0, lambda: self._ask_repair(err_msg))
        self.after(2000, lambda: self.send_status.configure(text=""))

    def _ask_repair(self, err_msg):
        if messagebox.askyesno("发送失败", f"{err_msg}\n\n是否进入修复程序？"):
            self._repair_dialog()

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

            add_line("┌─ Python 环境 ────────", "#888")
            ver = sys.version.split()[0]
            add_line(f"│ ✅ Python {ver}", "#27AE60")
            add_line(f"│    {sys.executable}", "#888")
            add_line("└──────────────────────", "#888")

            add_line("┌─ 依赖库 ─────────────", "#888")
            for pkg_name in ["broadlink", "hvac_ir", "customtkinter", "schedule", "tkcalendar"]:
                try:
                    mod = __import__(pkg_name)
                    ver_str = getattr(mod, "__version__", "OK")
                    add_line(f"│ ✅ {pkg_name} {ver_str}", "#27AE60")
                except Exception:
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

            add_line("┌─ 和风天气 API ───────", "#888")
            w = fetch_weather()
            if w:
                add_line(f"│ ✅ {w['temp']}°C {w['text']} (观测 {w['obsTime']})", "#27AE60")
            else:
                add_line("│ ❌ API 无响应 (请检查网络连接)", "#E74C3C")
                all_ok = False
            add_line("└──────────────────────", "#888")

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

        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(pady=(8, 10))
        ctk.CTkButton(btn_frame, text="🔄 重新检测", fg_color="#4A90D9",
                      command=run_diagnosis).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="关闭", fg_color="#666", command=dlg.destroy).pack(side="left", padx=5)

        run_diagnosis()

    def _device_guide(self):
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
        _cfg.config["trigger_time"] = t
        _cfg.config["schedule_enabled"] = bool(self.sched_switch.get())

        oh = self.off_hour_combo.get()
        om = self.off_min_combo.get()
        _cfg.config["off_time"] = f"{oh}:{om}"
        _cfg.config["off_enabled"] = bool(self.off_switch.get())

        save_config(_cfg.config)
        with _sched_lock:
            register_all_jobs()
        write_log("系统",
                  f"定时已更新: 开机 {t} {'(启用)' if _cfg.config['schedule_enabled'] else '(停用)'}  "
                  f"关机 {_cfg.config['off_time']} {'(启用)' if _cfg.config.get('off_enabled') else '(停用)'}")
        self._update_sched_status()
        self._update_off_status()

    def _trigger_now(self):
        try:
            result = scheduled_job()
            if result:
                self.send_status.configure(text=f"✅ {result}", text_color="#27AE60")
            else:
                self.send_status.configure(text="⏸️ 规则判定无需操作", text_color="gray")
                write_log("系统", "手动触发: 规则判定无需操作或天气获取失败")
        except Exception as e:
            self.send_status.configure(text=f"❌ {e}", text_color="#E74C3C")
            write_log("系统", f"手动触发失败: {e}")
        self.after(3000, lambda: self.send_status.configure(text=""))

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

            dist = calc_distance(_cfg.LOCATION["lat"], _cfg.LOCATION["lon"], detail["lat"], detail["lon"])
            alert = dist < _cfg.config.get("typhoon_alert_km", 800)
            status = "⚠️ 预警" if alert else "✅ 安全"
            status_color = "#E74C3C" if alert else "#27AE60"

            card = ctk.CTkFrame(self.ty_list)
            card.pack(fill="x", padx=5, pady=5, ipady=5)

            title_row = ctk.CTkFrame(card, fg_color="transparent")
            title_row.pack(fill="x", padx=10, pady=(5, 3))
            ctk.CTkLabel(title_row, text=f"🌀 {detail['cn']}  {detail['eng']}",
                         font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
            ctk.CTkLabel(title_row, text=f"#{detail['code']}",
                         font=ctk.CTkFont(size=12), text_color="gray").pack(side="left", padx=8)
            ctk.CTkLabel(title_row, text=status, text_color=status_color,
                         font=ctk.CTkFont(size=12, weight="bold")).pack(side="right")

            d1 = ctk.CTkFrame(card, fg_color="transparent")
            d1.pack(fill="x", padx=10)
            ctk.CTkLabel(d1, text=f"等级: {detail['cat']}  |  气压: {detail['pressure']}hPa  |  "
                                  f"风速: {detail['wind']}m/s").pack(anchor="center")
            ctk.CTkLabel(d1, text=f"位置: {detail['lat']}°N, {detail['lon']}°E  |  "
                                  f"移向: {detail['direction']}  |  移速: {detail['speed']}km/h").pack(anchor="center")
            ctk.CTkLabel(d1, text=f"距{_cfg.LOCATION['name']}: {dist}km").pack(anchor="center")

            if detail["forecasts"]:
                d2 = ctk.CTkFrame(card, fg_color="transparent")
                d2.pack(fill="x", padx=10, pady=(3, 8))
                ctk.CTkLabel(d2, text="路径预报:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="center")
                for fc in detail["forecasts"][:4]:
                    ctk.CTkLabel(d2, text=f"  +{fc['hours']}h → {fc['lat']}°N, {fc['lon']}°E  "
                                          f"{fc['pressure']}hPa  {fc['wind']}m/s  {fc['cat']}",
                                 font=ctk.CTkFont(size=11)).pack(anchor="center")

            self.ty_time_label.configure(text=f"更新时间: {detail['update_time']}")

            if alert and _cfg.config.get("typhoon_alert_enabled", True):
                messagebox.showwarning("台风预警",
                                       f"{detail['cn']} ({detail['cat']})\n"
                                       f"距{_cfg.LOCATION['name']}仅 {dist}km\n请关注中央气象台最新预报")

            write_log("台风", f"{detail['cn']} {detail['cat']} {detail['lat']}N,{detail['lon']}E 距{dist}km {status}")

        self.ty_time_label.configure(text=f"上次更新: {datetime.now():%H:%M}")
