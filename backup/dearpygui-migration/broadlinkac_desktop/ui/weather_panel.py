"""天气面板模块"""

import customtkinter as ctk
import webbrowser

import broadlinkac_core.config as _cfg
from broadlinkac_core.weather import fetch_weather, fetch_weather_alerts


class WeatherPanel:
    """天气面板"""
    
    def __init__(self, parent):
        self.parent = parent
        self.app = None
        
    def build(self, tab, app=None):
        """构建天气面板"""
        if app:
            self.app = app
        # 天气卡片
        weather_card = ctk.CTkFrame(tab)
        weather_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        weather_card.pack(fill="x", padx=10, pady=10)
        
        self._weather_card_label = ctk.CTkLabel(weather_card, text=f"🌤️ {_cfg.LOCATION['name']}天气",
                                                 font=ctk.CTkFont(size=14, weight="bold"))
        self._weather_card_label.pack(anchor="center", padx=12, pady=(10, 2))
        
        # 天气信息
        info_frame = ctk.CTkFrame(weather_card, fg_color="transparent")
        info_frame.pack(fill="x", padx=12, pady=5)
        
        # 左侧：温度
        left_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        left_frame.pack(side="left", fill="x", expand=True)
        
        self.wx_temp = ctk.CTkLabel(left_frame, text="—°C", font=ctk.CTkFont(size=36, weight="bold"))
        self.wx_temp.pack(anchor="w")
        
        self.wx_info = ctk.CTkLabel(left_frame, text="点击刷新", font=ctk.CTkFont(size=12))
        self.wx_info.pack(anchor="w")
        
        # 右侧：详细信息
        right_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        right_frame.pack(side="right", fill="x", expand=True)
        
        self.wx_detail = ctk.CTkLabel(right_frame, text="", font=ctk.CTkFont(size=11))
        self.wx_detail.pack(anchor="e")
        
        self.wx_obs = ctk.CTkLabel(right_frame, text="", font=ctk.CTkFont(size=10), text_color="gray")
        self.wx_obs.pack(anchor="e")
        
        # API 未配置时的帮助链接
        self.wx_link = ctk.CTkLabel(weather_card, text="", font=ctk.CTkFont(size=14),
                                     text_color=["#2E86C1", "#5DADE2"], cursor="hand2")
        self.wx_link.pack(pady=(0, 8))
        self.wx_link.pack_forget()
        self.wx_link.bind("<Button-1>", lambda e: webbrowser.open("https://console.qweather.com"))
        
        # 刷新按钮
        ctk.CTkButton(weather_card, text="🔄 刷新天气", fg_color="#4A90D9",
                      command=self._fetch_weather_all).pack(pady=(5, 10))
        
        # 预警信息卡片
        alert_card = ctk.CTkFrame(tab)
        alert_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        alert_card.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        ctk.CTkLabel(alert_card, text="⚠️ 预警信息", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="center", padx=12, pady=(10, 5))
        
        # 预警列表
        self.alert_frame = ctk.CTkScrollableFrame(alert_card, height=200)
        self.alert_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # 预警源切换
        source_frame = ctk.CTkFrame(alert_card, fg_color="transparent")
        source_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(source_frame, text="数据源:").pack(side="left")
        self.alert_source_combo = ctk.CTkComboBox(source_frame, values=["百度API", "和风API"], width=100)
        self.alert_source_combo.pack(side="left", padx=5)
        
        ctk.CTkButton(source_frame, text="刷新预警", fg_color="#4A90D9",
                      command=self._fetch_alerts).pack(side="right")
    
    def _fetch_weather_all(self):
        """刷新天气"""
        if self.app and hasattr(self.app, '_fetch_weather_all'):
            self.app._fetch_weather_all()
    
    def _fetch_alerts(self):
        """获取预警信息"""
        if self.app and hasattr(self.app, '_fetch_alerts'):
            self.app._fetch_alerts()
    
    def update_weather(self, weather_data):
        """更新天气显示"""
        if weather_data:
            self.wx_temp.configure(text=f"{weather_data.get('temp', '—')}°C")
            self.wx_info.configure(text=weather_data.get('text', ''))
            self.wx_detail.configure(text=f"湿度: {weather_data.get('humidity', '—')}%")
            self.wx_obs.configure(text=f"更新时间: {weather_data.get('obs_time', '')}")
        else:
            self.wx_temp.configure(text="—°C")
            self.wx_info.configure(text="获取失败")
    
    def update_alerts(self, alerts):
        """更新预警显示"""
        # 清空现有预警
        for widget in self.alert_frame.winfo_children():
            widget.destroy()
        
        if not alerts:
            ctk.CTkLabel(self.alert_frame, text="暂无预警信息", font=ctk.CTkFont(size=12)).pack(pady=20)
            return
        
        for alert in alerts:
            alert_item = ctk.CTkFrame(self.alert_frame)
            alert_item.pack(fill="x", pady=2)
            
            # 预警标题
            title = alert.get('title', '未知预警')
            level = alert.get('level', '')
            color = self._get_alert_color(level)
            
            ctk.CTkLabel(alert_item, text=title, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=color).pack(anchor="w", padx=5, pady=2)
            
            # 预警详情
            detail = alert.get('detail', '')
            if detail:
                ctk.CTkLabel(alert_item, text=detail, font=ctk.CTkFont(size=10),
                             text_color="gray").pack(anchor="w", padx=5, pady=(0, 2))
    
    def _get_alert_color(self, level):
        """根据预警等级返回颜色"""
        level_colors = {
            '蓝': '#0000FF',
            '黄': '#FFFF00',
            '橙': '#FFA500',
            '红': '#FF0000',
        }
        return level_colors.get(level, '#FFFFFF')