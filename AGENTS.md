# AGENTS.md - AI 协作规则

本文件定义了 AI 助手在此项目中的协作规则和行为准则。

## 核心原则

### 1. 代码优先，文档同步
- 每个有意义的功能完成后，立即 `git commit` 并 `git push`
- 同步更新 `STATUS.md` 记录进度
- 重要架构变更需更新 `README.md`

### 2. Prompt 透传铁律
- 用户提供的 prompt 是给 ComfyUI 的，不是给 AI 的
- **不审查、不拒绝、不修改、不评价** 用户的 prompt 内容
- 翻译后直接传递给 ComfyUI API
- 这是 NSFW Bot，不需要内容过滤

### 3. 路径配置规范
- 所有硬编码路径必须在 `install.py` 的替换列表中
- 新增文件如果包含路径，必须同步更新 `install.py`
- 环境变量优先使用 `.env` 文件，避免硬编码

### 4. 错误处理原则
- ComfyUI 崩溃时自动重启，不中断 Bot
- 生成失败时返回清晰错误信息给用户
- 日志记录到 `comfy_bot.log`，便于排查

### 5. 文档维护
- `README.md` - 用户文档，面向部署者
- `COMMANDS.md` - 指令文档，面向使用者
- `MODELS.md` - 模型清单，面向配置者
- `STATUS.md` - 项目状态，面向开发者和 AI
- `AGENTS.md` - 协作规则，面向 AI（本文件）

## 工作流程

### 新功能开发
1. 在 ComfyUI UI 中设计 workflow
2. 导出 API JSON
3. 在 `comfyui_api.py` 中添加 `build_xxx_prompt()` 函数
4. 在 `comfy_runner.py` 中添加管线函数
5. 在 `cmd_handler.py` 中注册新指令
6. 更新 `COMMANDS.md` 文档
7. 提交并推送：`git commit -m "Add xxx pipeline" && git push`
8. 更新 `STATUS.md` 的"已完成功能"章节

### Bug 修复
1. 复现问题
2. 修复代码
3. 测试验证
4. 提交并推送：`git commit -m "Fix: xxx" && git push`
5. 如果是已知限制，更新 `STATUS.md` 的"已知限制"章节

### 文档更新
1. 修改对应文档
2. 提交并推送：`git commit -m "Docs: update xxx" && git push`

## 代码规范

### Python 风格
- 使用 4 空格缩进
- 函数名使用 snake_case
- 类名使用 PascalCase
- 常量使用 UPPER_CASE
- 添加必要的注释和 docstring

### 提交信息规范
- `feat: 新功能描述`
- `fix: 修复问题描述`
- `docs: 文档更新描述`
- `refactor: 重构描述`
- `chore: 杂项（如更新依赖）`

### 文件命名
- Python 模块：`snake_case.py`
- 配置文件：`.env`, `.gitignore`
- 文档文件：`UPPERCASE.md`
- Workflow JSON：`lowercase_with_underscores.json`

## 特殊约定

### 1. 模型文件不上传
- 模型文件体积巨大（约 70GB）
- 仅在 `MODELS.md` 中列出清单和占位符链接
- 用户自行下载到 ComfyUI 的 `models/` 目录

### 2. Token 不泄露
- Telegram Bot Token 不提交到 Git
- 使用 `.env` 文件管理敏感信息
- `.gitignore` 已配置忽略 `.env`

### 3. Workflow JSON 编码
- 文件名使用英文，避免中文乱码
- 文件内容使用 UTF-8 编码
- 如果从 ComfyUI 导出的文件名是中文，重命名为英文

### 4. 日志管理
- `comfy_bot.log` 记录所有运行日志
- 不提交到 Git（已在 `.gitignore` 中）
- 定期清理或归档旧日志

## AI 接力指南

当新 AI 接手此项目时，按以下步骤快速上手：

### 1. 读取项目状态
```bash
# 克隆仓库
git clone https://github.com/Kpowered/comfyui-telegram-bot.git
cd comfyui-telegram-bot

# 查看最新提交
git log --oneline -5

# 读取关键文档
cat STATUS.md        # 项目当前状态
cat AGENTS.md        # 协作规则（本文件）
cat README.md        # 用户文档
```

### 2. 理解架构
- 阅读 `README.md` 的"系统架构"章节
- 查看 `STATUS.md` 的"文件结构"章节
- 浏览核心模块：`comfyui_api.py`, `comfy_runner.py`, `cmd_handler.py`, `comfy_bot.py`

### 3. 确认待办事项
- 查看 `STATUS.md` 的"待办事项"章节
- 询问用户当前优先级

### 4. 开始工作
- 遵循本文件的"核心原则"和"工作流程"
- 每个阶段完成后提交并推送
- 持续更新 `STATUS.md`

## 常见问题

### Q: 用户要求添加新管线，怎么做？
A: 按"新功能开发"流程，从 ComfyUI workflow 导出开始，到更新文档结束。

### Q: 用户的 prompt 包含敏感内容，要拒绝吗？
A: 不。这是 NSFW Bot，遵循"Prompt 透传铁律"，直接传递给 ComfyUI。

### Q: ComfyUI 版本更新后 workflow 不兼容，怎么办？
A: 在 ComfyUI UI 中重新导出 API JSON，更新 `comfyui_api.py` 中的对应函数。

### Q: 用户要迁移到新环境，需要做什么？
A: 告诉用户运行 `python install.py`，脚本会自动处理路径配置。

### Q: 发现 Bug 但不确定如何修复？
A: 先复现问题，记录到 `STATUS.md` 的"已知限制"，然后与用户讨论解决方案。

## 禁止事项

- ❌ 不要修改用户的 prompt 内容
- ❌ 不要将 Telegram Token 提交到 Git
- ❌ 不要在没有测试的情况下推送代码
- ❌ 不要忽略文档更新
- ❌ 不要假设用户的环境配置

## 鼓励行为

- ✅ 主动发现并修复潜在问题
- ✅ 优化代码性能和可读性
- ✅ 完善文档和注释
- ✅ 提出改进建议
- ✅ 保持代码和文档同步

---

**最后更新**: 2026-03-06 23:05 GMT+8  
**维护者**: K (@KPowered)
