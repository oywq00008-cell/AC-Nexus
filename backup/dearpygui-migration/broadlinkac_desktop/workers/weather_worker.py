"""天气数据获取工作模块"""

import threading
import time

from broadlinkac_core.weather import fetch_weather, fetch_weather_alerts


class WeatherWorker:
    """天气数据获取工作器"""
    
    def __init__(self, callback=None):
        self.callback = callback
        self.running = False
        self.thread = None
        self.interval = 300  # 5分钟刷新一次
        
    def start(self):
        """启动天气数据获取"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """停止天气数据获取"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
    
    def _worker_loop(self):
        """工作循环"""
        while self.running:
            try:
                # 获取天气数据
                weather = fetch_weather()
                alerts = fetch_weather_alerts()
                
                # 调用回调函数
                if self.callback:
                    self.callback(weather, alerts)
                
            except Exception as e:
                print(f"天气数据获取失败: {e}")
            
            # 等待下次刷新
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def fetch_now(self):
        """立即获取天气数据"""
        try:
            weather = fetch_weather()
            alerts = fetch_weather_alerts()
            
            if self.callback:
                self.callback(weather, alerts)
            
            return weather, alerts
            
        except Exception as e:
            print(f"天气数据获取失败: {e}")
            return None, None