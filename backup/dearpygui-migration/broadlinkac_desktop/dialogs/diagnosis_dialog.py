"""故障诊断对话框模块"""

import platform
import sys
import threading
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox

import broadlinkac_core.config as _cfg
from broadlinkac_core.config import get_current_device, add_or_update_device, save_config
from broadlinkac_core.ac_control import discover_devices, _get_local_ips


class DiagnosisDialog:
    """故障诊断对话框"""
    
    def __init__(self, parent):
        self.parent = parent
        
    def show(self):
        """显示故障诊断对话框"""
        dlg = ctk.CTkToplevel(self.parent)
        dlg.title("🔧 故障诊断")
        self._center_on_parent(dlg, 520, 460)
        dlg.transient(self.parent)

        ctk.CTkLabel(dlg, text="🔧 故障诊断", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))
        result_frame = ctk.CTkScrollableFrame(dlg, height=300)
        result_frame.pack(fill="both", expand=True, padx=15, pady=(5, 0))

        def add_line(text, color="#FFFFFF"):
            lbl = ctk.CTkLabel(result_frame, text=text, font=ctk.CTkFont(size=12),
                               text_color=color, anchor="center")
            lbl.pack(fill="x", pady=1)
            return lbl

        def ui_add_line(text, color="#FFFFFF"):
            """线程安全：将 add_line 投递到主线程"""
            dlg.after(0, lambda t=text, c=color: add_line(t, c))

        def ui_update():
            """线程安全：刷新 UI"""
            dlg.after(0, result_frame.update)

        def run_diagnosis():
            diag_btn.configure(text="⏳ 诊断中...", state="disabled")
            for w in result_frame.winfo_children():
                w.destroy()
            threading.Thread(target=_do_diagnosis, daemon=True).start()

        def _do_diagnosis():
            all_ok = True

            ui_add_line("┌─ Python 环境 ────────", "#888")
            ver = sys.version.split()[0]
            ui_add_line(f"│ ✅ Python {ver}", "#27AE60")
            ui_add_line(f"│    {sys.executable}", "#888")
            ui_add_line("└──────────────────────", "#888")

            ui_add_line("┌─ 依赖库 ─────────────", "#888")
            for pkg_name in ["broadlink", "hvac_ir", "customtkinter", "schedule", "tkcalendar"]:
                try:
                    mod = __import__(pkg_name)
                    ver_str = getattr(mod, "__version__", "OK")
                    ui_add_line(f"│ ✅ {pkg_name} {ver_str}", "#27AE60")
                except Exception:
                    def _show_missing_pkg(p):
                        row = ctk.CTkFrame(result_frame, fg_color="transparent")
                        row.pack(fill="x", pady=1)
                        label = ctk.CTkLabel(row, text=f"│ ❌ {p} 未安装",
                                             font=ctk.CTkFont(size=12), text_color="#E74C3C", anchor="center")
                        label.pack(side="left")
                        ctk.CTkButton(row, text="📦 安装", width=60, height=22,
                                      font=ctk.CTkFont(size=10), fg_color="#E67E22",
                                      command=lambda pkg=p, r=row, lbl=label: fix_pip(pkg, r, lbl, pkg)
                                      ).pack(side="right", padx=(10, 0))
                    dlg.after(0, _show_missing_pkg, pkg_name)
                    all_ok = False
            ui_add_line("└──────────────────────", "#888")

            ui_add_line("┌─ 博联设备扫描 ───────", "#888")
            ui_add_line("│ 🔍 扫描局域网...", "#E67E22")
            ui_update()
            device_found = True

            old_cache = get_current_device()
            old_ip = old_cache.get("host") if old_cache else None

            try:
                devices = discover_devices(timeout=5)
                if devices:
                    d = devices[0]
                    new_ip = d.host[0]
                    ip_changed = old_ip and new_ip != old_ip
                    ui_add_line(f"│ ✅ {d.model} ({d.name})", "#27AE60")
                    ui_add_line(f"│    IP: {new_ip}:{d.host[1]}", "#AAA")
                    mac_hex = d.mac.hex() if isinstance(d.mac, bytes) else str(d.mac)
                    ui_add_line(f"│    MAC: {mac_hex}", "#AAA")
                    if ip_changed:
                        ui_add_line(f"│    ⚠️ IP 已变更: {old_ip} → {new_ip}", "#E67E22")
                    try:
                        d.auth()
                        ui_add_line("│    认证: ✅ 通过", "#27AE60")
                        mac_hex = d.mac.hex() if isinstance(d.mac, bytes) else str(d.mac)
                        add_or_update_device(mac_hex, {
                            "host": new_ip, "port": d.host[1],
                            "mac": mac_hex, "model": d.model, "name": d.model or d.name,
                        })
                        save_config(_cfg.config)
                        if ip_changed:
                            ui_add_line("│    📝 缓存已更新", "#27AE60")
                    except Exception as ae:
                        ui_add_line(f"│    认证: ❌ {ae}", "#E74C3C")
                        device_found = False
                else:
                    def _show_no_device():
                        dev_row = ctk.CTkFrame(result_frame, fg_color="transparent")
                        dev_row.pack(fill="x", pady=1)
                        ctk.CTkLabel(dev_row, text="│ ❌ 未发现设备",
                                     font=ctk.CTkFont(size=12), text_color="#E74C3C").pack(side="left")
                        ctk.CTkButton(dev_row, text="🔍 排查指南", width=80, height=22,
                                      font=ctk.CTkFont(size=10), fg_color="#E67E22",
                                      command=self._device_guide).pack(side="right", padx=(10, 0))
                    dlg.after(0, _show_no_device)
                    device_found = False
            except Exception as de:
                ui_add_line(f"│ ❌ 扫描异常: {de}", "#E74C3C")
                device_found = False
            if not device_found:
                all_ok = False
            ui_add_line("└──────────────────────", "#888")

            def _ping_host(host):
                """ping 一次主机，返回 (success, response_time_ms 或 error_msg)"""
                import subprocess
                param = "-n" if platform.system() == "Windows" else "-c"
                try:
                    r = subprocess.run(["ping", param, "1", host],
                                       capture_output=True, text=True, timeout=5)
                    if r.returncode == 0:
                        for line in r.stdout.split("\n"):
                            if "time=" in line or "时间=" in line:
                                return True, line.strip()
                        return True, "OK"
                    return False, "超时"
                except Exception:
                    return False, "异常"

            def _run_network_diag():
                """三层递进网络诊断，哪层断就停。返回是否网络正常"""
                ui_add_line("│")
                ui_add_line("│   ┌─ 网络诊断 ───────────", "#888")
                net_ok = True

                # 第一层：检测本机是否接入网络
                ips = _get_local_ips()
                if not ips:
                    ui_add_line("│   │ ❌ 电脑未接入互联网", "#E74C3C")
                    ui_add_line("│   │    → 请检查网线/WiFi 是否已连接", "#E67E22")
                    net_ok = False
                else:
                    gateway = ".".join(ips[0].split(".")[:3] + ["1"])
                    ui_add_line(f"│   │ 📶 本机 IP: {ips[0]}", "#AAA")

                    # 第二层：测路由器连通性
                    ok, msg = _ping_host(gateway)
                    if ok:
                        ui_add_line(f"│   │ ✅ 网关 {gateway} 可达", "#27AE60")
                    else:
                        ui_add_line(f"│   │ ❌ 网关 {gateway} 不可达", "#E74C3C")
                        ui_add_line("│   │    → 请检查路由器是否正常", "#E67E22")
                        net_ok = False

                    if net_ok:
                        # 第三层：测外网连通性
                        ok, msg = _ping_host("8.8.8.8")
                        if ok:
                            ui_add_line("│   │ ✅ 外网可达 (8.8.8.8)", "#27AE60")
                        else:
                            ui_add_line("│   │ ❌ 外网不可达", "#E74C3C")
                            ui_add_line("│   │    → 请检查网络连接或DNS设置", "#E67E22")
                            net_ok = False

                ui_add_line("│   └──────────────────────", "#888")
                return net_ok

            # 执行网络诊断
            if not _run_network_diag():
                all_ok = False

            # 总结
            ui_add_line("")
            if all_ok:
                ui_add_line("🎉 诊断完成：一切正常！", "#27AE60")
            else:
                ui_add_line("⚠️ 诊断完成：发现问题，请按提示修复", "#E67E22")

            dlg.after(0, lambda: diag_btn.configure(text="🔍 重新诊断", state="normal"))

        diag_btn = ctk.CTkButton(dlg, text="🔍 开始诊断", command=run_diagnosis)
        diag_btn.pack(pady=(10, 15))
        
        # 自动开始诊断
        dlg.after(100, run_diagnosis)
    
    def _center_on_parent(self, child, width, height):
        """将子窗口居中到父窗口"""
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2
        
        child.geometry(f"{width}x{height}+{x}+{y}")
    
    def _device_guide(self):
        """显示设备排查指南"""
        guide_text = """博联设备排查指南：

1. 确认设备已通电并连接到同一局域网
2. 检查设备指示灯是否正常
3. 尝试重启设备和路由器
4. 确认防火墙未阻止UDP端口80
5. 使用博联官方APP测试设备连接"""
        messagebox.showinfo("设备排查指南", guide_text)