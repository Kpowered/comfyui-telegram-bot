@echo off
REM ComfyUI + Bot 启动脚本

cd /d "%~dp0"

REM 启动 ComfyUI (后台)
echo Starting ComfyUI...
start "" "D:\ComfyUI\ComfyUI_windows_portable\run_nvidia_gpu.bat"

REM 等待 ComfyUI 启动
timeout /t 15 /nobreak

REM 启动 Bot
echo Starting Telegram Bot...
"D:\ComfyUI\ComfyUI_windows_portable\python_embeded\python.exe" comfy_bot.py

pause
