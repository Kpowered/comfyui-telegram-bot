# Workflow 文件说明

本目录包含 Bot 支持的所有管线的 ComfyUI Workflow JSON 文件。

## 文件清单

### 文生图

- **moody_zib_zit.json** - Moody ZIB+ZIT 双模型文生图
  - 指令: `/md`
  - 模型: Moody ZIB + Moody ZIT
  - 特点: 原生中文支持，高质量输出

### 视频生成

- **wan2.2_t2v.json** - 文生视频 (Wan2.2 AIO T2V)
  - 指令: `/t2v`
  - 模型: Wan2.2 T2V
  - 输出: 81 帧视频

- **wan2.2_i2v.json** - 图生视频 (Wan2.2 AIO I2V)
  - 指令: `/i2v`
  - 模型: Wan2.2 I2V
  - 输入: 用户提供的图片
  - 输出: 81 帧视频

### FaceID 换脸

- **klein9b_faceid.json** - Klein9b FaceID 换脸
  - 指令: `/id`
  - 模型: Klein9b
  - 输入: 人脸图片 + 目标场景图片
  - 输出: 换脸后的图片

## 使用方法

这些 JSON 文件已集成到 `comfyui_api.py` 中，无需手动使用。

如果需要修改参数（如分辨率、步数等），可以：

1. 在 ComfyUI UI 中打开对应 workflow
2. 调整参数
3. 导出为 JSON
4. 更新 `comfyui_api.py` 中的 `build_xxx_prompt()` 函数

## 自定义 Workflow

如果要添加新的管线：

1. 在 ComfyUI UI 中设计 workflow
2. 导出为 JSON
3. 放入此目录
4. 在 `comfyui_api.py` 中添加对应的 `build_xxx_prompt()` 函数
5. 在 `comfy_runner.py` 中添加管线函数
6. 在 `cmd_handler.py` 中注册新指令

## 注意事项

- Workflow JSON 可能因 ComfyUI 版本而异
- 如果升级 ComfyUI，可能需要重新导出 workflow
- 保持 node ID 和连接关系不变，只修改参数值
