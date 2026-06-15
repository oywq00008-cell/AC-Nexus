"""日志查看对话框模块"""

import platform
import subprocess
import os
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox
from tkcalendar import Calendar

from broadlinkac_core.config import LOG_DIR
from broadlinkac_core.logger import get_log_dates


class LogDialog:
    """日志查看对话框"""
    
    def __init__(self, parent):
        self.parent = parent
        
    def show(self):
        """显示日志对话框"""
        dates = get_log_dates()
        if not dates:
            messagebox.showinfo("日志", "暂无日志记录。")
            return

        dlg = ctk.CTkToplevel(self.parent)
        dlg.title("📅 选择日期")
        self._center_on_parent(dlg, 300, 320)
        dlg.resizable(False, False)
        dlg.transient(self.parent)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="选择日期查看日志", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))

        cal = Calendar(dlg, selectmode="day", date_pattern="yyyy-mm-dd",
                       firstweekday="monday", showweeknumbers=False)
        cal.pack(padx=20, pady=10)

        # 日历配色适配主题
        is_dark = ctk.get_appearance_mode() == "Dark"
        if is_dark:
            cal.configure(
                background="#2b2b2b", foreground="#4A90D9",
                headersbackground="#333333", headersforeground="#4A90D9",
                normalbackground="#2b2b2b", normalforeground="#4A90D9",
                weekendbackground="#2b2b2b", weekendforeground="#4A90D9",
                othermonthbackground="#2b2b2b", othermonthforeground="#555555",
                selectbackground="#1a3a5c", selectforeground="white",
            )
            log_bg, log_fg = "#4a1a1a", "#E74C3C"
        else:
            cal.configure(
                foreground="#4A90D9",
                normalforeground="#4A90D9",
                weekendforeground="#4A90D9",
                othermonthforeground="#333333",
            )
            log_bg, log_fg = "#FADBD8", "#E74C3C"

        for d in dates:
            try:
                cal.calevent_create(datetime.strptime(d, "%Y-%m-%d"), "", "log")
                cal.tag_config("log", background=log_bg, foreground=log_fg)
            except:
                pass

        def on_open():
            date = cal.get_date()
            dlg.destroy()
            log_path = LOG_DIR / f"{date}.md"
            if os.name == "nt":
                os.startfile(str(log_path))
            else:
                subprocess.run(["open", str(log_path)])

        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(pady=(5, 10))
        ctk.CTkButton(btn_frame, text="取消", fg_color="gray", command=dlg.destroy).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="打开日志", command=on_open).pack(side="left", padx=5)
    
    def _center_on_parent(self, child, width, height):
        """将弹窗居中于主窗口（先隐藏定位后再显示，避免闪烁）"""
        child.withdraw()
        child.update_idletasks()
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() - width) // 2
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() - height) // 2
        child.geometry(f"{width}x{height}+{x}+{y}")
        child.deiconify()