# ComfyUI 模型清单

Bot 支持的所有管线及其所需模型文件。

## 文生图管线

### 1. RedCraft DX3 (默认文生图)
**指令**: `/img`

**模型文件**:
```
models/unet/
  └── redcraftFeb1926Latest_zibDistilledDX3Lucis.safetensors

models/clip/
  └── huihui-qwen3-4b-abliterated-v2-q8_0.gguf

models/vae/
  └── ae.sft
```

**下载**:
- RedCraft: https://civitai.com/models/...
- Qwen3 CLIP: https://huggingface.co/...
- VAE: ComfyUI 自带

---

### 2. Moody ZIB+ZIT (双模型高质量)
**指令**: `/md`

**模型文件**:
```
models/unet/
  ├── zimage base/moody-wild-V1-distilled-10steps.safetensors  (ZIB)
  └── moody-v9.safetensors  (ZIT)

models/clip/
  └── qwen_3_4b.safetensors

models/vae/
  └── ae.safetensors

models/upscale_models/
  └── 1xSkinContrast-SuperUltraCompact.pth
```

**下载**:
- Moody ZIB: https://civitai.com/models/...
- Moody ZIT: https://civitai.com/models/...

---

## 视频生成管线

### 3. Wan2.2 AIO T2V (文生视频)
**指令**: `/t2v`

**模型文件**:
```
models/checkpoints/
  └── wan2.2-t2v-rapid-aio-v10-nsfw.safetensors
```

**下载**:
- Wan2.2 T2V: https://huggingface.co/...

---

### 4. Wan2.2 AIO I2V (图生视频)
**指令**: `/i2v`

**模型文件**:
```
models/checkpoints/
  └── wan2.2-i2v-rapid-aio-v10-nsfw.safetensors

models/clip_vision/
  └── clip_vision_h.safetensors

models/vae/
  └── wan_2.1_vae.safetensors
```

**下载**:
- Wan2.2 I2V: https://huggingface.co/...
- CLIP Vision: ComfyUI 自带

---

## FaceID 换脸管线

### 5. Klein9b FaceID
**指令**: `/id`

**模型文件**:
```
models/unet/
  └── F2K-9b-darkBeastMar0326Latest_dbkleinv2BFS.safetensors

models/clip/
  └── qwen_3_8b_fp8mixed.safetensors

models/vae/
  └── flux2-vae.safetensors
```

**下载**:
- Klein9b: https://civitai.com/models/...
- Qwen3 8B: https://huggingface.co/...

---

## 可选: 视频插帧

**RIFE 插帧模型** (用于提升视频帧率):
```
models/rife/
  └── flownet.pkl
```

**下载**:
- RIFE: https://github.com/hzwer/ECCV2022-RIFE

---

## 快速下载脚本

```bash
# 创建模型目录
cd D:\ComfyUI\ComfyUI_windows_portable\ComfyUI
mkdir -p models/unet models/clip models/vae models/checkpoints models/clip_vision models/upscale_models

# 使用 ComfyUI Manager 自动下载
# 或手动从上述链接下载并放入对应目录
```

---

## 模型大小参考

| 模型 | 大小 | 用途 |
|------|------|------|
| RedCraft DX3 | ~8GB | 文生图 |
| Moody ZIB+ZIT | ~12GB | 高质量文生图 |
| Wan2.2 T2V | ~15GB | 文生视频 |
| Wan2.2 I2V | ~15GB | 图生视频 |
| Klein9b | ~18GB | FaceID 换脸 |

**总计**: 约 70GB（如果全部安装）

---

## 最小配置

如果只想快速测试，最少需要：
- RedCraft DX3 (文生图)
- Qwen3 CLIP
- ae.sft VAE

约 10GB 即可运行 `/img` 指令。
