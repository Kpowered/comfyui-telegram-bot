"""
部署脚本 - 自动配置路径
运行: python install.py
"""
import os
import sys
import shutil
from pathlib import Path

def find_comfyui():
    """尝试自动查找 ComfyUI 安装路径"""
    common_paths = [
        r"D:\ComfyUI\ComfyUI_windows_portable",
        r"C:\ComfyUI\ComfyUI_windows_portable",
        Path.home() / "ComfyUI",
    ]
    for p in common_paths:
        if Path(p).exists():
            return str(p)
    return None

def main():
    print("=== ComfyUI + Bot 部署向导 ===\n")
    
    # 1. 检测 ComfyUI
    comfyui_path = find_comfyui()
    if comfyui_path:
        print(f"✓ 检测到 ComfyUI: {comfyui_path}")
        use_detected = input("使用此路径? (Y/n): ").strip().lower()
        if use_detected == 'n':
            comfyui_path = input("请输入 ComfyUI 路径: ").strip()
    else:
        comfyui_path = input("请输入 ComfyUI 路径: ").strip()
    
    if not Path(comfyui_path).exists():
        print(f"✗ 路径不存在: {comfyui_path}")
        sys.exit(1)
    
    # 2. 获取 Telegram Token
    token = input("\n请输入 Telegram Bot Token: ").strip()
    if not token:
        print("✗ Token 不能为空")
        sys.exit(1)
    
    # 3. 设置 Workspace
    workspace = Path.cwd()
    print(f"\n当前工作目录: {workspace}")
    custom_ws = input("使用此目录作为 workspace? (Y/n): ").strip().lower()
    if custom_ws == 'n':
        workspace = Path(input("请输入 workspace 路径: ").strip())
    
    # 4. 生成配置
    config = {
        'COMFYUI_PATH': comfyui_path,
        'COMFYUI_URL': 'http://127.0.0.1:8188',
        'OUTPUT_DIR': str(Path(comfyui_path) / 'ComfyUI' / 'output'),
        'WORKSPACE': str(workspace),
        'TELEGRAM_TOKEN': token,
        'PYTHON_PATH': str(Path(comfyui_path) / 'python_embeded' / 'python.exe'),
        'FFMPEG_PATH': str(Path(comfyui_path) / 'python_embeded' / 'Lib' / 'site-packages' / 'imageio_ffmpeg' / 'binaries' / 'ffmpeg-win-x86_64-v7.1.exe'),
        'OLLAMA_URL': 'http://127.0.0.1:11434',
    }
    
    # 5. 写入 .env
    env_file = workspace / '.env'
    with open(env_file, 'w', encoding='utf-8') as f:
        for k, v in config.items():
            f.write(f"{k}={v}\n")
    print(f"\n✓ 配置已写入: {env_file}")
    
    # 6. 更新 Python 文件中的硬编码路径
    files_to_update = ['comfy_bot.py', 'comfy_runner.py', 'comfyui_api.py']
    print("\n正在更新文件路径...")
    
    for fname in files_to_update:
        fpath = workspace / fname
        if not fpath.exists():
            print(f"⚠ 文件不存在: {fname}")
            continue
        
        content = fpath.read_text(encoding='utf-8')
        
        # 替换路径
        replacements = {
            r'D:\ComfyUI\ComfyUI_windows_portable': comfyui_path,
            r'C:\Users\admin\.openclaw\workspace': str(workspace),
            '8799567575:AAF5ocEo0sg22SAiwXJgQ96TbhCEMlilUvY': token,
        }
        
        for old, new in replacements.items():
            content = content.replace(old, new)
        
        fpath.write_text(content, encoding='utf-8')
        print(f"  ✓ {fname}")
    
    # 7. 生成启动脚本
    bat_content = f"""@echo off
cd /d "%~dp0"
echo Starting ComfyUI...
start "" "{comfyui_path}\\run_nvidia_gpu.bat"
timeout /t 15 /nobreak
echo Starting Telegram Bot...
"{config['PYTHON_PATH']}" comfy_bot.py
pause
"""
    bat_file = workspace / 'start_bot.bat'
    bat_file.write_text(bat_content, encoding='utf-8')
    print(f"\n✓ 启动脚本: {bat_file}")
    
    # 8. 完成
    print("\n=== 部署完成 ===")
    print(f"\n启动方式:")
    print(f"  1. 双击运行: {bat_file}")
    print(f"  2. 或命令行: python comfy_bot.py")
    print(f"\n开机自启:")
    print(f"  Win+R 输入 shell:startup")
    print(f"  将 {bat_file} 复制到启动文件夹")

if __name__ == '__main__':
    main()
