"""
ComfyUI API 对接模块 - 文生图
通过 ComfyUI REST API 提交工作流、轮询进度、取回结果图片。
"""

import json
import os
import time
import uuid
import urllib.request
import urllib.error
import urllib.parse

COMFYUI_URL = "http://127.0.0.1:8188"
OUTPUT_DIR = r"D:\ComfyUI\ComfyUI_windows_portable\ComfyUI\output"


def build_txt2img_prompt(
    positive_prompt: str,
    width: int = 1152,
    height: int = 1152,
    steps: int = 5,
    cfg: float = 1.0,
    seed: int | None = None,
) -> dict:
    """构建文生图的 API prompt"""
    if seed is None:
        import random
        seed = random.randint(0, 2**53)

    prompt = {
        "3": {
            "class_type": "CLIPLoaderGGUF",
            "inputs": {
                "clip_name": "huihui-qwen3-4b-abliterated-v2-q8_0.gguf",
                "type": "lumina2",
            }
        },
        "4": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "ae.sft"
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": positive_prompt,
                "clip": ["3", 0]
            }
        },
        "47": {
            "class_type": "ConditioningZeroOut",
            "inputs": {
                "conditioning": ["7", 0]
            }
        },
        "10": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1
            }
        },
        "43": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "redcraftFeb1926Latest_zibDistilledDX3Lucis.safetensors",
                "weight_dtype": "default"
            }
        },
        "9": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["43", 0],
                "positive": ["7", 0],
                "negative": ["47", 0],
                "latent_image": ["10", 0],
                "seed": seed,
                "control_after_generate": "fixed",
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0
            }
        },
        "25": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["9", 0],
                "vae": ["4", 0]
            }
        },
        "12": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["25", 0],
                "filename_prefix": "api/txt2img"
            }
        }
    }
    return prompt


