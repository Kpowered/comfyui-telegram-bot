# ComfyUI Telegram Bot 部署包

一个轻量级的 Telegram Bot，通过 REST API 对接 ComfyUI，实现文生图、文生视频、图生视频等功能。

## 特点

- **轻量**: 仅 90KB 代码，不包含 ComfyUI 本体和模型
- **即插即用**: 自动识别现有 ComfyUI 环境，无需重复安装
- **独立运行**: Bot 独立进程，不依赖 OpenClaw 或其他 AI 框架
- **自动重启**: 检测 ComfyUI 状态，崩溃时自动重启
- **开机自启**: 支持 Windows 启动文件夹，开机自动运行

## 系统架构

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

## 前置条件

1. **ComfyUI**: 已安装并能正常运行（任何版本）
2. **Telegram Bot**: 从 [@BotFather](https://t.me/BotFather) 创建 Bot 并获取 Token
3. **Python**: 使用 ComfyUI 自带的 embedded Python，无需额外安装

## 快速开始

### 1. 解压部署包

```bash
# 解压到任意目录
unzip comfyui_bot_deployment.zip -d comfyui_bot
cd comfyui_bot
```

### 2. 运行自动配置

```bash
python install.py
```

按提示输入：
- ComfyUI 安装路径（如 `D:\ComfyUI\ComfyUI_windows_portable`）
- Telegram Bot Token（从 @BotFather 获取）
- Workspace 路径（默认当前目录）

脚本会自动：
- 生成 `.env` 配置文件
- 更新所有 Python 文件中的路径
- 创建启动脚本 `start_bot.bat`

### 3. 启动 Bot

**方式 1: 批处理脚本**
```bash
start_bot.bat
```

**方式 2: 直接运行**
```bash
python comfy_bot.py
```

### 4. 测试

在 Telegram 中向 Bot 发送：
```
/img a cute cat
```

如果返回图片，说明部署成功。

## 支持的指令

| 指令 | 功能 | 示例 |
|------|------|------|
| `/img <prompt>` | 文生图 (RedCraft DX3) | `/img a girl in garden --size 832x1216` |
| `/md <prompt>` | 文生图 (Moody 双模型，原生中文) | `/md 一个女孩在花园里` |
| `/t2v <prompt>` | 文生视频 (Wan2.2 AIO) | `/t2v a cat running --length 81` |
| `/i2v <prompt>` | 图生视频 (需先发图片) | `/i2v camera zoom in --steps 20` |
| `/id <prompt> --target <path>` | FaceID 换脸 (需先发人脸图) | `/id a superhero --target scene.jpg` |
| `/pm <prompt>` | AI 扩写 prompt (需 Ollama) | `/pm beach sunset` |

### 可选参数

- `--size WxH`: 图片/视频尺寸（如 `1024x1024`, `832x480`）
- `--steps N`: 采样步数（默认因管线而异）
- `--length N`: 视频帧数（默认 81）
- `--target <path>`: 目标图片路径（FaceID 用）

## 开机自启

### Windows

1. 按 `Win+R`，输入 `shell:startup`，回车
2. 将 `start_bot.bat` 复制到打开的文件夹
3. 重启电脑测试

### Linux/Mac

编辑 crontab：
```bash
crontab -e
```

添加：
```
@reboot cd /path/to/comfyui_bot && python comfy_bot.py
```

## 文件说明

### 核心模块

- **comfyui_api.py**: ComfyUI REST API 底层封装
  - 提交 workflow JSON
  - 轮询任务状态
  - 下载生成结果
  
- **comfy_runner.py**: 管线执行器
  - `txt2img()`: 文生图
  - `txt2video()`: 文生视频
  - `img2video()`: 图生视频
  - `klein_faceid()`: FaceID 换脸
  - `moody_txt2img()`: Moody 双模型文生图

- **cmd_handler.py**: 指令解析器
  - 解析 Telegram 消息
  - 提取参数（size/steps/length）
  - 调用对应管线

- **comfy_bot.py**: Telegram Bot 主程序
  - 长轮询接收消息
  - 多线程处理请求
  - 自动重启 ComfyUI
  - PID 锁防止重复启动

- **ffmpeg_utils.py**: 视频处理工具
  - 视频拼接
  - 压缩（超过 15MB 时）

### 配置文件

- **.env.template**: 环境变量模板
- **COMMANDS.md**: 指令详细文档
- **FILES.md**: 文件清单

### 脚本

- **install.py**: 自动配置向导
- **check.py**: 部署包完整性检查
- **comfy_bot.bat**: Windows 启动脚本

## 故障排查

### Bot 无法启动

**症状**: 运行 `python comfy_bot.py` 后立即退出

**原因**: 可能已有实例在运行

**解决**:
```bash
# 删除 PID 锁文件
del comfy_bot.pid
# 重新启动
python comfy_bot.py
```

### ComfyUI 连接失败

**症状**: Bot 日志显示 `ComfyUI not responding`

**检查**:
1. ComfyUI 是否已启动？访问 http://127.0.0.1:8188
2. 端口是否被占用？检查防火墙设置
3. 路径配置是否正确？查看 `.env` 文件

**解决**: Bot 会自动尝试重启 ComfyUI，等待 30 秒后重试

### 图片/视频生成失败

**症状**: Bot 返回 `Generation failed`

**原因**:
- 模型文件缺失或损坏
- Workflow JSON 与 ComfyUI 版本不兼容
- 显存不足

**解决**:
1. 查看 ComfyUI 控制台错误信息
2. 检查模型文件是否完整（在 `ComfyUI/models/` 目录）
3. 降低分辨率或步数（如 `--size 512x512 --steps 10`）

### 视频文件过大无法发送

**症状**: Telegram 提示文件过大

**原因**: Telegram 限制单文件 50MB（Bot API 限制 20MB）

**解决**: Bot 会自动压缩超过 15MB 的视频，如果仍然过大：
- 减少视频长度（`--length 41`）
- 降低分辨率（`--size 576x1024`）

## 高级配置

### 修改默认参数

编辑 `comfy_runner.py`，修改函数默认值：

```python
def txt2img(prompt, width=1024, height=1024, steps=5):
    # 改为 steps=10 提升质量
```

### 添加新管线

1. 在 ComfyUI 中设计 workflow，导出 API JSON
2. 在 `comfyui_api.py` 中添加 `build_xxx_prompt()` 函数
3. 在 `comfy_runner.py` 中添加 `xxx()` 管线函数
4. 在 `cmd_handler.py` 中注册新指令

### 更换模型

编辑 `comfyui_api.py` 中的模型文件名：

```python
"unet_name": "your_model_name.safetensors"
```

### 使用 Ollama 扩写 prompt

安装 Ollama 并启动：
```bash
ollama serve
```

在 Bot 中使用 `/pm` 指令：
```
/pm beach sunset
```

Bot 会调用 Ollama 将简短描述扩写为详细 prompt。

## 迁移到新环境

### 导出配置

```bash
# 打包整个目录
zip -r comfyui_bot_backup.zip comfyui_bot/
```

### 导入到新机器

1. 在新机器上安装 ComfyUI
2. 解压备份包
3. 运行 `python install.py` 重新配置路径
4. 启动 Bot

## 安全建议

- **不要**将 Telegram Token 提交到公开仓库
- 使用 `.env` 文件管理敏感信息（已在 `.gitignore` 中）
- 定期备份 `comfy_bot.log` 日志
- 限制 Bot 访问权限（在 @BotFather 中设置）

## 性能优化

### 减少 API 调用

Bot 使用长轮询（timeout=10s），减少无效请求。

### 多线程处理

每个用户请求在独立线程中处理，不会阻塞其他用户。

### 自动清理

Bot 会自动清理 `seen` 集合（超过 500 条消息时），防止内存泄漏。

## 日志

Bot 日志保存在 `comfy_bot.log`，包含：
- 启动/停止时间
- 接收到的指令
- ComfyUI 状态检查
- 错误信息

查看实时日志：
```bash
tail -f comfy_bot.log
```

## 更新

### 更新 Bot 代码

```bash
# 备份旧版本
cp comfy_bot.py comfy_bot.py.bak

# 替换新文件
# 重启 Bot
```

### 更新 ComfyUI

ComfyUI 更新后，可能需要更新 workflow JSON：
1. 在 ComfyUI 中重新导出 API JSON
2. 更新 `comfyui_api.py` 中的 `build_xxx_prompt()` 函数

## 常见问题

**Q: 支持哪些 ComfyUI 版本？**  
A: 理论上支持所有版本，但 workflow JSON 可能需要适配。

**Q: 可以同时运行多个 Bot 吗？**  
A: 可以，但需要使用不同的 Token 和 workspace 目录。

**Q: 支持 Discord/WhatsApp 吗？**  
A: 当前仅支持 Telegram，但可以修改 `comfy_bot.py` 适配其他平台。

**Q: 生成速度慢怎么办？**  
A: 减少步数（`--steps 5`）或使用更快的模型（如 Turbo 系列）。

**Q: 可以在服务器上运行吗？**  
A: 可以，使用 `nohup` 或 `screen` 保持后台运行：
```bash
nohup python comfy_bot.py > bot.log 2>&1 &
```

## 技术栈

- **Python 3.x**: 核心语言
- **urllib**: HTTP 请求（无第三方依赖）
- **threading**: 多线程处理
- **ComfyUI**: 图像/视频生成后端
- **Telegram Bot API**: 消息接收与发送
- **FFmpeg**: 视频处理（ComfyUI 自带）

## 许可

本项目为个人使用工具，代码可自由修改和分发。

## 致谢

- ComfyUI 社区提供的强大工具
- Telegram Bot API 的简洁设计
- 各模型作者的开源贡献

## 联系

如有问题或建议，欢迎反馈。

---

**最后更新**: 2026-03-06  
**版本**: 1.0.0
