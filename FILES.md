# 部署包文件清单

## 核心文件 (7个)
- comfyui_api.py - ComfyUI REST API封装
- comfy_runner.py - 管线执行器
- cmd_handler.py - 指令解析器
- comfy_bot.py - Telegram Bot主程序
- ffmpeg_utils.py - 视频处理工具

## 配置文件 (3个)
- .env.template - 环境变量模板
- COMMANDS.md - 指令文档
- README.md - 部署说明

## 脚本 (2个)
- install.py - 自动配置脚本
- comfy_bot.bat - Windows启动脚本

## 使用方法

### 方式1: 自动配置 (推荐)
```bash
python install.py
```
按提示输入ComfyUI路径和Bot Token，自动完成配置。

### 方式2: 手动配置
1. 复制 `.env.template` 为 `.env`
2. 编辑 `.env` 填入实际路径和Token
3. 手动修改各Python文件中的硬编码路径

### 启动
```bash
# 方式1: 批处理
comfy_bot.bat

# 方式2: 直接运行
python comfy_bot.py
```

### 开机自启
Win+R 输入 `shell:startup`，将 `comfy_bot.bat` 复制进去。

## 迁移到新环境
1. 打包整个 `deployment/` 文件夹
2. 在新机器上安装ComfyUI
3. 运行 `python install.py` 重新配置
4. 测试启动

## 文件大小
- 核心代码: ~50KB
- 不含ComfyUI和模型文件