def queue_prompt(prompt: dict, client_id: str | None = None) -> str:
    """提交 prompt 到 ComfyUI，返回 prompt_id"""
    if client_id is None:
        client_id = str(uuid.uuid4())

    payload = json.dumps({
        "prompt": prompt,
        "client_id": client_id
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        return result["prompt_id"]
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        raise RuntimeError(f"Failed to queue prompt: HTTP {e.code} {e.reason}; body={body}")
    except Exception as e:
        raise RuntimeError(f"Failed to queue prompt: {e}")


def poll_history(prompt_id: str, timeout: int = 1800, interval: float = 2.0) -> dict:
    """轮询直到 prompt 完成，返回 history 数据"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{COMFYUI_URL}/queue", timeout=10) as resp:
                queue = json.loads(resp.read())

            in_queue = False
            for item in queue.get("queue_running", []) + queue.get("queue_pending", []):
                if len(item) >= 2 and item[1] == prompt_id:
                    in_queue = True
                    break

            if not in_queue:
                with urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}", timeout=10) as resp:
                    history = json.loads(resp.read())
                if prompt_id in history:
                    status = history[prompt_id].get("status", {})
                    if status.get("completed", False) or status.get("status_str") == "success":
                        return history[prompt_id]
                    if "outputs" in history[prompt_id] and history[prompt_id]["outputs"]:
                        return history[prompt_id]
        except urllib.error.URLError:
            pass
        except Exception:
            pass
        time.sleep(interval)
    raise TimeoutError(f"ComfyUI prompt {prompt_id} timed out after {timeout}s")


def get_output_images(history: dict) -> list[dict]:
    """从 history 中提取输出图片信息列表"""
    images = []
    outputs = history.get("outputs", {})
    for node_id, node_output in outputs.items():
        if "images" in node_output:
            for img in node_output["images"]:
                images.append(img)
    return images


def get_image_path(img_info: dict) -> str:
    """根据图片信息构建本地文件路径"""
    subfolder = img_info.get("subfolder", "")
    filename = img_info["filename"]
    return os.path.join(OUTPUT_DIR, subfolder, filename)


def txt2img(
    prompt_text: str,
    width: int = 1152,
    height: int = 1152,
    steps: int = 5,
    seed: int | None = None,
) -> list[str]:
    """
    一键文生图。返回本地图片路径列表。
    """
    prompt = build_txt2img_prompt(
        positive_prompt=prompt_text,
        width=width,
        height=height,
        steps=steps,
        seed=seed,
    )
    prompt_id = queue_prompt(prompt)
    history = poll_history(prompt_id)
    images = get_output_images(history)
    paths = [get_image_path(img) for img in images]
    return paths



def upload_image(image_path: str) -> str:
    """上传图片到 ComfyUI input 目录，返回文件名"""
    import mimetypes
    filename = os.path.basename(image_path)
    mime_type = mimetypes.guess_type(image_path)[0] or "image/png"

    boundary = uuid.uuid4().hex
    with open(image_path, "rb") as f:
        image_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8") + image_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        f"{COMFYUI_URL}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    return result["name"]



def build_img2video_prompt(
    positive_prompt: str,
    image_name: str,
    negative_prompt: str = (
        "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，"
        "最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，"
        "画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，"
        "杂乱的背景，三条腿，背景人很多，倒着走, "
        "censored, mosaic censoring, bar censor, pixelated, glowing, bloom, blurry, day, "
        "out of focus, low detail, bad anatomy, ugly, overexposed, underexposed, "
        "distorted face, extra limbs, cartoonish, 3d render artifacts, duplicate people, "
        "unnatural lighting, bad composition, missing shadows, low resolution, "
        "poorly textured, glitch, noise, grain, static, motionless, still frame, "
        "overall grayish, worst quality, low quality, JPEG compression artifacts, "
        "subtitles, stylized, artwork, painting, illustration, cluttered background, "
        "many people in background, three legs, walking backward, zoom out, zoom in, "
        "mouth speaking, moving mouth, talking, speaking, mute speaking, "
        "unnatural skin tone, discolored eyelid, red eyelids, red upper eyelids, "
        "no red eyeshadow, closed eyes, no wide-open innocent eyes, "
        "poorly drawn hands, extra fingers, fused fingers, poorly drawn face, "
        "deformed, disfigured, malformed limbs, thighs, fog, mist, "
        "voluminous eyelashes, blush,"
    ),
    width: int = 832,
    height: int = 480,
    length: int = 80,

    steps: int = 10,
    cfg: float = 1.15,
    high_steps: int = 5,
    seed: int | None = None,
    audio_prompt: str | None = None,
    audio_negative: str = "music, singing, speech, dialogue, voiceover, narration, words, harsh, loud, distorted, clipping, echo, reverb, low quality, noise, music, songs, music video, background music.",
    audio_steps: int = 75,
    audio_cfg: float = 5.0,
    norife: bool = False,
    out_tag: str = 'img2video',
) -> dict:
    """构建图生视频 API prompt — 双阶段采样 (Smooth Workflow v3.0)

    High 模型跑前 high_steps 步，Low 模型跑剩余步数。
    ImageResizeKJv2 节点做输入图缩放（lanczos, 16像素对齐）。
    """
    if seed is None:
        import random
        seed = random.randint(0, 2**53)

    prompt = {
        # LoadImage (184)
        "184": {
            "class_type": "LoadImage",
            "inputs": {
                "image": image_name
            }
        },
        # ImageResizeKJv2 (182) - lanczos, 16像素对齐
        "182": {
            "class_type": "ImageResizeKJv2",
            "inputs": {
                "image": ["184", 0],
                "width": width,
                "height": height,
                "upscale_method": "lanczos",
                "keep_proportion": "resize",
                "pad_color": "0, 0, 0",
                "crop_position": "center",
                "divisible_by": 16,
                "device": "cpu"
            }
        },
        # CLIPVisionLoader (190)
        "190": {
            "class_type": "CLIPVisionLoader",
            "inputs": {
                "clip_name": "clip_vision_h.safetensors"
            }
        },
        # CLIPVisionEncode (189) - crop=none
        "189": {
            "class_type": "CLIPVisionEncode",
            "inputs": {
                "clip_vision": ["190", 0],
                "image": ["184", 0],
                "crop": "none"
            }
        },
        # CLIPLoader (192) - umt5, wan, cpu
        "192": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                "type": "wan",
                "device": "cpu"
            }
        },
        # CLIPTextEncode positive (176)
        "176": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": positive_prompt,
                "clip": ["192", 0]
            }
        },
        # CLIPTextEncode negative (195)
        "195": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["192", 0]
            }
        },
        # VAELoader (191)
        "191": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "wan_2.1_vae.safetensors"
            }
        },
        # WanImageToVideo (172)
        "172": {
            "class_type": "WanImageToVideo",
            "inputs": {
                "positive": ["176", 0],
                "negative": ["195", 0],
                "vae": ["191", 0],
                "width": width,
                "height": height,
                "length": length,
                "batch_size": 1,
                "clip_vision_output": ["189", 0],
                "start_image": ["182", 0]
            }
        },
        # UNETLoader High (197)
        "197": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "smoothMixWan2214BI2V_i2vV20High.safetensors",
                "weight_dtype": "default"
            }
        },
        # Power Lora Loader High (201) - 空挂，预留 LoRA 位
        "201": {
            "class_type": "Power Lora Loader (rgthree)",
            "inputs": {
                "model": ["197", 0],
            }
        },
        # ModelSamplingSD3 High (168)
        "168": {
            "class_type": "ModelSamplingSD3",
            "inputs": {
                "model": ["201", 0],
                "shift": 8.0
            }
        },
        # UNETLoader Low (186) - 改用 High 模型（Low 已损坏）
        "186": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "smoothMixWan2214BI2V_i2vV20High.safetensors",
                "weight_dtype": "default"
            }
        },
        # Power Lora Loader Low (200) - 空挂，预留 LoRA 位
        "200": {
            "class_type": "Power Lora Loader (rgthree)",
            "inputs": {
                "model": ["186", 0],
            }
        },
        # ModelSamplingSD3 Low (169)
        "169": {
            "class_type": "ModelSamplingSD3",
            "inputs": {
                "model": ["200", 0],
                "shift": 8.0
            }
        },
        # KSamplerAdvanced High (206) - 前 high_steps 步
        "206": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["168", 0],
                "add_noise": "enable",
                "noise_seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler_ancestral",
                "scheduler": "simple",
                "positive": ["172", 0],
                "negative": ["172", 1],
                "latent_image": ["172", 2],
                "start_at_step": 0,
                "end_at_step": high_steps,
                "return_with_leftover_noise": "enable"
            }
        },
        # KSamplerAdvanced Low (205) - high_steps 步之后
        "205": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["169", 0],
                "add_noise": "disable",
                "noise_seed": 0,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler_ancestral",
                "scheduler": "simple",
                "positive": ["172", 0],
                "negative": ["172", 1],
                "latent_image": ["206", 0],
                "start_at_step": high_steps,
                "end_at_step": 10000,
                "return_with_leftover_noise": "disable"
            }
        },
        # cleanGpuUsed (179) - 采样后释放显存
        "179": {
            "class_type": "easy cleanGpuUsed",
            "inputs": {
                "anything": ["205", 0]
            }
        },
        # VAEDecode (171)
        "171": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["179", 0],
                "vae": ["191", 0]
            }
        },
        # Pick From Batch (167) - 取最后一帧用于 ColorMatch
        "167": {
            "class_type": "Pick From Batch (mtb)",
            "inputs": {
                "image": ["171", 0],
                "from_direction": "end",
                "count": 1
            }
        },
        # ColorMatch (165) - 最后一帧颜色匹配原图
        "165": {
            "class_type": "ColorMatch",
            "inputs": {
                "image_ref": ["184", 0],
                "image_target": ["167", 0],
                "method": "mkl",
                "strength": 0.4,
                "multithread": True
            }
        },
        # ImageScaleBy for last frame (166) - lanczos 2x
        "166": {
            "class_type": "ImageScaleBy",
            "inputs": {
                "image": ["165", 0],
                "upscale_method": "lanczos",
                "scale_by": 2.0
            }
        },
        # SaveImage last frame (164)
        "164": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["166", 0],
                "filename_prefix": "api/img2video_lastframe"
            }
        },
        # ImageScaleBy 2x lanczos (181) - 全帧序列放大
        "181": {
            "class_type": "ImageScaleBy",
            "inputs": {
                "image": ["171", 0],
                "upscale_method": "lanczos",
                "scale_by": 2.0
            }
        },
        # cleanGpuUsed (199) - upscale 后释放显存
        "199": {
            "class_type": "easy cleanGpuUsed",
            "inputs": {
                "anything": ["181", 0]
            }
        },
        # RIFEInterpolation (212) - 16fps -> 25fps
        "212": {
            "class_type": "RIFEInterpolation",
            "inputs": {
                "images": ["199", 0],
                "source_fps": 16,
                "target_fps": 25,
                "scale": 1.0,
                "model_name": "flownet.pkl",
                "batch_size": 8,
                "use_fp16": True
            }
        },
        # VHS_VideoCombine (198) - h264-mp4
        "198": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                # 大动作段可通过 norife=True 直接绕过插帧，避免重影
                "images": ["199", 0] if norife else ["212", 0],
                "frame_rate": 16 if norife else 25,
                "loop_count": 0,
                "filename_prefix": f"Video/{out_tag}",
                "format": "video/h264-mp4",
                "pix_fmt": "yuv420p",
                "crf": 16,
                "save_metadata": True,
                "trim_to_audio": False,
                "pingpong": False,
                "save_output": True
            }
        }
    }

    # MMAudio 音频生成（仅当 audio_prompt 不为 None 时启用）
    if audio_prompt is not None:
        import random as _rnd
        audio_seed = _rnd.randint(0, 2**53)
        duration_sec = length / 16.2  # 帧数转秒数

        # MMAudioModelLoader (211)
        prompt["211"] = {
            "class_type": "MMAudioModelLoader",
            "inputs": {
                "mmaudio_model": "mmaudio_large_44k_v2_fp16.safetensors",
                "base_precision": "fp16"
            }
        }
        # MMAudioFeatureUtilsLoader (204)
        prompt["204"] = {
            "class_type": "MMAudioFeatureUtilsLoader",
            "inputs": {
                "vae_model": "mmaudio_vae_44k_fp16.safetensors",
                "synchformer_model": "mmaudio_synchformer_fp16.safetensors",
                "clip_model": "apple_DFN5B-CLIP-ViT-H-14-384_fp16.safetensors",
                "mode": "44k",
                "precision": "fp16"
            }
        }
        # MMAudioSampler (214)
        prompt["214"] = {
            "class_type": "MMAudioSampler",
            "inputs": {
                "mmaudio_model": ["211", 0],
                "feature_utils": ["204", 0],
                "images": ["212", 0],
                "duration": duration_sec,
                "steps": audio_steps,
                "cfg": audio_cfg,
                "seed": audio_seed,
                "prompt": audio_prompt,
                "negative_prompt": audio_negative,
                "mask_away_clip": False,
                "force_offload": True
            }
        }
        # NormalizeAudioLoudness (207)
        prompt["207"] = {
            "class_type": "NormalizeAudioLoudness",
            "inputs": {
                "audio": ["214", 0],
                "lufs": -25.0
            }
        }
        # 把音频接入 VHS_VideoCombine
        prompt["198"]["inputs"]["audio"] = ["207", 0]

    return prompt


def get_output_videos(history: dict) -> list[dict]:
    """从 history 中提取输出视频信息（SaveVideo 输出在 images 字段里）"""
    videos = []
    outputs = history.get("outputs", {})
    for node_id, node_output in outputs.items():
        # SaveVideo 把 mp4 放在 "images" 字段
        for key in ("videos", "images", "gifs"):
            if key in node_output:
                for item in node_output[key]:
                    fname = item.get("filename", "")
                    if fname.endswith((".mp4", ".webm", ".avi")):
                        videos.append(item)
    return videos


def img2video_submit(
    prompt_text: str,
    image_path: str,
    negative_prompt: str = "blurry, low detail, jpeg artifacts, distorted face, extra limbs, bad anatomy, text, subtitles",
    width: int = 832,
    height: int = 480,
    length: int = 80,
    steps: int = 10,
    cfg: float = 1.15,
    high_steps: int = 5,
    seed: int | None = None,
    audio_prompt: str | None = None,
    audio_negative: str = "music, singing, speech, dialogue, voiceover, narration, words, harsh, loud, distorted, clipping, echo, reverb, low quality, noise, music, songs, music video, background music.",
    audio_steps: int = 75,
    audio_cfg: float = 5.0,
    norife: bool = False,
    out_tag: str = "img2video",
) -> str:
    """
    异步提交图生视频任务，立即返回 prompt_id。
    双阶段采样：High 模型跑前 high_steps 步，Low 模型跑剩余步数。
    """
    uploaded_name = upload_image(image_path)

    prompt = build_img2video_prompt(
        positive_prompt=prompt_text,
        image_name=uploaded_name,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        length=length,
        steps=steps,
        cfg=cfg,
        high_steps=high_steps,
        seed=seed,
        audio_prompt=audio_prompt,
        audio_negative=audio_negative,
        audio_steps=audio_steps,
        audio_cfg=audio_cfg,
        norife=norife,
        out_tag=out_tag,
    )

    prompt_id = queue_prompt(prompt)
    return prompt_id


def check_video_status(prompt_id: str) -> dict:
    """
    检查视频生成状态。返回:
    {"status": "running", "progress": "5/20"}
    {"status": "success", "paths": ["D:/...mp4"]}
    {"status": "error", "message": "..."}
    """
    try:
        with urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}") as resp:
            history = json.loads(resp.read())
    except urllib.error.URLError:
        return {"status": "running", "progress": "unknown"}

    if prompt_id not in history:
        # 检查队列
        try:
            with urllib.request.urlopen(f"{COMFYUI_URL}/queue") as resp:
                queue = json.loads(resp.read())
            running = queue.get("queue_running", [])
            pending = queue.get("queue_pending", [])
            for item in running:
                if len(item) > 1 and item[1] == prompt_id:
                    return {"status": "running", "progress": "sampling"}
            for item in pending:
                if len(item) > 1 and item[1] == prompt_id:
                    return {"status": "running", "progress": "queued"}
        except urllib.error.URLError:
            pass
        return {"status": "running", "progress": "unknown"}

    entry = history[prompt_id]
    status_info = entry.get("status", {})

    if status_info.get("status_str") == "error":
        msgs = status_info.get("messages", [])
        err_msg = "unknown error"
        for msg in msgs:
            if msg[0] == "execution_error" and len(msg) > 1:
                err_msg = msg[1].get("exception_message", err_msg)
        return {"status": "error", "message": err_msg}

    if status_info.get("completed", False) or status_info.get("status_str") == "success":
        videos = get_output_videos(entry)
        paths = []
        for vid in videos:
            subfolder = vid.get("subfolder", "")
            filename = vid["filename"]
            paths.append(os.path.join(OUTPUT_DIR, subfolder, filename))
        return {"status": "success", "paths": paths}

    return {"status": "running", "progress": "processing"}






def build_moody_zib_zit_prompt(
    positive_prompt: str,
    negative_prompt: str = "artifacts, model, figurine, low resolution, blurry image, overexposed, light leaks, JPEG compression, watermark, noise, body imperfections, text",
    width: int = 1920,
    height: int = 1080,
    zib_steps: int = 9,
    zib_cfg: float = 1.0,
    zib_end_step: int = 7,
    zit_steps: int = 9,
    zit_cfg: float = 1.0,
    zit_start_step: int = 4,
    seed: int | None = None,
) -> dict:
    """构建 Moody ZIB+ZIT 双模型文生图工作流（直接生成目标分辨率）"""
    import random
    if seed is None:
        seed = random.randint(0, 2**53)

    prompt = {
        # CLIP + VAE
        "1": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen_3_4b.safetensors",
                "type": "lumina2",
                "device": "default",
            }
        },
        "2": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ae.safetensors"}
        },
        # Positive / Negative prompts
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": positive_prompt,
                "clip": ["1", 0],
            }
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["1", 0],
            }
        },
        "5": {
            "class_type": "ConditioningZeroOut",
            "inputs": {"conditioning": ["3", 0]}
        },
        # Empty latent - 直接使用目标分辨率
        "6": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1}
        },
        # === Stage 1: ZIB ===
        "10": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "zimage base\\moody-wild-V1-distilled-10steps.safetensors",
                "weight_dtype": "default",
            }
        },
        "11": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"shift": 3.0, "model": ["10", 0]}
        },
        "12": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "add_noise": "enable",
                "noise_seed": seed,
                "control_after_generate": "randomize",
                "steps": zib_steps,
                "cfg": zib_cfg,
                "sampler_name": "dpmpp_2m_sde",
                "scheduler": "beta",
                "start_at_step": 0,
                "end_at_step": zib_end_step,
                "return_with_leftover_noise": "enable",
                "model": ["11", 0],
                "positive": ["3", 0],
                "negative": ["4", 0],
                "latent_image": ["6", 0],
            }
        },
        # === Stage 2: ZIT (直接在目标分辨率上继续) ===
        "20": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "moodyPornMix_zitV9.safetensors",
                "weight_dtype": "default",
            }
        },
        "21": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"shift": 3.0, "model": ["20", 0]}
        },
        "22": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "add_noise": "disable",
                "noise_seed": seed,
                "control_after_generate": "randomize",
                "steps": zit_steps,
                "cfg": zit_cfg,
                "sampler_name": "dpmpp_2m_sde",
                "scheduler": "beta",
                "start_at_step": zit_start_step,
                "end_at_step": 10000,
                "return_with_leftover_noise": "disable",
                "model": ["21", 0],
                "positive": ["3", 0],
                "negative": ["5", 0],
                "latent_image": ["12", 0],
            }
        },
        # VAE Decode
        "30": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["22", 0],
                "vae": ["2", 0],
            }
        },
        # Save
        "50": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "moody",
                "images": ["30", 0],
            }
        },
    }
    return prompt
    """构建 Moody ZIB+ZIT 双模型文生图工作流"""
    import random
    if seed is None:
        seed = random.randint(0, 2**53)
    seed2 = random.randint(0, 2**53)

    # 计算 tile 尺寸: (dim_after_latent_upscale * upscale_by + 64) / 2
    scaled_w = int(width * latent_scale)
    scaled_h = int(height * latent_scale)
    tile_w = int((scaled_w * upscale_by + 64) / 2)
    tile_h = int((scaled_h * upscale_by + 64) / 2)

    prompt = {
        # CLIP + VAE
        "1": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen_3_4b.safetensors",
                "type": "lumina2",
                "device": "default",
            }
        },
        "2": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ae.safetensors"}
        },
        # Positive / Negative prompts
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": positive_prompt,
                "clip": ["1", 0],
            }
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["1", 0],
            }
        },
        "5": {
            "class_type": "ConditioningZeroOut",
            "inputs": {"conditioning": ["3", 0]}
        },
        # Empty latent
        "6": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1}
        },
        # === Stage 1: ZIB ===
        "10": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "zimage base\\moody-wild-V1-distilled-10steps.safetensors",
                "weight_dtype": "default",
            }
        },
        "11": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"shift": 3.0, "model": ["10", 0]}
        },
        "12": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "add_noise": "enable",
                "noise_seed": seed,
                "control_after_generate": "randomize",
                "steps": zib_steps,
                "cfg": zib_cfg,
                "sampler_name": "res_multistep",
                "scheduler": "simple",
                "start_at_step": 0,
                "end_at_step": zib_end_step,
                "return_with_leftover_noise": "enable",
                "model": ["11", 0],
                "positive": ["3", 0],
                "negative": ["4", 0],
                "latent_image": ["6", 0],
            }
        },
        # Latent upscale 1.6x
        "13": {
            "class_type": "LatentUpscaleBy",
            "inputs": {
                "upscale_method": "bislerp",
                "scale_by": latent_scale,
                "samples": ["12", 0],
            }
        },
        # === Stage 2: ZIT ===
        "20": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "moody-v9.safetensors",
                "weight_dtype": "default",
            }
        },
        "21": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"shift": 3.0, "model": ["20", 0]}
        },
        "22": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "add_noise": "disable",
                "noise_seed": seed2,
                "control_after_generate": "randomize",
                "steps": zit_steps,
                "cfg": zit_cfg,
                "sampler_name": "dpmpp_2m_sde",
                "scheduler": "beta",
                "start_at_step": zit_start_step,
                "end_at_step": 10000,
                "return_with_leftover_noise": "disable",
                "model": ["21", 0],
                "positive": ["3", 0],
                "negative": ["5", 0],
                "latent_image": ["13", 0],
            }
        },
        # VAE Decode (stage 2 output)
        "30": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["22", 0],
                "vae": ["2", 0],
            }
        },
        # === UltimateSDUpscale ===
        "40": {
            "class_type": "UpscaleModelLoader",
            "inputs": {"model_name": "1xSkinContrast-SuperUltraCompact.pth"}
        },
        "41": {
            "class_type": "UltimateSDUpscale",
            "inputs": {
                "image": ["30", 0],
                "model": ["21", 0],
                "positive": ["3", 0],
                "negative": ["5", 0],
                "vae": ["2", 0],
                "upscale_model": ["40", 0],
                "upscale_by": upscale_by,
                "seed": seed2,
                "steps": upscale_steps,
                "cfg": upscale_cfg,
                "sampler_name": "dpmpp_2m_sde",
                "scheduler": "beta",
                "denoise": upscale_denoise,
                "mode_type": "Linear",
                "tile_width": tile_w,
                "tile_height": tile_h,
                "mask_blur": 64,
                "tile_padding": 32,
                "seam_fix_mode": "None",
                "seam_fix_denoise": 1.0,
                "seam_fix_width": 64,
                "seam_fix_mask_blur": 8,
                "seam_fix_padding": 16,
                "force_uniform_tiles": True,
                "tiled_decode": False,
                "batch_size": 1,
            }
        },
        # Save
        "50": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "moody",
                "images": ["30", 0],
            }
        },
    }
    return prompt


def moody_zib_zit(
    positive_prompt: str,
    negative_prompt: str = "artifacts, model, figurine, low resolution, blurry image, overexposed, light leaks, JPEG compression, watermark, noise, body imperfections, text",
    width: int = 1920,
    height: int = 1080,
    seed: int | None = None,
    timeout: int = 600,
) -> list[str]:
    """Moody ZIB+ZIT 双模型文生图（直接生成 1920x1080）"""
    print(f"[moody_zib_zit] Building prompt: {width}x{height}", flush=True)
    prompt = build_moody_zib_zit_prompt(
        positive_prompt=positive_prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        seed=seed,
    )
    print(f"[moody_zib_zit] Queueing prompt...", flush=True)
    prompt_id = queue_prompt(prompt)
    print(f"[moody_zib_zit] Prompt queued: {prompt_id}, polling...", flush=True)
    history = poll_history(prompt_id, timeout=timeout)
    print(f"[moody_zib_zit] Poll complete, extracting images...", flush=True)
    images = get_output_images(history)
    paths = [get_image_path(img) for img in images]
    print(f"[moody_zib_zit] Done: {paths}", flush=True)
    return paths


def build_pulid_faceid_prompt(
    prompt_text: str,
    face_image_path: str,
    negative_prompt: str = "",
    width: int = 640,
    height: int = 960,
    steps: int = 20,
    cfg: float = 1.0,
    guidance: float = 4.0,
    weight: float = 1.0,
    start_at: float = 0.0,
    end_at: float = 1.0,
    seed: int | None = None,
) -> dict:
    """构建 PuLID FaceID 图片管线 (Flux1-dev 原版 + PuLID Flux)"""
    if seed is None:
        import random
        seed = random.randint(0, 2**53)

    uploaded_face = upload_image(face_image_path)

    prompt = {
        # DualCLIPLoader: t5xxl_fp8 + clip_l (Flux 原版文本编码器)
        "1": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
                "clip_name2": "clip_l.safetensors",
                "type": "flux"
            }
        },
        # CLIPTextEncode - positive
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt_text, "clip": ["1", 0]}
        },
        # FluxGuidance
        "3": {
            "class_type": "FluxGuidance",
            "inputs": {"conditioning": ["2", 0], "guidance": guidance}
        },
        # UNETLoader - Flux1-dev fp8
        "4": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "flux1-dev-fp8.safetensors", "weight_dtype": "default"}
        },
        # ModelSamplingFlux
        "5": {
            "class_type": "ModelSamplingFlux",
            "inputs": {
                "model": ["4", 0],
                "max_shift": 1.15, "base_shift": 0.5,
                "width": width, "height": height
            }
        },
        # PulidFluxModelLoader
        "6": {
            "class_type": "PulidFluxModelLoader",
            "inputs": {"pulid_file": "pulid_flux_v0.9.0.safetensors"}
        },
        # PulidFluxEvaClipLoader
        "7": {"class_type": "PulidFluxEvaClipLoader", "inputs": {}},
        # PulidFluxInsightFaceLoader
        "8": {
            "class_type": "PulidFluxInsightFaceLoader",
            "inputs": {"provider": "CPU"}
        },
        # LoadImage - face reference
        "9": {
            "class_type": "LoadImage",
            "inputs": {"image": uploaded_face}
        },
        # ApplyPulidFlux
        "10": {
            "class_type": "ApplyPulidFlux",
            "inputs": {
                "model": ["5", 0], "pulid_flux": ["6", 0],
                "eva_clip": ["7", 0], "face_analysis": ["8", 0],
                "image": ["9", 0], "weight": weight,
                "start_at": start_at, "end_at": end_at
            }
        },
        # EmptySD3LatentImage
        "11": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1}
        },
        # KSampler
        "12": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["10", 0], "positive": ["3", 0],
                "negative": ["3", 0], "latent_image": ["11", 0],
                "seed": seed, "steps": steps, "cfg": cfg,
                "sampler_name": "euler", "scheduler": "simple",
                "denoise": 1.0
            }
        },
        # VAELoader
        "13": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ae.safetensors"}
        },
        # VAEDecode
        "14": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["12", 0], "vae": ["13", 0]}
        },
        # SaveImage
        "15": {
            "class_type": "SaveImage",
            "inputs": {"images": ["14", 0], "filename_prefix": "faceid"}
        }
    }
    return prompt


def pulid_faceid(
    prompt_text: str,
    face_image_path: str,
    negative_prompt: str = "",
    width: int = 640, height: int = 960,
    steps: int = 20, weight: float = 1.0,
    guidance: float = 4.0,
    seed: int | None = None, timeout: int = 300,
) -> list[str]:
    """PuLID FaceID 图片生成，返回输出路径列表"""
    prompt = build_pulid_faceid_prompt(
        prompt_text=prompt_text, face_image_path=face_image_path,
        negative_prompt=negative_prompt, width=width, height=height,
        steps=steps, weight=weight, guidance=guidance, seed=seed,
    )
    prompt_id = queue_prompt(prompt)
    for _ in range(timeout):
        time.sleep(1)
        history = poll_history(prompt_id)
        if history:
            images = get_output_images(history)
            return [get_image_path(img) for img in images]
    raise TimeoutError(f"PuLID FaceID timed out after {timeout}s")




# ============ Wan2.2 AIO I2V ============

def build_wan_aio_i2v_prompt(
    positive_prompt: str,
    image_name: str,
    width: int = 640,
    height: int = 640,
    length: int = 81,
    steps: int = 4,
    cfg: float = 1.0,
    seed: int | None = None,
    shift: float = 8.0,
) -> dict:
    """构建 Wan2.2 AIO I2V prompt（基于正确的工作流）"""
    if seed is None:
        import random
        seed = random.randint(0, 2**53)

    return {
        "1": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "", "clip": ["6", 1]}
        },
        "2": {
            "class_type": "CLIPVisionLoader",
            "inputs": {"clip_name": "clip_vision_h.safetensors"}
        },
        "3": {
            "class_type": "CLIPVisionEncode",
            "inputs": {
                "clip_vision": ["2", 0],
                "image": ["15", 0],
                "crop": "none"
            }
        },
        "4": {
            "class_type": "LoadImage",
            "inputs": {"image": image_name}
        },
        "5": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["12", 0],
                "vae": ["6", 2]
            }
        },
        "6": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "wan2.2-i2v-rapid-aio-v10-nsfw.safetensors"}
        },
        "8": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": positive_prompt, "clip": ["6", 1]}
        },
        "9": {
            "class_type": "ModelSamplingSD3",
            "inputs": {"model": ["6", 0], "shift": shift}
        },
        "10": {
            "class_type": "WanImageToVideo",
            "inputs": {
                "positive": ["8", 0],
                "negative": ["1", 0],
                "vae": ["6", 2],
                "clip_vision_output": ["3", 0],
                "start_image": ["15", 0],
                "width": ["15", 3],
                "height": ["15", 4],
                "length": length,
                "batch_size": 1
            }
        },
        "12": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["9", 0],
                "positive": ["10", 0],
                "negative": ["10", 1],
                "latent_image": ["10", 2],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler_ancestral",
                "scheduler": "beta",
                "denoise": 1.0
            }
        },
        "13": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["5", 0],
                "frame_rate": 18,
                "loop_count": 0,
                "filename_prefix": "api/wan_aio_i2v",
                "format": "video/h264-mp4",
                "pix_fmt": "yuv420p",
                "crf": 19,
                "save_metadata": False,
                "trim_to_audio": False,
                "pingpong": False,
                "save_output": True
            }
        },
        "15": {
            "class_type": "LayerUtility: ImageScaleByAspectRatio V2",
            "inputs": {
                "image": ["4", 0],
                "aspect_ratio": "original",
                "proportional_width": 1,
                "proportional_height": 1,
                "fit": "letterbox",
                "method": "lanczos",
                "round_to_multiple": "8",
                "scale_to_side": "shortest",
                "scale_to_length": max(width, height),
                "background_color": "#000000"
            }
        }
    }


def wan_aio_t2v_submit(
    prompt_text: str,
    width: int = 832,
    height: int = 480,
    length: int = 81,
    steps: int = 4,
    cfg: float = 1.0,
    seed: int | None = None,
) -> str:
    """异步提交 Wan2.2 AIO T2V 任务，返回 prompt_id"""
    if seed is None:
        import random
        seed = random.randint(0, 2**53)
    
    prompt = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "wan2.2-t2v-rapid-aio-v10-nsfw.safetensors"}
        },
        "2": {
            "class_type": "ModelSamplingSD3",
            "inputs": {"model": ["1", 0], "shift": 8.0}
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["2", 0],
                "positive": ["5", 0],
                "negative": ["4", 0],
                "latent_image": ["6", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler_ancestral",
                "scheduler": "beta",
                "denoise": 1.0
            }
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "", "clip": ["1", 1]}
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt_text, "clip": ["1", 1]}
        },
        "6": {
            "class_type": "EmptyHunyuanLatentVideo",
            "inputs": {
                "width": width,
                "height": height,
                "length": length,
                "batch_size": 1
            }
        },
        "7": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["1", 2]}
        },
        "13": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["7", 0],
                "frame_rate": 18,
                "loop_count": 0,
                "filename_prefix": "api/wan_aio_t2v",
                "format": "video/h264-mp4",
                "pix_fmt": "yuv420p",
                "crf": 19,
                "save_metadata": False,
                "trim_to_audio": False,
                "pingpong": False,
                "save_output": True
            }
        }
    }
    
    prompt_id = queue_prompt(prompt)
    return prompt_id


def wan_aio_i2v_submit(
    prompt_text: str,
    image_path: str,
    width: int = 640,
    height: int = 640,
    length: int = 81,
    steps: int = 4,
    cfg: float = 1.0,
    seed: int | None = None,
) -> str:
    """异步提交 Wan2.2 AIO I2V 任务，返回 prompt_id"""
    uploaded_name = upload_image(image_path)
    
    prompt = build_wan_aio_i2v_prompt(
        positive_prompt=prompt_text,
        image_name=uploaded_name,
        width=width,
        height=height,
        length=length,
        steps=steps,
        cfg=cfg,
        seed=seed
    )
    
    prompt_id = queue_prompt(prompt)
    return prompt_id


# ============ Klein9b FaceID ============

def build_klein_faceid_prompt(
    prompt_text: str,
    face_image_name: str,
    target_image_name: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 20,
    cfg: float = 1.0,
    seed: int | None = None,
) -> dict:
    """构建 Klein9b FaceID prompt"""
    if seed is None:
        import random
        seed = random.randint(0, 2**53)

    return {
        "1": {
            "class_type": "KSamplerSelect",
            "inputs": {
                "sampler_name": "euler"
            }
        },
        "2": {
            "class_type": "BasicGuider",
            "inputs": {
                "model": ["18", 0],
                "conditioning": ["97", 0]
            }
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "flux2-vae.safetensors"
            }
        },
        "4": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen_3_8b_fp8mixed.safetensors",
                "type": "flux2",
                "device": "default"
            }
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt_text,
                "clip": ["4", 0]
            }
        },
        "10": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "",
                "clip": ["4", 0]
            }
        },
        "14": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["17", 0],
                "guider": ["2", 0],
                "sampler": ["1", 0],
                "sigmas": ["15", 0],
                "latent_image": ["79", 0]
            }
        },
        "15": {
            "class_type": "BasicScheduler",
            "inputs": {
                "scheduler": "simple",
                "steps": steps,
                "denoise": 1.0,
                "model": ["18", 0]
            }
        },
        "17": {
            "class_type": "RandomNoise",
            "inputs": {
                "noise_seed": seed
            }
        },
        "18": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "flux-2-klein\\F2K-9b-darkBeastMar0326Latest_dbkleinv2BFS.safetensors",
                "weight_dtype": "default"
            }
        },
        "20": {
            "class_type": "LoadImage",
            "inputs": {
                "image": target_image_name
            }
        },
        "23": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["162", 0],
                "filename_prefix": "api/klein_faceid"
            }
        },
        "79": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1
            }
        },
        "80": {
            "class_type": "GetImageSize+",
            "inputs": {
                "image": ["98", 0]
            }
        },
        "84": {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["20", 0],
                "upscale_method": "lanczos",
                "width": ["80", 0],
                "height": ["80", 1],
                "crop": "disabled"
            }
        },
        "91": {
            "class_type": "LoadImage",
            "inputs": {
                "image": face_image_name
            }
        },
        "92": {
            "class_type": "ReferenceLatent",
            "inputs": {
                "conditioning": ["10", 0],
                "latent": ["93", 0]
            }
        },
        "93": {
            "class_type": "VAEEncode",
            "inputs": {
                "pixels": ["98", 0],
                "vae": ["3", 0]
            }
        },
        "94": {
            "class_type": "ReferenceLatent",
            "inputs": {
                "conditioning": ["5", 0],
                "latent": ["93", 0]
            }
        },
        "95": {
            "class_type": "ReferenceLatent",
            "inputs": {
                "conditioning": ["92", 0],
                "latent": ["96", 0]
            }
        },
        "96": {
            "class_type": "VAEEncode",
            "inputs": {
                "pixels": ["84", 0],
                "vae": ["3", 0]
            }
        },
        "97": {
            "class_type": "ReferenceLatent",
            "inputs": {
                "conditioning": ["94", 0],
                "latent": ["96", 0]
            }
        },
        "98": {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["91", 0],
                "upscale_method": "lanczos",
                "width": 1024,
                "height": 1024,
                "crop": "center"
            }
        },
        "162": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["14", 0],
                "vae": ["3", 0]
            }
        }
    }


def klein_faceid(
    prompt_text: str,
    face_image_path: str,
    target_image_path: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 20,
    cfg: float = 1.0,
    seed: int | None = None,
    timeout: int = 300,
) -> list[str]:
    """Klein9b FaceID 换脸，返回输出路径列表"""
    uploaded_face = upload_image(face_image_path)
    uploaded_target = upload_image(target_image_path)
    
    prompt = build_klein_faceid_prompt(
        prompt_text=prompt_text,
        face_image_name=uploaded_face,
        target_image_name=uploaded_target,
        width=width,
        height=height,
        steps=steps,
        cfg=cfg,
        seed=seed
    )
    
    prompt_id = queue_prompt(prompt)
    history = poll_history(prompt_id, timeout=timeout)
    images = get_output_images(history)
    return [get_image_path(img) for img in images]


if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) or "a cute cat"
    print(f"Generating: {text}")
    paths = txt2img(text)
    for p in paths:
        print(f"Output: {p}")




