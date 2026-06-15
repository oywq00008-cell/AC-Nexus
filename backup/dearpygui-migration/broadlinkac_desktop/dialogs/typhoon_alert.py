"""台风预警弹窗模块"""

import customtkinter as ctk
from tkinter import BooleanVar, Toplevel

import broadlinkac_core.config as _cfg


class TyphoonAlert:
    """台风预警弹窗"""
    
    def __init__(self, parent):
        self.parent = parent
        self.muted = False
        
    def show(self, detail, dist):
        """显示台风预警弹窗，10秒倒计时自动关闭，支持本次启动不再显示"""
        if self.muted:
            return
            
        dlg = Toplevel(self.parent)
        dlg.title("🌀 台风预警")
        dlg.transient(self.parent)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text=f"{detail['cn']}  {detail['eng']}",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(15, 3))
        ctk.CTkLabel(dlg, text=f"{detail['cat']}  |  距{_cfg.LOCATION['name']}仅 {dist}km",
                     font=ctk.CTkFont(size=12), text_color="#E74C3C").pack()
        ctk.CTkLabel(dlg, text="请关注中央气象台最新预报",
                     font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(5, 10))

        mute_var = BooleanVar(value=False)
        ctk.CTkCheckBox(dlg, text="本次启动不再显示", variable=mute_var).pack(pady=(0, 5))

        countdown_label = ctk.CTkLabel(dlg, text="10 秒后自动关闭",
                                       font=ctk.CTkFont(size=11), text_color="gray")
        countdown_label.pack(pady=(0, 8))

        def on_ok():
            if mute_var.get():
                self.muted = True
            dlg.destroy()

        ctk.CTkButton(dlg, text="确定", width=100, command=on_ok).pack(pady=(0, 10))

        def tick(remaining):
            if not dlg.winfo_exists():
                return
            if remaining <= 0:
                # 挂机无人操作 → 静音
                self.muted = True
                dlg.destroy()
                return
            countdown_label.configure(text=f"{remaining} 秒后自动关闭")
            dlg.after(1000, tick, remaining - 1)

        dlg.after(1000, tick, 9)
        self._center_on_parent(dlg, 360, 230)
    
    def _center_on_parent(self, child, width, height):
        """将子窗口居中到父窗口"""
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2
        
        child.geometry(f"{width}x{height}+{x}+{y}")