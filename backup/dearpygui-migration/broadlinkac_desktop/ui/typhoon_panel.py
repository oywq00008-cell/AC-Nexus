"""台风监测面板模块"""

import customtkinter as ctk
from tkinter import Canvas

import broadlinkac_core.config as _cfg
from broadlinkac_core.typhoon import fetch_typhoons, fetch_typhoon_detail, calc_distance


class TyphoonPanel:
    """台风监测面板"""
    
    def __init__(self, parent):
        self.parent = parent
        self._ty_page = 0
        self._ty_data = []
        self.app = None
        
    def build(self, tab, app=None):
        """构建台风监测面板"""
        if app:
            self.app = app
        # 台风信息卡片
        typhoon_card = ctk.CTkFrame(tab)
        typhoon_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        typhoon_card.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(typhoon_card, text="🌀 台风监测", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="center", padx=12, pady=(10, 5))
        
        # 台风源切换
        source_frame = ctk.CTkFrame(typhoon_card, fg_color="transparent")
        source_frame.pack(fill="x", padx=12, pady=5)
        
        ctk.CTkLabel(source_frame, text="数据源:").pack(side="left")
        self.ty_source_combo = ctk.CTkComboBox(source_frame, values=["NMC", "NHC"], width=100)
        self.ty_source_combo.pack(side="left", padx=5)
        
        ctk.CTkButton(source_frame, text="刷新台风", fg_color="#4A90D9",
                      command=self._fetch_typhoon_all).pack(side="right")
        
        # 台风状态
        self.ty_status = ctk.CTkLabel(typhoon_card, text="正在加载...", font=ctk.CTkFont(size=12))
        self.ty_status.pack(anchor="w", padx=12, pady=5)
        
        # 台风路径图
        path_card = ctk.CTkFrame(tab)
        path_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        path_card.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        ctk.CTkLabel(path_card, text="📍 路径预报", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="center", padx=12, pady=(10, 5))
        
        # 路径画布
        self.canvas = Canvas(path_card, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # 翻页控制
        page_frame = ctk.CTkFrame(path_card, fg_color="transparent")
        page_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self._ty_page_prev = ctk.CTkButton(page_frame, text="◀ 上一个", width=80, fg_color="#555",
                                            command=self._ty_prev_page)
        self._ty_page_prev.pack(side="left")
        
        self._ty_page_label = ctk.CTkLabel(page_frame, text="第 0/0 页", font=ctk.CTkFont(size=12))
        self._ty_page_label.pack(side="left", expand=True)
        
        self._ty_page_next = ctk.CTkButton(page_frame, text="下一个 ▶", width=80, fg_color="#555",
                                            command=self._ty_next_page)
        self._ty_page_next.pack(side="right")
        
        # 台风详情
        detail_card = ctk.CTkFrame(tab)
        detail_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        detail_card.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(detail_card, text="📋 台风详情", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="center", padx=12, pady=(10, 5))
        
        self.detail_text = ctk.CTkTextbox(detail_card, height=100)
        self.detail_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    def _fetch_typhoon_all(self):
        """获取台风数据"""
        if self.app and hasattr(self.app, '_fetch_typhoon_all'):
            self.app._fetch_typhoon_all()
    
    def _ty_prev_page(self):
        """上一个台风"""
        if self._ty_page > 0:
            self._ty_page -= 1
            self._render_typhoon()
    
    def _ty_next_page(self):
        """下一个台风"""
        if self._ty_page < len(self._ty_data) - 1:
            self._ty_page += 1
            self._render_typhoon()
    
    def update_typhoon_data(self, typhoons):
        """更新台风数据"""
        self._ty_data = typhoons or []
        self._ty_page = 0
        self._render_typhoon()
    
    def _render_typhoon(self):
        """渲染台风路径"""
        # 清空画布
        self.canvas.delete("all")
        
        if not self._ty_data:
            self.ty_status.configure(text="暂无台风数据")
            self._ty_page_label.configure(text="第 0/0 页")
            return
        
        # 更新状态
        total_pages = len(self._ty_data)
        self.ty_status.configure(text=f"共 {total_pages} 个台风")
        self._ty_page_label.configure(text=f"第 {self._ty_page + 1}/{total_pages} 页")
        
        # 更新按钮状态
        self._ty_page_prev.configure(state="normal" if self._ty_page > 0 else "disabled")
        self._ty_page_next.configure(state="normal" if self._ty_page < total_pages - 1 else "disabled")
        
        # 获取当前台风数据
        typhoon = self._ty_data[self._ty_page]
        
        # 绘制台风路径
        self._draw_typhoon_path(typhoon)
        
        # 更新详情
        self._update_typhoon_detail(typhoon)
    
    def _draw_typhoon_path(self, typhoon):
        """绘制台风路径"""
        # 这里需要实现台风路径绘制逻辑
        # 暂时显示台风名称
        self.canvas.create_text(150, 100, text=typhoon.get('name', '未知台风'),
                                fill="white", font=("Arial", 14))
    
    def _update_typhoon_detail(self, typhoon):
        """更新台风详情"""
        self.detail_text.delete("1.0", "end")
        
        detail = f"名称: {typhoon.get('name', '未知')}\n"
        detail += f"等级: {typhoon.get('level', '未知')}\n"
        detail += f"位置: {typhoon.get('lat', '—')}°N, {typhoon.get('lon', '—')}°E\n"
        detail += f"风速: {typhoon.get('wind', '—')} 米/秒\n"
        detail += f"移动: {typhoon.get('move', '未知')}\n"
        
        # 计算距离
        if 'lat' in typhoon and 'lon' in typhoon:
            dist = calc_distance(typhoon['lat'], typhoon['lon'],
                                _cfg.LOCATION['lat'], _cfg.LOCATION['lon'])
            detail += f"距{_cfg.LOCATION['name']}: {dist:.0f} 公里\n"
        
        self.detail_text.insert("1.0", detail)