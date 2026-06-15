"""空调控制面板模块"""

import customtkinter as ctk
import webbrowser

import broadlinkac_core.config as _cfg
from broadlinkac_core.config import get_current_device, AC_BRANDS
from broadlinkac_core.ac_control import MODES, FANS, send_ac
from ..utils.assets import get_asset


class AcPanel:
    """空调控制面板"""
    
    def __init__(self, parent):
        self.parent = parent
        self._temp_val = 26
        self.app = None  # 将在build时设置
        
    def build(self, tab, app=None):
        """构建空调控制面板"""
        if app:
            self.app = app
        grid_frame = ctk.CTkFrame(tab, fg_color="transparent")
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

        # API 未配置时的帮助链接
        self.wx_link = ctk.CTkLabel(weather_card, text="", font=ctk.CTkFont(size=14),
                                     text_color=["#2E86C1", "#5DADE2"], cursor="hand2")
        self.wx_link.pack(pady=(0, 8))
        self.wx_link.pack_forget()
        self.wx_link.bind("<Button-1>", lambda e: webbrowser.open("https://console.qweather.com"))
        ctk.CTkButton(weather_card, text="🔄 刷新天气", fg_color="#4A90D9",
                      command=self._fetch_weather_all).pack(pady=(5, 10))

        # 右上: 控制
        ctrl_card = ctk.CTkFrame(grid_frame)
        ctrl_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        ctrl_card.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)

        self._ctrl_card_label = ctk.CTkLabel(ctrl_card,
            text=f"🎮 {get_current_device().get('brand', '格力')}空调控制",
            font=ctk.CTkFont(size=14, weight="bold"))
        self._ctrl_card_label.pack(anchor="center", padx=12, pady=(10, 5))

        # 控制主体：左列控件 + 右列 Logo
        body = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=(12, 8), pady=(0, 10))
        body.grid_columnconfigure(0, weight=1)

        controls = ctk.CTkFrame(body, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="nsew")

        self.brand_logo_label = ctk.CTkLabel(body, text="")
        self.brand_logo_label.grid(row=0, column=1, padx=(5, 5), sticky="w")

        row1 = ctk.CTkFrame(controls, fg_color="transparent")
        row1.pack(fill="x", pady=2)
        ctk.CTkLabel(row1, text="电源:", width=45).pack(side="left")
        self.power_switch = ctk.CTkSwitch(row1, text="")
        self.power_switch.pack(side="left")
        self.power_switch.select()

        row2 = ctk.CTkFrame(controls, fg_color="transparent")
        row2.pack(fill="x", pady=2)
        ctk.CTkLabel(row2, text="模式:", width=45).pack(side="left")
        self.mode_combo = ctk.CTkComboBox(row2, values=[k for k in MODES if k != "关闭"], width=100)
        self.mode_combo.set("制冷")
        self.mode_combo.pack(side="left")

        row3 = ctk.CTkFrame(controls, fg_color="transparent")
        row3.pack(fill="x", pady=2)
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

        row4 = ctk.CTkFrame(controls, fg_color="transparent")
        row4.pack(fill="x", pady=2)
        ctk.CTkLabel(row4, text="风速:", width=45).pack(side="left")
        self.fan_combo = ctk.CTkComboBox(row4, values=list(FANS.keys()), width=100)
        self.fan_combo.set("自动")
        self.fan_combo.pack(side="left")

        # 发送按钮
        send_frame = ctk.CTkFrame(body, fg_color="transparent")
        send_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ctk.CTkButton(send_frame, text="📡 发送指令", fg_color="#2E7D32", height=32,
                      command=self._on_send_click).pack(fill="x")
        
        # 左下: 预警信息
        alert_card = ctk.CTkFrame(grid_frame)
        alert_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        alert_card.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        
        ctk.CTkLabel(alert_card, text="⚠️ 预警信息", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="center", padx=12, pady=(10, 5))
        self.alert_text = ctk.CTkTextbox(alert_card, height=100)
        self.alert_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # 右下: 定时设置
        sched_card = ctk.CTkFrame(grid_frame)
        sched_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        sched_card.grid(row=1, column=1, sticky="nsew", padx=2, pady=2)
        
        ctk.CTkLabel(sched_card, text="⏰ 定时设置", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="center", padx=12, pady=(10, 5))
        
        # 定时开关
        sched_frame = ctk.CTkFrame(sched_card, fg_color="transparent")
        sched_frame.pack(fill="x", padx=10, pady=5)
        
        self.sched_switch = ctk.CTkSwitch(sched_frame, text="定时开机")
        self.sched_switch.pack(side="left")
        
        self.off_switch = ctk.CTkSwitch(sched_frame, text="定时关机")
        self.off_switch.pack(side="right")
        
        # 定时时间
        time_frame = ctk.CTkFrame(sched_card, fg_color="transparent")
        time_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(time_frame, text="开机时间:").pack(side="left")
        self.on_time_entry = ctk.CTkEntry(time_frame, width=80, placeholder_text="12:00")
        self.on_time_entry.pack(side="left", padx=5)
        
        ctk.CTkLabel(time_frame, text="关机时间:").pack(side="left", padx=(10, 0))
        self.off_time_entry = ctk.CTkEntry(time_frame, width=80, placeholder_text="22:00")
        self.off_time_entry.pack(side="left", padx=5)
        
        # 自动调温
        auto_frame = ctk.CTkFrame(sched_card, fg_color="transparent")
        auto_frame.pack(fill="x", padx=10, pady=5)
        
        self.auto_switch = ctk.CTkSwitch(auto_frame, text="自动调温")
        self.auto_switch.pack(side="left")
        
        ctk.CTkButton(auto_frame, text="编辑规则", width=80, fg_color="#4A90D9",
                      command=self._edit_rules).pack(side="right")
        
        # 保存按钮
        ctk.CTkButton(sched_card, text="💾 保存设置", fg_color="#2E7D32",
                      command=self._save_schedule).pack(pady=(10, 15))
    
    def _on_send_click(self):
        """发送空调指令"""
        try:
            power = "on" if self.power_switch.get() else "off"
            mode = MODES.get(self.mode_combo.get(), "cool")
            temp = self._temp_val
            fan = FANS.get(self.fan_combo.get(), "auto")
            
            result = send_ac(power, mode, temp, fan)
            print(f"发送成功: {result}")
        except Exception as e:
            print(f"发送失败: {e}")
    
    def _fetch_weather_all(self):
        """刷新天气"""
        if self.app and hasattr(self.app, '_fetch_weather_all'):
            self.app._fetch_weather_all()
    
    def _edit_rules(self):
        """编辑温度规则"""
        if self.app and hasattr(self.app, 'rules_dialog'):
            self.app.rules_dialog.show()
    
    def _save_schedule(self):
        """保存定时设置"""
        # 这里需要实现保存定时设置的逻辑
        pass