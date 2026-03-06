"""
快速测试脚本 - 验证部署包完整性
"""
import os
from pathlib import Path

REQUIRED_FILES = [
    'comfyui_api.py',
    'comfy_runner.py', 
    'cmd_handler.py',
    'comfy_bot.py',
    'ffmpeg_utils.py',
    'install.py',
    'comfy_bot.bat',
    '.env.template',
    'COMMANDS.md',
    'README.md',
]

def check_deployment():
    root = Path(__file__).parent
    print("=== 部署包完整性检查 ===\n")
    
    missing = []
    for f in REQUIRED_FILES:
        path = root / f
        if path.exists():
            size = path.stat().st_size
            print(f"✓ {f:20s} ({size:,} bytes)")
        else:
            print(f"✗ {f:20s} [缺失]")
            missing.append(f)
    
    print(f"\n总计: {len(REQUIRED_FILES)} 个文件")
    
    if missing:
        print(f"\n⚠ 缺失 {len(missing)} 个文件:")
        for f in missing:
            print(f"  - {f}")
        return False
    else:
        print("\n✓ 所有文件完整")
        return True

if __name__ == '__main__':
    ok = check_deployment()
    exit(0 if ok else 1)
