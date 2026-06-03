#!/usr/bin/env python3
"""BroadlinkAC — 博联空调智能控制器 (macOS 桌面应用)

启动 GUI:
    python3 ac_controller.py

Agent 调用:
    from broadlinkac_core import init, send_ac
    init(api_key="xxx", qw_host="https://xxx.re.qweatherapi.com")
    send_ac("on", "cool", 26, "auto")
"""

from broadlinkac_core import init
from broadlinkac_desktop.app import App

if __name__ == "__main__":
    init()
    app = App()
    app.mainloop()
