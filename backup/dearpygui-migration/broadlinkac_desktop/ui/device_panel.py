"""设备管理面板模块"""

import customtkinter as ctk
from tkinter import messagebox

import broadlinkac_core.config as _cfg
from broadlinkac_core.config import get_device_list, switch_device, add_or_update_device, save_config
from broadlinkac_core.ac_control import discover_devices


class DevicePanel:
    """设备管理面板"""
    
    def __init__(self, parent):
        self.parent = parent
        
    def build(self, tab):
        """构建设备管理面板"""
        # 设备列表卡片
        device_card = ctk.CTkFrame(tab)
        device_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        device_card.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(device_card, text="📡 设备管理", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="center", padx=12, pady=(10, 5))
        
        # 设备选择
        select_frame = ctk.CTkFrame(device_card, fg_color="transparent")
        select_frame.pack(fill="x", padx=12, pady=5)
        
        ctk.CTkLabel(select_frame, text="当前设备:").pack(side="left")
        self.device_combo = ctk.CTkComboBox(select_frame, values=[], width=200)
        self.device_combo.pack(side="left", padx=5)
        self.device_combo.bind("<<ComboboxSelected>>", self._on_device_switch)
        
        # 设备操作按钮
        btn_frame = ctk.CTkFrame(device_card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=5)
        
        ctk.CTkButton(btn_frame, text="🔍 扫描设备", fg_color="#4A90D9",
                      command=self._scan_devices).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="✏️ 重命名", fg_color="#E67E22",
                      command=self._rename_device).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="🗑️ 删除", fg_color="#E74C3C",
                      command=self._delete_device).pack(side="left", padx=2)
        
        # 设备信息卡片
        info_card = ctk.CTkFrame(tab)
        info_card.configure(border_width=1, border_color="#4A4A4A", corner_radius=8)
        info_card.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        ctk.CTkLabel(info_card, text="📋 设备信息", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="center", padx=12, pady=(10, 5))
        
        # 设备信息显示
        self.info_frame = ctk.CTkFrame(info_card, fg_color="transparent")
        self.info_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # 设备详情
        self.device_info = ctk.CTkTextbox(info_card, height=150)
        self.device_info.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # 刷新设备列表
        self._refresh_device_list()
    
    def _refresh_device_list(self):
        """刷新设备列表"""
        devices = get_device_list()
        device_names = [f"{name} ({mac[:8]}...)" for mac, name in devices]
        
        self.device_combo.configure(values=device_names)
        if device_names:
            self.device_combo.set(device_names[0])
        
        # 更新设备信息
        self._update_device_info()
    
    def _on_device_switch(self, event):
        """设备切换事件"""
        selection = self.device_combo.get()
        if not selection:
            return
        
        # 从选择中提取MAC地址
        devices = get_device_list()
        for mac, name in devices:
            if f"{name} ({mac[:8]}...)" == selection:
                switch_device(mac)
                self._update_device_info()
                break
    
    def _scan_devices(self):
        """扫描设备"""
        try:
            devices = discover_devices(timeout=5)
            if devices:
                for device in devices:
                    mac = device.mac.hex() if isinstance(device.mac, bytes) else str(device.mac)
                    add_or_update_device(mac, {
                        "host": device.host[0],
                        "port": device.host[1],
                        "mac": mac,
                        "model": device.model,
                        "name": device.model or device.name,
                    })
                save_config(_cfg.config)
                self._refresh_device_list()
                messagebox.showinfo("扫描完成", f"发现 {len(devices)} 个设备")
            else:
                messagebox.showwarning("扫描完成", "未发现设备")
        except Exception as e:
            messagebox.showerror("扫描失败", f"扫描设备失败: {e}")
    
    def _rename_device(self):
        """重命名设备"""
        selection = self.device_combo.get()
        if not selection:
            messagebox.showwarning("提示", "请先选择设备")
            return
        
        # 获取当前设备名称
        devices = get_device_list()
        current_name = ""
        current_mac = ""
        for mac, name in devices:
            if f"{name} ({mac[:8]}...)" == selection:
                current_name = name
                current_mac = mac
                break
        
        if not current_mac:
            return
        
        # 弹出重命名对话框
        dlg = ctk.CTkToplevel(self.parent)
        dlg.title("重命名设备")
        dlg.geometry("300x150")
        dlg.transient(self.parent)
        dlg.grab_set()
        
        ctk.CTkLabel(dlg, text="设备名称:").pack(pady=(20, 5))
        name_entry = ctk.CTkEntry(dlg, width=250)
        name_entry.insert(0, current_name)
        name_entry.pack(pady=5)
        
        def do_rename():
            new_name = name_entry.get().strip()
            if new_name:
                # 更新设备名称
                device = _cfg.config["devices"][current_mac]
                device["name"] = new_name
                save_config(_cfg.config)
                self._refresh_device_list()
                dlg.destroy()
                messagebox.showinfo("成功", "设备已重命名")
        
        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text="取消", fg_color="gray", command=dlg.destroy).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="确定", command=do_rename).pack(side="left", padx=5)
    
    def _delete_device(self):
        """删除设备"""
        selection = self.device_combo.get()
        if not selection:
            messagebox.showwarning("提示", "请先选择设备")
            return
        
        # 确认删除
        if not messagebox.askyesno("确认删除", f"确定要删除设备 {selection} 吗？"):
            return
        
        # 获取设备MAC
        devices = get_device_list()
        for mac, name in devices:
            if f"{name} ({mac[:8]}...)" == selection:
                # 删除设备
                del _cfg.config["devices"][mac]
                
                # 如果删除的是当前设备，切换到第一个设备
                if _cfg.config.get("current_device_mac") == mac:
                    if _cfg.config["devices"]:
                        first_mac = next(iter(_cfg.config["devices"]))
                        _cfg.config["current_device_mac"] = first_mac
                    else:
                        _cfg.config["current_device_mac"] = ""
                
                save_config(_cfg.config)
                self._refresh_device_list()
                messagebox.showinfo("成功", "设备已删除")
                break
    
    def _update_device_info(self):
        """更新设备信息显示"""
        self.device_info.delete("1.0", "end")
        
        current_mac = _cfg.config.get("current_device_mac", "")
        if not current_mac or current_mac not in _cfg.config.get("devices", {}):
            self.device_info.insert("1.0", "未选择设备")
            return
        
        device = _cfg.config["devices"][current_mac]
        
        info = f"设备名称: {device.get('name', '未知')}\n"
        info += f"品牌: {device.get('brand', '未知')}\n"
        info += f"型号: {device.get('model', '未知')}\n"
        info += f"MAC地址: {current_mac}\n"
        info += f"IP地址: {device.get('host', '未知')}\n"
        info += f"端口: {device.get('port', '未知')}\n"
        info += f"风速: {device.get('fan', 'auto')}\n"
        info += f"定时开机: {'启用' if device.get('schedule_enabled') else '禁用'}\n"
        info += f"定时关机: {'启用' if device.get('off_enabled') else '禁用'}\n"
        info += f"自动调温: {'启用' if device.get('auto_adjust') else '禁用'}\n"
        
        self.device_info.insert("1.0", info)