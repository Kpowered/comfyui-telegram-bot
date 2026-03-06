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





def txt2video(prompt, width=832, height=480, length=81, steps=4, cfg=1.0):
    """文生视频 (Wan2.2 AIO T2V)"""
    try:
        pid = comfyui_api.wan_aio_t2v_submit(
            prompt_text=prompt, width=width, height=height,
            length=length, steps=steps, cfg=cfg)
        r = _poll(pid, timeout=1800)
        if r["status"] == "success":
            return {"ok": True, "path": _sendable(r["paths"][0]),
                    "original": r["paths"][0]}
        return {"ok": False, "error": r.get("message", "unknown")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def img2video(prompt, image_path, width=832, height=480,
              length=81, steps=12, cfg=1.0, high_steps=6,
              audio_prompt=None, norife=False, out_tag="img2video"):
    """图生视频 (Wan2.2 AIO)"""
    try:
        pid = comfyui_api.wan_aio_i2v_submit(
            prompt_text=prompt, image_path=image_path,
            width=width, height=height, length=length,
            steps=steps, cfg=cfg)
        r = _poll(pid, timeout=1800)
        if r["status"] == "success":
            return {"ok": True, "path": _sendable(r["paths"][0]),
                    "original": r["paths"][0]}
        return {"ok": False, "error": r.get("message", "unknown")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def klein_faceid(prompt, face_image_path, target_image_path, 
                 width=1024, height=1024, steps=20, cfg=1.0, seed=None):
    """Klein9b FaceID 换脸"""
    try:
        paths = comfyui_api.klein_faceid(
            prompt_text=prompt, face_image_path=face_image_path,
            target_image_path=target_image_path,
            width=width, height=height, steps=steps, cfg=cfg, seed=seed)
        return {"ok": True, "path": _to_ws(paths[0], "faceid"),
                "original": paths[0]}
    except Exception as e:
        return {"ok": False, "error": str(e)}





def moody_txt2img(prompt, width=640, height=960, seed=None):
    """Moody ZIB+ZIT 双模型文生图"""
    try:
        paths = comfyui_api.moody_zib_zit(
            positive_prompt=prompt, width=width, height=height, seed=seed)
        return {"ok": True, "path": _to_ws(paths[0], "moody"), "original": paths[0]}
    except Exception as e:
        return {"ok": False, "error": str(e)}




