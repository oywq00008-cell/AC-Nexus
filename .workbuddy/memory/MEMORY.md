# BroadlinkAC — 项目记忆

## 架构
- 入口：`ac_controller_pyside6.py` → `broadlinkac_desktop.app_pyside6:main()`
- 核心：`broadlinkac_core/`（零 GUI）— init/send_ac/weather/typhoon/scheduler/logger
- 桌面：`broadlinkac_desktop/`（PySide6 Fusion）— app_pyside6 + pyside/*
- 协议：`hvac_ir/`（14 品牌）+ `protocols/`（3 自研）→ 统一产出 duration 数组

## 设备后端
- 当前：Broadlink RM（python-broadlink，UDP 局域网发现 + 发码）
- 计划：+ 米家空调伴侣（python-miio，ChuangmiIr.play_raw()）
- 计划：+ ESP32 ESPHome（HTTP API，transmit_raw）
- **关键洞察**：所有接入米家 APP 的红外遥控器都能通过 Token 提取 + python-miio 控制，不止小米官方硬件
- IR 协议栈可复用：hvac_ir → duration[] → 各后端分别发送

## 米家集成方案（待实施）
- 扫码登录：QrCodeXiaomiCloudConnector → GUI 弹窗/终端 ASCII QR
- Token 存储：keyring → 系统钥匙串（不落 config.json）
- 代码位置：`tests/xiaomi_backend/`（token_manager.py + ir_sender.py + integration_guide.md）
- 集成改动：config.py(2字段) + ac_control.py(路由) + dialogs.py(扫码UI) + SKILL.md
- 等待硬件到货后实施

## 功率监测计划（待实施）
- **双线并行**：博联→日志推断，米家→功率读取，不替代
- 米家空调伴侣可读取实时功率（ChuangmiPlug.status().power）
- 判定：>50W 运行中 / <10W 已关机
- 统一入口：`get_ac_state(dev_type)` 按类型路由
- 代码位置：`tests/xiaomi_backend/power_monitor.py`（待创建）
- 等待硬件到货后实施

## 定时任务
- `init()` 自动调用 `start_scheduler()` → 守护线程
- 从 config.json 读模板注册 schedule 任务
- 首次扫描前设备离线会跳过
- 启动后无需任何操作即可自动执行定时

## 发布渠道
- GitHub Actions：tag v* → 三平台自动打包
- LobeHub Skills：`npx skills add oywq00008-cell/BroadlinkAC-For-Agent`
- Homebrew Tap：`brew install --cask oywq00008-cell/broadlinkac/broadlinkac`

## Windows 打包要点
- ICO：5 尺寸（16/24/32/48/256）透明底
- 版本信息：`version_info.txt` + spec 引用
- setWindowIcon + 托盘 ICO

## 命名与 SEO（计划）
- 候选新名：**AC Nexus**（寓意多设备连接中枢）
- 策略：保留 GitHub 仓库名 BroadlinkAC（现有搜索量），内部逐步升级品牌
- README 搜索引擎优化：关键词命中（博联/米家/空调遥控器/红外/AI Agent/17品牌）
- 加米家后 README 加「支持博联 RM、米家空调伴侣、ESP32 ESPHome」
- 窗口标题：`AC Nexus — 博联/米家/ESP32 空调控制器`
- 先加功能再统一更名，避免丢失现有用户

## ⚠️ 教训：主题切换 mode_map 方向（2026-06-16）
- `dialogs.py` 中 `mode_map` 必须是 **English → Chinese**：`{"system": "跟随系统", "light": "浅色", "dark": "深色"}`
- 不能反过来写成 `{"跟随系统": "system", ...}`，否则 `mode_map.get("dark")` 返回 `None`
- 导致 `theme_cb.setCurrentText()` 永远回退到"跟随系统"，保存的深色模式丢失
- `on_theme_change` 中通过 `{v: k for k, v in mode_map.items()}.get(t, "system")` 反查，将中文转回英文
- 对比原始代码时发现：旧版无信号阻断（`addItems` 时 handler 未连接，安全），新版需 `QSignalBlocker` 配合
- **始终对照备份代码验证变量命名和映射方向，不要凭记忆改写**
