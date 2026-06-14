"""终端测试：扫码获取米家设备 Token 并存钥匙串

用法: python test_qr_terminal.py
依赖: pip install -r requirements.txt
需要: 桌面上的 xiaomi_token_extractor 文件夹（token_extractor.py）
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../Desktop/xiaomi_token_extractor"))

from token_manager import qr_login_terminal, list_stored_devices

print("=" * 50)
print("  小米设备扫码测试")
print("=" * 50)

result = qr_login_terminal()

if result:
    print("\n已保存到系统钥匙串的设备:")
    for did, info in result.items():
        print(f"  📱 {info['name']}")
        print(f"     ID: {did}")
        print(f"     IP: {info['ip'] or 'N/A'}")
        print(f"     Token: {info['token'][:16]}...")
        print()

    print("\n验证读取:")
    devices = list_stored_devices()
    for d in devices:
        print(f"  {d['name']}: {'✅ 已存储' if d['has_token'] else '❌ 未存储'}")
else:
    print("没有获取到设备。")
