# STATUS.md - 项目状态

## 项目概述

ComfyUI Telegram Bot - 轻量级 Telegram Bot，通过 REST API 对接 ComfyUI，实现文生图、文生视频、图生视频、FaceID 换脸等功能。

## 当前状态

**版本**: v1.0  
**最后更新**: 2026-03-06  
**GitHub**: https://github.com/Kpowered/comfyui-telegram-bot

## 已完成功能

### 核心功能
- ✅ ComfyUI REST API 封装 (comfyui_api.py)
- ✅ Telegram Bot 长轮询接收消息 (comfy_bot.py)
- ✅ 指令解析与分发 (cmd_handler.py)
- ✅ 管线执行器 (comfy_runner.py)
- ✅ 视频处理工具 (ffmpeg_utils.py)

### 支持的管线
- ✅ 文生图 - RedCraft DX3 (`/img`)
- ✅ 文生图 - Moody ZIB+ZIT 双模型 (`/md`)
- ✅ 文生视频 - Wan2.2 AIO T2V (`/t2v`)
- ✅ 图生视频 - Wan2.2 AIO I2V (`/i2v`)
- ✅ FaceID 换脸 - Klein9b (`/id`)
- ✅ Prompt 扩写 - Ollama (`/pm`)

### 自动化功能
- ✅ ComfyUI 状态检测与自动重启
- ✅ 视频文件自动压缩（超过 15MB）
- ✅ PID 锁防止重复启动
- ✅ 多线程处理用户请求
- ✅ 自动配置脚本 (install.py)

### 部署支持
- ✅ Windows 开机自启（Startup 文件夹）
- ✅ 环境变量配置模板 (.env.example / .env.template)
- ✅ Git 配置 (.gitignore)
- ✅ 完整文档 (README.md / COMMANDS.md / MODELS.md / FILES.md)
- ✅ Workflow JSON 文件（4 个管线）

## 技术架构

```
用户 (Telegram)
    ↓
comfy_bot.py (轮询 + 指令解析)
    ↓
cmd_handler.py (指令分发)
    ↓
comfy_runner.py (管线执行)
    ↓
comfyui_api.py (REST API 封装)
    ↓
ComfyUI (http://127.0.0.1:8188)
```

## 文件结构

```
comfyui-telegram-bot/
├── comfyui_api.py          # ComfyUI REST API 底层封装
├── comfy_runner.py         # 管线执行器
├── cmd_handler.py          # 指令解析器
├── comfy_bot.py            # Telegram Bot 主程序
├── ffmpeg_utils.py         # 视频处理工具
├── install.py              # 自动配置脚本
├── check.py                # 部署包完整性检查
├── comfy_bot.bat           # Windows 启动脚本
├── .env.example            # 环境变量示例（详细版）
├── .env.template           # 环境变量模板（简洁版）
├── .gitignore              # Git 忽略规则
├── README.md               # 完整文档
├── COMMANDS.md             # 指令文档
├── MODELS.md               # 模型清单
├── FILES.md                # 文件清单
├── STATUS.md               # 项目状态（本文件）
├── AGENTS.md               # 协作规则
└── workflows/              # Workflow JSON 文件
    ├── README.md
    ├── moody_zib_zit.json
    ├── wan2.2_t2v.json
    ├── wan2.2_i2v.json
    └── klein9b_faceid.json
```

## 已知限制

1. **平台支持**: 当前仅支持 Telegram，不支持 Discord/WhatsApp
2. **模型依赖**: 需要用户自行下载模型文件（约 70GB）
3. **视频大小**: Telegram 限制单文件 50MB（Bot API 限制 20MB）
4. **并发处理**: 多线程处理，但 ComfyUI 本身可能有队列限制
5. **错误恢复**: ComfyUI 崩溃时会自动重启，但可能丢失当前任务

## 待办事项

### 短期（可选）
- [ ] 添加更多管线（如 ControlNet、Inpainting）
- [ ] 支持批量生成
- [ ] 添加生成历史记录
- [ ] 优化视频压缩策略

### 长期（可选）
- [ ] 支持 Discord/WhatsApp
- [ ] Web UI 管理界面
- [ ] 多用户权限管理
- [ ] 云端部署方案

## 部署环境

### 开发环境
- **机器**: BJ-5800x3D
- **系统**: Windows 10/11
- **GPU**: RTX 3090 24GB
- **内存**: 64GB RAM
- **ComfyUI**: D:\ComfyUI\ComfyUI_windows_portable\
- **Workspace**: C:\Users\admin\.openclaw\workspace\

### 生产环境
- **Bot Token**: 8799567575:AAF5ocEo0sg22SAiwXJgQ96TbhCEMlilUvY
- **Bot 用户名**: @NSFW_IMGBOT
- **ComfyUI API**: http://127.0.0.1:8188
- **Ollama API**: http://127.0.0.1:11434

## 迁移到新环境

### 快速部署
```bash
# 1. 克隆仓库
git clone https://github.com/Kpowered/comfyui-telegram-bot.git
cd comfyui-telegram-bot

# 2. 运行自动配置
python install.py

# 3. 启动 Bot
python comfy_bot.py
```

### 前置条件
- ComfyUI 已安装并能正常运行
- Telegram Bot Token（从 @BotFather 获取）
- Python（使用 ComfyUI 自带的 embedded Python）

### 配置说明
`install.py` 会自动：
1. 检测 ComfyUI 安装路径
2. 提示输入 Telegram Bot Token
3. 生成 `.env` 配置文件
4. 更新所有 Python 文件中的硬编码路径
5. 创建启动脚本 `start_bot.bat`

## 最近更新

### 2026-03-06
- 创建 GitHub 仓库并推送所有文件
- 添加 MODELS.md 模型清单
- 重命名 workflow 文件为英文（避免编码问题）
- 完善 install.py 文档说明
- 修正 .env.template 编码问题
- 创建 STATUS.md 和 AGENTS.md

## 联系方式

- **GitHub Issues**: https://github.com/Kpowered/comfyui-telegram-bot/issues
- **开发者**: K (@KPowered)

---

**最后更新**: 2026-03-06 23:05 GMT+8
