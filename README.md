# 🎮 BroadlinkAC

[English](README_EN.md) | 中文

博联空调智能控制器 — macOS 桌面应用 + **AI Agent 可编程调用**。

> 💡 一个 App 管完空调所有事：**每天定时自动开关**、**根据室外温度智能调整制冷/制热**、**台风预警**、**Agent 远程控制**。接入 Broadlink RM 系列红外遥控器即可。

```python
from ac_controller import init, send_ac

# 初始化（可一次传入所有配置，自动持久化到 config.json）
init(
    api_key="你的和风API Key",
    qw_host="https://xxx.re.qweatherapi.com",
    location={"lat": 22.54, "lon": 114.05, "name": "深圳"},
    brand="格力",
)

send_ac("on", "cool", 26, "auto")  # 开空调，制冷 26°C，自动风
send_ac("off", "cool", 26, "auto") # 关空调
```

## ✨ 核心功能

- 🎯 **多品牌支持** — 格力 / 美的 / 小米 / 海尔 / 奥克斯 / 海信 / 大金 / 三菱 / 松下，覆盖主流空调
- ⏰ **定时开关机** — 每天按设定时间自动开机 / 关机，无需手动操作
- 🌡️ **温度规则** — 根据室外温度自动调整：例如室外 36°C 以上 → 制冷 24°C，室外 25-29°C → 制冷 27°C，室外 18-24°C → 不启动，室外 17°C 以下 → 制热 28°C。规则完全可编辑
- 🌤️ **实时天气** — 和风天气 API，温度 / 湿度 / 体感 / 风向，定时自动刷新
- 🌀 **台风监测** — 中央气象台数据，实时路径追踪，距离预警提醒
- 📋 **操作日志** — 每日自动记录开关机、温度调整、台风动态，可回溯查看
- 🔧 **故障诊断** — 内置一键检测，自动安装缺失依赖
- 🤖 **Agent 可调用** — `import` 零副作用，`init()` 即用，OpenAI / Claude / Hermes 等任意 Agent 均适配

### 🕐 定时规则示例

| 室外温度 | 动作 | 目标温度 |
|----------|------|----------|
| ≥ 36°C | 制冷 | 24°C |
| 33-35°C | 制冷 | 25°C |
| 30-32°C | 制冷 | 26°C |
| 25-29°C | 制冷 | 27°C |
| 18-24°C | 不启动 | — |
| ≤ 17°C | 制热 | 28°C |

每天到达设定的开机时间，App 自动检测室外温度，按规则决定是否开空调、开到几度。另外支持独立的定时关机（如每晚 22:00 自动关）。

## 🧰 硬件要求

- 一台 Mac（Apple Silicon / Intel）
- [Broadlink RM 系列](https://www.broadlink.com.cn/) 红外遥控器（RM Mini / RM Pro / RM4 Mini 等）
- 空调（支持品牌见上）

## 🚀 快速开始

### 方式一：下载 .app（推荐）

从 [Releases](https://github.com/oywq00008-cell/BroadlinkAC/releases) 下载 `BroadlinkAC.app`，拖到应用程序文件夹，双击运行。

首次启动如提示"无法验证开发者"：
```bash
xattr -cr /Applications/BroadlinkAC.app
```

### 方式二：从源码运行

```bash
git clone https://github.com/oywq00008-cell/BroadlinkAC.git
cd BroadlinkAC
pip install -r requirements.txt
python3 ac_controller.py
```

### 方式三：Agent 全自动调用

```bash
git clone https://github.com/oywq00008-cell/BroadlinkAC.git
cd BroadlinkAC
pip install -r requirements.txt
```

然后 Agent 即可 `import ac_controller` 控制空调。适合与 **OpenAI Codex CLI / Claude Code / Hermes Agent / OpenCalw** 等搭配使用。

```python
from ac_controller import init, send_ac

init(api_key="你的Key", qw_host="https://你的Host")  # 一次传入所有配置，自动保存
send_ac("on", "cool", 26, "auto")                 # 直接控制
```

无需手动编辑文件，所有配置通过 `init()` 参数一次性传入即可持久化。

## ⚙️ 配置

首次运行后在菜单栏 **设置** 中填入：

| 项目 | 说明 |
|------|------|
| 和风 API Key | [和风天气控制台](https://console.qweather.com) 免费申请 |
| 个人 Host | 免费订阅的 API Host 地址 |
| 空调品牌 | 选择你家空调品牌 |

博联设备会自动扫描局域网发现，无需手动配 IP。

## 📁 项目结构

```
ac_controller.py          # 主程序（customtkinter GUI + 可编程 API）
protocols/
├── haier.py              # 海尔协议（从 IRremoteESP8266 C++ 移植）
├── aux.py                # 奥克斯协议
└── panasonic.py          # 松下协议
requirements.txt          # Python 依赖
```

## 🔐 隐私

所有配置（API Key、城市、时间规则）保存在本地 `~/.ac_controller/`，不上传任何服务器。天气和台风数据直接从官方 API 获取。

## 📜 协议

MIT License
