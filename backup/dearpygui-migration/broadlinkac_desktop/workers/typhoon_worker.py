"""台风数据获取工作模块"""

import threading
import time

from broadlinkac_core.typhoon import fetch_typhoons, fetch_typhoon_detail, typhoon_threat_distance


class TyphoonWorker:
    """台风数据获取工作器"""
    
    def __init__(self, callback=None, alert_callback=None):
        self.callback = callback
        self.alert_callback = alert_callback
        self.running = False
        self.thread = None
        self.interval = 1800  # 30分钟刷新一次
        self.provider = "nmc"  # nmc 或 nhc
        
    def start(self):
        """启动台风数据获取"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """停止台风数据获取"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
    
    def set_provider(self, provider):
        """设置数据源"""
        self.provider = provider
    
    def _worker_loop(self):
        """工作循环"""
        while self.running:
            try:
                # 获取台风数据
                typhoons = fetch_typhoons(self.provider)
                
                # 调用回调函数
                if self.callback:
                    self.callback(typhoons)
                
                # 检查台风威胁
                if self.alert_callback:
                    self._check_threat(typhoons)
                
            except Exception as e:
                print(f"台风数据获取失败: {e}")
            
            # 等待下次刷新
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def _check_threat(self, typhoons):
        """检查台风威胁"""
        try:
            # 检查是否有台风距离小于100公里
            for typhoon in typhoons:
                if 'lat' in typhoon and 'lon' in typhoon:
                    dist, name = typhoon_threat_distance()
                    if dist < 100:
                        # 发送预警
                        if self.alert_callback:
                            self.alert_callback(typhoon, dist)
                        break
                        
        except Exception as e:
            print(f"台风威胁检查失败: {e}")
    
    def fetch_now(self):
        """立即获取台风数据"""
        try:
            typhoons = fetch_typhoons(self.provider)
            
            if self.callback:
                self.callback(typhoons)
            
            return typhoons
            
        except Exception as e:
            print(f"台风数据获取失败: {e}")
            return None