"""温度规则编辑对话框模块"""

import customtkinter as ctk
from tkinter import messagebox

import broadlinkac_core.config as _cfg
from broadlinkac_core.config import get_current_device, save_config


class RulesDialog:
    """温度规则编辑对话框"""
    
    def __init__(self, parent):
        self.parent = parent
        
    def show(self):
        """显示温度规则编辑对话框"""
        dev = get_current_device()
        rules = dev.get("temp_rules", [])
        
        dlg = ctk.CTkToplevel(self.parent)
        dlg.title("🌡️ 温度规则")
        self._center_on_parent(dlg, 400, 350)
        dlg.transient(self.parent)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="室外温度 → 空调设置", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))

        # 规则表格
        table_frame = ctk.CTkFrame(dlg)
        table_frame.pack(fill="both", expand=True, padx=15, pady=10)

        # 表头
        headers = ["最低°C", "最高°C", "目标°C", "模式"]
        for i, header in enumerate(headers):
            ctk.CTkLabel(table_frame, text=header, font=ctk.CTkFont(size=12, weight="bold")).grid(
                row=0, column=i, padx=5, pady=5, sticky="ew")

        # 规则行
        entries = []
        for i, rule in enumerate(rules):
            row_entries = []
            for j, value in enumerate(rule):
                entry = ctk.CTkEntry(table_frame, width=60)
                entry.insert(0, str(value))
                entry.grid(row=i+1, column=j, padx=5, pady=2, sticky="ew")
                row_entries.append(entry)
            entries.append(row_entries)

        def save():
            new_rules = []
            for row_entries in entries:
                try:
                    low = int(row_entries[0].get())
                    high = int(row_entries[1].get())
                    temp = int(row_entries[2].get())
                    mode = row_entries[3].get()
                    new_rules.append([low, high, temp, mode])
                except ValueError:
                    messagebox.showerror("错误", "请输入有效的数字")
                    return
            
            dev = get_current_device()
            dev["temp_rules"] = new_rules
            save_config(_cfg.config)
            dlg.destroy()
            messagebox.showinfo("成功", "温度规则已保存")

        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(pady=(5, 15))
        ctk.CTkButton(btn_frame, text="取消", fg_color="gray", command=dlg.destroy).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="保存", command=save).pack(side="left", padx=5)
    
    def _center_on_parent(self, child, width, height):
        """将子窗口居中到父窗口"""
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2
        
        child.geometry(f"{width}x{height}+{x}+{y}")