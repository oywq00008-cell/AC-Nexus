# 小米 Token 提取测试

下载的工具: `token_extractor.exe` (18.7 MB)
来源: https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor

## 使用方法

在终端中双击运行 `token_extractor.exe`，或者在当前目录打开命令行运行：

```powershell
.\token_extractor.exe
```

## 运行后流程

1. 选择登录方式：输入 `1`（用户名+密码）或 `2`（二维码）
2. 选择服务器区域：输入 `cn`（中国）
3. 登录小米账号
4. 工具会列出你账号下所有设备，包括：
   - 设备名称
   - IP 地址
   - Token（32位十六进制字符串）
   - MAC 地址

## 输出示例

```
Device: 米家空调伴侣2        IP: 192.168.1.100
Token: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6
MAC:    AA:BB:CC:DD:EE:FF

Device: 米家智能插座        IP: 192.168.1.101
Token: f6e5d4c3b2a10987...
```

## 注意事项

- 需要小米账号（不是小米社区或米家 APP 内的小米 ID）
- 服务器选 `cn`（中国大陆）
- 如果有二步验证，注意查看邮箱验证码
- 每天调用次数有限（3-5 次）
