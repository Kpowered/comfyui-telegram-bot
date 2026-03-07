# ComfyUI Telegram Bot

一个轻量级的 Telegram Bot，用于通过 Telegram 调用 ComfyUI 生成图片和视频。

## 特性

- 🎨 **文生图**：支持 RedCraft DX3 和 Moody ZIB+ZIT 双模型
- 🎬 **文生视频**：支持 Wan 2.2 AIO T2V
- 🖼️ **图生视频**：支持 Wan 2.2 AIO I2V
- 👤 **FaceID 换脸**：支持 Klein9b 模型
- 📱 **Telegram 集成**：直接在 Telegram 中发送命令生成内容

## 快速开始

### 前置要求

- Windows 系统
- ComfyUI 已安装并配置
- Python 3.8+
- Telegram Bot Token（从 [@BotFather](https://t.me/BotFather) 获取）

### 安装

1. 克隆仓库到 workspace 目录：
```bash
git clone https://github.com/Kpowered/comfyui-telegram-bot.git
cd comfyui-telegram-bot
```

2. 配置 Bot Token：
编辑 `comfy_bot.py`，替换 `TOKEN` 为你的 Bot Token：
```python
TOKEN = "YOUR_BOT_TOKEN_HERE"
```

3. 配置 ComfyUI 路径：
编辑 `comfy_bot.py`，设置 ComfyUI 安装路径：
```python
COMFYUI_PATH = r"D:\ComfyUI\ComfyUI_windows_portable"
```

### 运行

#### 手动启动
```bash
python comfy_bot.py
```

#### 开机自启（推荐）
1. 按 `Win+R`，输入 `shell:startup`
2. 创建 `comfy_bot.bat`：
```batch
@echo off
cd /d C:\Users\admin\.openclaw\workspace
start /min python comfy_bot.py
```
3. 将 `.bat` 文件放入启动文件夹

## 使用指南

### 可用命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/img <prompt>` | RedCraft 文生图（英文） | `/img a beautiful sunset` |
| `/md <prompt>` | Moody 文生图（中文，1920x1080） | `/md 一位美丽的女孩` |
| `/t2v <prompt>` | 文生视频 | `/t2v 猫咪在跑步` |
| `/i2v` | 图生视频（需先发送图片） | 发送图片后回复 `/i2v` |
| `/id <prompt>` | FaceID 换脸（需先发送人脸图片） | 发送人脸图后 `/id 一位女战士` |
| `/help` | 查看帮助 | `/help` |

### 工作流程

1. **文生图**：
   - 发送 `/md 你的提示词`
   - Bot 显示"生成中..."
   - 完成后自动发送图片

2. **图生视频**：
   - 先发送一张图片
   - 回复该图片并发送 `/i2v`
   - 等待视频生成

3. **FaceID 换脸**：
   - 先发送一张人脸照片
   - 回复该照片并发送 `/id 场景描述`
   - 生成带有该人脸的新图片

## 技术细节

### 架构

```
Telegram Bot (comfy_bot.py)
    ↓
命令处理器 (cmd_handler.py)
    ↓
工作流执行器 (comfy_runner.py)
    ↓
ComfyUI API (comfyui_api.py)
    ↓
ComfyUI (http://127.0.0.1:8188)
```

### 核心模块

- **comfy_bot.py**：Telegram Bot 主程序，使用 `urllib` 轻量级实现
- **cmd_handler.py**：命令解析和路由
- **comfy_runner.py**：工作流执行器，调用 ComfyUI API
- **comfyui_api.py**：ComfyUI API 封装，包含所有工作流定义

### 工作流配置

所有工作流都在 `comfyui_api.py` 中定义：

- `build_redcraft_prompt()` - RedCraft DX3 文生图
- `build_moody_zib_zit_prompt()` - Moody ZIB+ZIT 双模型文生图
- `build_wan_t2v_prompt()` - Wan 2.2 文生视频
- `build_wan_i2v_prompt()` - Wan 2.2 图生视频
- `build_klein_faceid_prompt()` - Klein9b FaceID 换脸

## 故障排查

### Bot 无响应

1. 检查 Bot 是否运行：
```powershell
Get-Process python | Where-Object {(Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -like "*comfy_bot*"}
```

2. 查看日志：
```powershell
Get-Content C:\Users\admin\.openclaw\workspace\comfy_bot.log -Tail 50
```

### ComfyUI 连接失败

1. 检查 ComfyUI 是否运行：
```powershell
curl http://127.0.0.1:8188/system_stats
```

2. 检查队列状态：
```powershell
curl http://127.0.0.1:8188/queue | ConvertFrom-Json
```

### 显存不足

如果遇到显存不足错误：
- `/md` 命令已优化为直接生成 1920x1080，无需多次 upscale
- 视频生成建议降低分辨率或帧数
- 关闭其他占用显存的程序

更多排查命令见 `memory/lessons.md`。

## 更新日志

### 2026-03-07
- ✅ 修复 `/md` 命令显存不足问题（去掉 UltimateSDUpscale）
- ✅ 修复 `poll_history` 逻辑错误（先检查队列，再检查 history）
- ✅ 添加子进程实时日志输出（`-u` 参数）
- ✅ 修复 `edit_msg` 错误处理（即使编辑失败也继续发送结果）
- ✅ 默认分辨率改为 1920x1080

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 致谢

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - 强大的 Stable Diffusion 工作流引擎
- [Telegram Bot API](https://core.telegram.org/bots/api) - Telegram Bot 开发接口
