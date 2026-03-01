"""
ComfyUI 指令执行器 - 统一入口
"""
import sys, os, time, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfyui_api
from ffmpeg_utils import concat_reencode

WORKSPACE = r"C:\Users\admin\.openclaw\workspace"
FFMPEG = (r"D:\ComfyUI\ComfyUI_windows_portable\python_embeded"
          r"\Lib\site-packages\imageio_ffmpeg\binaries"
          r"\ffmpeg-win-x86_64-v7.1.exe")
MAX_TG = 15 * 1024 * 1024


def _compress(src, dst, crf=28):
    import subprocess
    subprocess.run([FFMPEG, "-i", src, "-c:v", "libx264",
                    "-crf", str(crf), "-preset", "fast", "-y", dst],
                   capture_output=True, check=True)


def _to_ws(src, tag="out"):
    ext = os.path.splitext(src)[1]
    dst = os.path.join(WORKSPACE, f"{tag}_{int(time.time())}{ext}")
    shutil.copy2(src, dst)
    return dst


def _sendable(video_path):
    ws = _to_ws(video_path, "video")
    if os.path.getsize(ws) > MAX_TG:
        c = ws.replace(".mp4", "_c.mp4")
        _compress(ws, c)
        os.remove(ws)
        return c
    return ws


def _poll(pid, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = comfyui_api.check_video_status(pid)
        if s["status"] in ("success", "error"):
            return s
        time.sleep(10)
    return {"status": "error", "message": f"timeout {timeout}s"}


# ========== 管线 ==========

def txt2img(prompt, width=1024, height=1024, steps=5):
    """文生图(RedCraft)，返回 {ok, path, original} 或 {ok, error}"""
    try:
        paths = comfyui_api.txt2img(prompt, width=width, height=height, steps=steps)
        return {"ok": True, "path": _to_ws(paths[0], "img"), "original": paths[0]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def zimg_txt2img(prompt, width=1024, height=1024, steps=8):
    """Z-Image-Turbo 文生图（原生中文），返回 {ok, path, original}"""
    try:
        paths = comfyui_api.zimage_txt2img(prompt, width=width, height=height, steps=steps)
        return {"ok": True, "path": _to_ws(paths[0], "zimg"), "original": paths[0]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def zimg_faceref(prompt, face_image_path, width=1024, height=1024, steps=8):
    """Z-Image-Turbo 参考脸文生图（保持脸部一致性）"""
    try:
        paths = comfyui_api.zimage_faceref(
            prompt, face_image_path, width=width, height=height, steps=steps)
        return {"ok": True, "path": _to_ws(paths[0], "zface"), "original": paths[0]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def img2video(prompt, image_path, width=832, height=480,
              length=81, steps=12, cfg=1.0, high_steps=6,
              audio_prompt=None, norife=False, out_tag="img2video"):
    """图生视频

    - norife=True: 绕过 RIFE 插帧（大动作段避免重影）
    - out_tag: 输出目录前缀 (Video/<out_tag>)
    """
    try:
        pid = comfyui_api.img2video_submit(
            prompt_text=prompt, image_path=image_path,
            width=width, height=height, length=length,
            steps=steps, cfg=cfg, high_steps=high_steps,
            audio_prompt=audio_prompt,
            norife=norife,
            out_tag=out_tag)
        r = _poll(pid, timeout=600)
        if r["status"] == "success":
            return {"ok": True, "path": _sendable(r["paths"][0]),
                    "original": r["paths"][0]}
        return {"ok": False, "error": r.get("message", "unknown")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def i2v_two_stage(
    prompt_a, prompt_b,
    image_path,
    width=576, height=1024,
    length_a=48, length_b=32,
    steps=10, cfg=1.15, high_steps=5,
    fps=25,
):
    """两段 I2V：A(大动作, no RIFE) + B(小动作, 可RIFE) -> ffmpeg 拼接并统一 CFR fps."""
    ra = img2video(prompt_a, image_path, width, height,
                   length=length_a, steps=steps, cfg=cfg, high_steps=high_steps,
                   norife=True, out_tag="i2v_a")
    if not ra.get("ok"):
        return ra

    rb = img2video(prompt_b, image_path, width, height,
                   length=length_b, steps=steps, cfg=cfg, high_steps=high_steps,
                   norife=False, out_tag="i2v_b")
    if not rb.get("ok"):
        return rb

    out = os.path.join(WORKSPACE, f"i2v_{int(time.time())}.mp4")
    concat_reencode(FFMPEG, ra["original"], rb["original"], out, fps=fps, crf=16)
    return {"ok": True, "path": _sendable(out), "original": out}


def upscale(video_path, resolution=1080, fps=25.0):
    """视频超分 (SeedVR2)"""
    try:
        pid = comfyui_api.video_upscale_submit(
            video_path=video_path, resolution=resolution, fps=fps)
        r = _poll(pid, timeout=3000)
        if r["status"] == "success":
            return {"ok": True, "path": _sendable(r["paths"][0]),
                    "original": r["paths"][0]}
        return {"ok": False, "error": r.get("message", "unknown")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def video(prompt, width=832, height=480, length=81,
          steps=12, cfg=1.0, high_steps=6, audio_prompt=None):
    """一条龙：文生图 → 图生视频"""
    img = txt2img(prompt, width=width, height=height, steps=5)
    if not img["ok"]:
        return img
    return img2video(prompt, img["original"], width=width, height=height,
                     length=length, steps=steps, cfg=cfg, high_steps=high_steps,
                     audio_prompt=audio_prompt)


def pipeline(prompt, width=832, height=480, length=81,
             steps=12, cfg=1.0, high_steps=6, resolution=1080,
             audio_prompt=None):
    """全管线：文生图 → 图生视频 → 超分"""
    vid = video(prompt, width, height, length, steps, cfg, high_steps,
                audio_prompt=audio_prompt)
    if not vid["ok"]:
        return vid
    return upscale(vid["original"], resolution=resolution)


def moody_txt2img(prompt, width=640, height=960, seed=None):
    """Moody ZIB+ZIT 双模型文生图"""
    try:
        paths = comfyui_api.moody_zib_zit(
            positive_prompt=prompt, width=width, height=height, seed=seed)
        return {"ok": True, "path": _to_ws(paths[0], "moody"), "original": paths[0]}
    except Exception as e:
        return {"ok": False, "error": str(e)}



def pulid_faceid(prompt, face_image_path, width=640, height=960,
                 steps=20, weight=1.0):
    """PuLID FaceID 图片生成（保持脸部一致性）"""
    try:
        paths = comfyui_api.pulid_faceid(
            prompt_text=prompt, face_image_path=face_image_path,
            width=width, height=height, steps=steps, weight=weight)
        return {"ok": True, "path": _to_ws(paths[0], "faceid"),
                "original": paths[0]}
    except Exception as e:
        return {"ok": False, "error": str(e)}
