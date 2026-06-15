"""设备扫描和管理工作模块"""

import threading
import time

from broadlinkac_core.ac_control import discover_devices
from broadlinkac_core.config import add_or_update_device, save_config
import broadlinkac_core.config as _cfg


class DeviceWorker:
    """设备扫描和管理工作器"""
    
    def __init__(self, callback=None):
        self.callback = callback
        self.running = False
        self.thread = None
        self.interval = 60  # 1分钟扫描一次
        
    def start(self):
        """启动设备扫描"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """停止设备扫描"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
    
    def _worker_loop(self):
        """工作循环"""
        while self.running:
            try:
                # 扫描设备
                devices = discover_devices(timeout=5)
                
                # 更新设备信息
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
                
                # 调用回调函数
                if self.callback:
                    self.callback(devices)
                
            except Exception as e:
                print(f"设备扫描失败: {e}")
            
            # 等待下次扫描
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def scan_now(self):
        """立即扫描设备"""
        try:
            devices = discover_devices(timeout=5)
            
            # 更新设备信息
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
            
            if self.callback:
                self.callback(devices)
            
            return devices
            
        except Exception as e:
            print(f"设备扫描失败: {e}")
            return None