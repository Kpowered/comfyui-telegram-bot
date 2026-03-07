"""ComfyUI Telegram Bot"""
import os, sys, json, time, threading, subprocess, traceback
import urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cmd_handler

# ── 全局锁：防止并发处理 /md 请求 ──
md_lock = threading.Lock()

# ── PID lock: only one instance allowed ──
PIDFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "comfy_bot.pid")

def _acquire_lock():
    if os.path.exists(PIDFILE):
        try:
            old_pid = int(open(PIDFILE).read().strip())
            # check if old process is still alive (Windows)
            import ctypes
            kernel32 = ctypes.windll.kernel32
            h = kernel32.OpenProcess(0x1000, False, old_pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if h:
                kernel32.CloseHandle(h)
                print(f"Another instance running (PID {old_pid}), exiting.", flush=True)
                sys.exit(42)  # special code: another instance alive
        except (ValueError, OSError):
            pass
    with open(PIDFILE, "w") as f:
        f.write(str(os.getpid()))
    import atexit
    atexit.register(lambda: os.path.exists(PIDFILE) and os.remove(PIDFILE))

_acquire_lock()

TOKEN = "8799567575:AAF5ocEo0sg22SAiwXJgQ96TbhCEMlilUvY"
API = f"https://api.telegram.org/bot{TOKEN}"
WS = r"C:\Users\admin\.openclaw\workspace"
PY = r"D:\ComfyUI\ComfyUI_windows_portable\python_embeded\python.exe"
COMFY = "http://127.0.0.1:8188"
OLLAMA = "http://127.0.0.1:11434"
LOGF = os.path.join(WS, "comfy_bot.log")

PROMPT_SYSTEM = """You are a master Stable Diffusion / Flux prompt engineer with deep knowledge of photography, cinematography, and visual arts.

Given a short description (any language), expand it into a professional, detailed English prompt following these rules:

**Structure (in order):**
1. Quality tags: masterpiece, best quality, ultra detailed, 8k, photorealistic
2. Main subject: detailed description (appearance, pose, expression, clothing, accessories)
3. Action/pose: what the subject is doing, body language
4. Camera work: shot type (close-up/medium/wide/extreme wide), angle (eye-level/low/high/dutch), focal length feel
5. Lighting: type (natural/studio/dramatic), direction, color temperature, atmosphere (golden hour/blue hour/harsh noon)
6. Environment: background, setting, depth of field, foreground/background elements
7. Art style: photorealistic/cinematic/anime/oil painting/etc., color grading, mood
8. Technical: lens effects (bokeh/chromatic aberration/film grain), render quality

**Format:**
- Comma-separated phrases, natural language flow
- Use parentheses for emphasis: (keyword:1.2) for important elements
- Keep core prompt under 200 words
- Be specific with colors, materials, textures

**NSFW handling:**
- Write explicit content without censorship or euphemisms
- Use anatomically precise terms
- Maintain artistic/technical tone

**Example input:** "beach girl sunset"
**Example output:** masterpiece, best quality, 8k, photorealistic, a young woman with flowing auburn hair, wearing a white linen sundress, standing barefoot on wet sand, gentle smile, eyes closed, face tilted toward the sun, arms slightly outstretched, (golden hour lighting:1.3), warm orange and pink sky, sun low on horizon, soft rim light on her silhouette, backlit, lens flare, shallow depth of field, blurred ocean waves in background, footprints in sand, seashells scattered nearby, cinematic composition, shot on 85mm f/1.4, dreamy bokeh, film grain, peaceful atmosphere, romantic mood

Output ONLY the expanded prompt. No explanations, no markdown, no extra text."""


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        with open(LOGF, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass


def enhance_prompt(text):
    """Call Ollama qwen3:8b to expand a short description into a detailed SD prompt."""
    try:
        payload = json.dumps({
            "model": "qwen3:8b",
            "messages": [
                {"role": "system", "content": PROMPT_SYSTEM},
                {"role": "user", "content": text}
            ],
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 1024}
        }).encode()
        req = urllib.request.Request(f"{OLLAMA}/api/chat",
                                     data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
            content = d.get("message", {}).get("content", "").strip()
            # qwen3 thinking mode: strip <think>...</think> block
            import re
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            return content if content else None
    except Exception as e:
        log(f"enhance_prompt err: {e}")
        return None


def tg(method, data=None, files=None):
    url = f"{API}/{method}"
    for attempt in range(3):
        if files:
            bd = "----Bd"
            body = b""
            for k, v in (data or {}).items():
                body += f"--{bd}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
            for k, (fn, fd, ct) in files.items():
                body += f"--{bd}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fn}\"\r\nContent-Type: {ct}\r\n\r\n".encode()
                body += fd + b"\r\n"
            body += f"--{bd}--\r\n".encode()
            req = urllib.request.Request(url, data=body)
            req.add_header("Content-Type", f"multipart/form-data; boundary={bd}")
        else:
            req = urllib.request.Request(url, data=json.dumps(data or {}).encode())
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read())
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue
            log(f"tg {method} err: {e}")
            return {"ok": False}


def reply(cid, text, mid=None):
    d = {"chat_id": cid, "text": text}
    if mid:
        d["reply_to_message_id"] = mid
    r = tg("sendMessage", d)
    if r.get("ok"):
        return r["result"]["message_id"]
    return None


def edit_msg(cid, msg_id, text):
    try:
        return tg("editMessageText", {"chat_id": cid, "message_id": msg_id, "text": text})
    except Exception as e:
        log(f"edit_msg failed: {e}")
        return None


def send_photo(cid, path, cap="", mid=None):
    d = {"chat_id": str(cid)}
    if cap:
        d["caption"] = cap[:1024]
    if mid:
        d["reply_to_message_id"] = str(mid)
    with open(path, "rb") as f:
        return tg("sendPhoto", d, {"photo": (os.path.basename(path), f.read(), "image/png")})


def send_video(cid, path, cap="", mid=None):
    d = {"chat_id": str(cid)}
    if cap:
        d["caption"] = cap[:1024]
    if mid:
        d["reply_to_message_id"] = str(mid)
    with open(path, "rb") as f:
        return tg("sendVideo", d, {"video": (os.path.basename(path), f.read(), "video/mp4")})


def dl_file(file_id):
    r = tg("getFile", {"file_id": file_id})
    if not r.get("ok"):
        return None
    fp = r["result"]["file_path"]
    ext = ".mp4" if "video" in fp or fp.endswith(".mp4") else ".jpg"
    local = os.path.join(WS, f"tg_{file_id[:8]}{ext}")
    urllib.request.urlretrieve(f"https://api.telegram.org/file/bot{TOKEN}/{fp}", local)
    return local


COMFY_CMD = [
    r"D:\ComfyUI\ComfyUI_windows_portable\python_embeded\python.exe",
    "-s", r"D:\ComfyUI\ComfyUI_windows_portable\ComfyUI\main.py",
    "--listen", "127.0.0.1", "--port", "8188",
    "--output-directory", r"D:\ComfyUI\ComfyUI_windows_portable\ComfyUI\output"
]
_comfy_restarting = False


def alive():
    try:
        return urllib.request.urlopen(f"{COMFY}/system_stats", timeout=10).status == 200
    except:
        return False


def cleanup_stuck_processes():
    """清理运行超过15分钟的 cmd_handler 子进程"""
    try:
        import psutil
        killed = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            try:
                cmdline = proc.info.get('cmdline') or []
                if any('cmd_handler' in str(arg) for arg in cmdline):
                    runtime = time.time() - proc.info['create_time']
                    if runtime > 900:  # 15分钟
                        log(f"Killing stuck process PID {proc.info['pid']} (runtime: {runtime:.0f}s)")
                        proc.kill()
                        killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if killed > 0:
            log(f"Cleaned up {killed} stuck process(es)")
    except ImportError:
        # psutil 不可用，使用 Windows 原生方法
        try:
            import ctypes
            for proc_id in range(1, 65536):
                try:
                    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, proc_id)
                    if handle:
                        ctypes.windll.kernel32.CloseHandle(handle)
                except:
                    pass
        except:
            pass
    except Exception as e:
        log(f"Cleanup error: {e}")


def ensure_comfy():
    """Check ComfyUI, auto-restart if down. Returns True if alive."""
    global _comfy_restarting
    if alive():
        _comfy_restarting = False
        return True
    if _comfy_restarting:
        return False
    _comfy_restarting = True
    log("ComfyUI offline, auto-restarting...")
    try:
        subprocess.Popen(COMFY_CMD,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=0x00000008)  # DETACHED_PROCESS
    except Exception as e:
        log(f"ComfyUI restart failed: {e}")
        _comfy_restarting = False
        return False
    # wait up to 60s for it to come online
    for _ in range(12):
        time.sleep(5)
        if alive():
            log("ComfyUI restarted OK")
            _comfy_restarting = False
            return True
    log("ComfyUI restart timeout")
    _comfy_restarting = False
    return False


def comfy_progress():
    """查询 ComfyUI 当前执行进度，返回 (current, total) 或 None"""
    try:
        with urllib.request.urlopen(f"{COMFY}/prompt", timeout=3) as r:
            d = json.loads(r.read())
            info = d.get("exec_info", {})
            cur = info.get("current", {})
            if cur.get("node"):
                return cur.get("progress", {}).get("value"), cur.get("progress", {}).get("max")
    except:
        pass
    return None, None


def run_cmd(cmd, body, img=None, vid=None, progress_cb=None):
    script = f"""
import sys, json
sys.path.insert(0, r'{WS}')
import cmd_handler
r = cmd_handler.handle({repr(cmd)}, {repr(body)}, image_path={repr(img)}, video_path={repr(vid)})
print(json.dumps(r, ensure_ascii=False))
sys.stdout.flush()
"""
    proc = subprocess.Popen([PY, "-u", "-c", script],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, bufsize=1)
    t0 = time.time()
    last_update = 0
    timeout = 600  # 10分钟超时
    
    # 使用线程读取输出，避免死锁
    stdout_lines = []
    stderr_lines = []
    
    def read_stdout():
        for line in proc.stdout:
            stdout_lines.append(line)
    
    def read_stderr():
        for line in proc.stderr:
            stderr_lines.append(line)
    
    import threading
    t_out = threading.Thread(target=read_stdout, daemon=True)
    t_err = threading.Thread(target=read_stderr, daemon=True)
    t_out.start()
    t_err.start()
    
    while proc.poll() is None:
        elapsed = time.time() - t0
        if elapsed > timeout:
            log(f"Process timeout after {timeout}s, killing PID {proc.pid}")
            try:
                proc.kill()
                proc.wait(timeout=5)
            except:
                pass
            return {"ok": False, "error": f"timeout {timeout}s"}
        if progress_cb and elapsed - last_update >= 15:
            last_update = elapsed
            progress_cb(elapsed)
        time.sleep(1)
    
    # 等待输出读取完成
    t_out.join(timeout=5)
    t_err.join(timeout=5)
    
    stdout = ''.join(stdout_lines)
    stderr = ''.join(stderr_lines)
    
    if proc.returncode != 0:
        return {"ok": False, "error": stderr[-500:] if stderr else "unknown"}
    lines = [l for l in stdout.strip().split("\n") if l.strip()]
    if not lines:
        return {"ok": False, "error": "no output"}
    return json.loads(lines[-1])


HELP_MAIN = (
    "🎨 图先生 ComfyUI Bot\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "🖼 文生图\n"
    "  /img — RedCraft DX3 文生图\n"
    "  /md — Moody ZIB+ZIT 文生图\n\n"
    "🎬 视频\n"
    "  /t2v — Wan2.2 AIO 文生视频\n"
    "  /i2v — Wan2.2 AIO 图生视频\n\n"
    "✨ AI提示词\n"
    "  /pm — 扩写详细英文prompt\n"
    "  /en — 中文翻译英文（简单直译）\n"
    "  任意出图指令加 --xx 自动扩写\n\n"
    "⚙️ 系统\n"
    "  /restart — 重启 Bot\n\n"
    "输入 /help <指令> 查看详细用法\n"
    "例: /help img"
)

HELP_DETAIL = {
    "pm": (
        "✨ /pm <描述>\n"
        "AI 扩写提示词（Qwen3 8B 本地模型）\n"
        "输入简短中文描述，返回详细英文 SD prompt\n\n"
        "示例:\n"
        "/pm 海边的女孩\n"
        "/pm 赛博朋克城市夜景"
    ),
    "en": (
        "🔄 /en <中文文本>\n"
        "简单直译中文到英文（Qwen3 8B 本地模型）\n"
        "不扩写，只做准确翻译\n\n"
        "示例:\n"
        "/en 图中女子轻轻晃动，回头微笑\n"
        "/en 一位穿着红色连衣裙的女孩"
    ),
    "img": (
        "📸 /img <prompt>\n"
        "RedCraft DX3 文生图，中文自动翻译英文\n\n"
        "参数:\n"
        "  --size WxH (默认 1024x1024)\n"
        "  --steps N (默认 5)\n\n"
        "示例:\n"
        "/img a girl in garden --size 832x1216"
    ),
    "zimg": (
        "📸 /zimg <prompt>\n"
        "Z-Image-Turbo 文生图，原生中文\n\n"
        "参数:\n"
        "  --size WxH (默认 1024x1024)\n"
        "  --steps N (默认 8)\n\n"
        "示例:\n"
        "/zimg 海边日落的女孩 --steps 12"
    ),
    "moody": (
        "📸 /moody <prompt>\n"
        "Moody ZIB+ZIT 双模型，原生中文，高画质\n\n"
        "参数:\n"
        "  --size WxH (默认 640x960 竖图)\n"
        "  步数固定 ZIB=17 + ZIT=12 不可调\n\n"
        "示例:\n"
        "/moody 森林中的精灵少女 --size 768x1024"
    ),
    "faceid": (
        "🖼 /faceid <prompt>\n"
        "PuLID 脸部一致性生图，回复人脸照片使用\n"
        "建议用英文 prompt\n\n"
        "参数:\n"
        "  --size WxH (默认 1024x1024)\n"
        "  --steps N (默认 20)\n"
        "  --weight F (默认 0.9，脸部权重)\n\n"
        "示例:\n"
        "/faceid nude woman on beach --weight 0.85"
    ),
    "i2v": (
        "🎬 /i2v <prompt>\n"
        "图生视频，回复图片使用，~5-8min\n\n"
        "参数:\n"
        "  --size WxH (默认 832x480)\n"
        "  --steps N (默认 12)\n"
        "  --length N (帧数，默认 81 ≈5秒)\n"
        '  --audio "描述" (AI配音，如 "wind blowing")\n\n'
        "示例:\n"
        "/i2v walking forward --steps 16 --length 121\n"
        '/i2v girl dancing --audio "upbeat music, footsteps"'
    ),
    "t2v": (
        "🎬 /t2v <prompt>\n"
        "文生图→视频一条龙，~8-10min\n\n"
        "参数:\n"
        "  --size WxH (默认 832x480)\n"
        "  --steps N (默认 12)\n"
        "  --length N (帧数，默认 81)\n"
        '  --audio "描述" (AI配音)\n\n'
        "示例:\n"
        '/t2v sunset beach girl dancing --audio "waves crashing"'
    ),
    "upscale": (
        "🎬 /upscale\n"
        "视频超分到1080p，回复视频使用，~5-10min\n\n"
        "参数:\n"
        "  --res N (分辨率，默认 1080)\n\n"
        "示例:\n"
        "回复一个视频，输入 /upscale"
    ),
    "pipeline": (
        "🎬 /pipeline <prompt>\n"
        "全管线：文生图→视频→超分，~15-20min\n\n"
        "参数:\n"
        "  --size WxH (默认 832x480)\n"
        "  --steps N (默认 12)\n"
        "  --length N (帧数，默认 81)\n"
        "  --res N (超分分辨率，默认 1080)\n"
        '  --audio "描述" (AI配音)\n\n'
        "示例:\n"
        '/pipeline girl walking on beach --audio "footsteps on sand"'
    ),
}

HELP = HELP_MAIN

TIPS = {
    "img": "🎨 Generating...",
    "zimg": "🎨 Z-Image-Turbo generating...",
    "moody": "🎨 Moody ZIB+ZIT dual-model generating (~2-3min)...",
    "zface": "🎨 Z-Image face reference generating...",
    "faceid": "🎨 PuLID FaceID generating (~30s)...",
    "i2v": "🎬 img2video ~5-10min...",
    "i2v2": "🎬 i2v2 (two-stage) ~10-15min...",
    "t2v": "🎬 txt2video ~8-10min...",
    "upscale": "🎬 Upscaling ~5-10min...",
    "pipeline": "🎬 Full pipeline ~15-20min...",
    "md": "🎨 Moody generating...",
}


def get_photo(msg):
    if msg.get("photo"):
        return msg["photo"][-1]["file_id"]
    r = msg.get("reply_to_message", {})
    if r.get("photo"):
        return r["photo"][-1]["file_id"]
    return None


def get_video(msg):
    r = msg.get("reply_to_message", {})
    return r["video"]["file_id"] if r.get("video") else None


def send_result(cid, mid, res):
    if not res.get("ok"):
        reply(cid, "Error: " + res.get("error", "unknown"), mid)
        return
    cap = res.get("prompt_en", "")[:1024]
    
    # 添加压缩提示
    if res.get("compressed"):
        cap = "⚠️ 提示词过长，已自动压缩总结\n\n" + cap
    
    if res.get("type") == "video":
        send_video(cid, res["path"], cap, mid)
    else:
        send_photo(cid, res["path"], cap, mid)


def handle(msg):
    cid = msg["chat"]["id"]
    mid = msg["message_id"]
    text = (msg.get("text") or "").strip()
    if not text or not text.startswith("/"):
        return

    parts = text.split(None, 1)
    cmd = parts[0].lower().split("@")[0].lstrip("/")
    body = parts[1] if len(parts) > 1 else ""

    log(f"CMD /{cmd} body={body[:50]} chat={cid}")

    if cmd in ("help", "start"):
        if body.strip() in HELP_DETAIL:
            reply(cid, HELP_DETAIL[body.strip()], mid)
        else:
            reply(cid, HELP_MAIN, mid)
        return

    # /pm — AI prompt enhancement only
    if cmd == "pm":
        if not body.strip():
            reply(cid, "Usage: /pm <描述>", mid)
            return
        tip_id = reply(cid, "✨ AI 扩写中...", mid)
        result = enhance_prompt(body.strip())
        if result:
            edit_msg(cid, tip_id, f"✨ Enhanced Prompt:\n\n{result}")
        else:
            edit_msg(cid, tip_id, "❌ 扩写失败，Ollama 可能未启动")
        return

    if cmd == "en":
        if not body.strip():
            reply(cid, "Usage: /en <中文文本>", mid)
            return
        tip_id = reply(cid, "🔄 翻译中...", mid)
        result = cmd_handler.translate_zh2en(body.strip())
        if result:
            edit_msg(cid, tip_id, f"🔄 Translation:\n\n{result}")
        else:
            edit_msg(cid, tip_id, "❌ 翻译失败")
        return

    if cmd == "restart":
        reply(cid, "🔄 重启 Bot 中...", mid)
        log("User requested restart")
        sys.exit(0)
        return

    # allow new commands even if not in TIPS (fallback tip)
    if cmd not in TIPS:
        # still proceed if cmd is supported by cmd_handler; show a generic tip
        if cmd not in ("i2v2",):
            return
        TIPS[cmd] = "i2v2 (two-stage) ~10-15min..."
    if not ensure_comfy():
        reply(cid, "ComfyUI 正在重启，请稍后再试...", mid)
        return

    img = vid = None
    if cmd in ("i2v", "i2v2", "zface", "faceid"):
        fid = get_photo(msg)
        if not fid:
            log(f"No photo found for {cmd}")
            reply(cid, f"Reply to a photo with /{cmd} <prompt>", mid)
            return
        log(f"Downloading photo {fid[:16]}...")
        img = dl_file(fid)
        log(f"Photo downloaded: {img}")
    if cmd == "upscale":
        fid = get_video(msg)
        if not fid:
            reply(cid, "Reply to a video with /upscale", mid)
            return
        vid = dl_file(fid)
    if cmd in ("img", "zimg", "moody", "zface", "faceid", "t2v", "pipeline") and not body:
        reply(cid, f"Usage: /{cmd} <prompt>", mid)
        return

    # --xx: AI prompt expansion before generation
    if "--xx" in body:
        body = body.replace("--xx", "").strip()
        reply(cid, "✨ AI 扩写 prompt 中...", mid)
        enhanced = enhance_prompt(body)
        if enhanced:
            body = enhanced
            log(f"Enhanced prompt: {body[:80]}")
        else:
            log("enhance failed, using original prompt")

    tip_id = reply(cid, TIPS[cmd], mid)

    def on_progress(elapsed):
        mins = int(elapsed) // 60
        secs = int(elapsed) % 60
        bar = TIPS[cmd].split("...")[0]
        edit_msg(cid, tip_id, f"{bar}... ⏱ {mins}:{secs:02d}")

    try:
        # /md 使用锁防止并发
        if cmd == "md":
            if not md_lock.acquire(blocking=False):
                reply(cid, "⏳ 另一个 /md 任务正在执行，请稍后再试", mid)
                return
            try:
                r = run_cmd(cmd, body, img, vid, progress_cb=on_progress)
            finally:
                md_lock.release()
        else:
            r = run_cmd(cmd, body, img, vid, progress_cb=on_progress)
        
        if tip_id:
            edit_msg(cid, tip_id, "✅ Done" if r.get("ok") else f"❌ {r.get('error','unknown')[:200]}")
        send_result(cid, mid, r)
    except Exception as e:
        log(f"handle err: {e}")
        reply(cid, f"Error: {e}", mid)


def main():
    log("Starting bot...")
    offset = None
    seen = set()  # 去重：已处理的 message_id
    last_cleanup = time.time()
    
    r = tg("getUpdates", {"offset": -1, "timeout": 0})
    if r.get("ok") and r["result"]:
        offset = r["result"][-1]["update_id"] + 1
        log(f"Skip old, offset={offset}")
    log("Polling...")
    
    # 启动通知
    try:
        result = tg("sendMessage", {"chat_id": "607333500", "text": "✅ Bot 已启动"})
        if result.get("ok"):
            log("Startup notification sent")
        else:
            log(f"Startup notification failed: {result}")
    except Exception as e:
        log(f"Startup notification error: {e}")

    while True:
        try:
            # 每5分钟清理一次卡住的子进程
            if time.time() - last_cleanup > 300:
                cleanup_stuck_processes()
                last_cleanup = time.time()
            
            p = {"timeout": 10}
            if offset:
                p["offset"] = offset
            r = tg("getUpdates", p)
            if not r.get("ok"):
                log(f"getUpdates fail")
                time.sleep(5)
                continue
            for u in r["result"]:
                offset = u["update_id"] + 1
                msg = u.get("message")
                if not msg:
                    continue
                mid = msg["message_id"]
                if mid in seen:
                    continue
                seen.add(mid)
                if len(seen) > 500:
                    seen.clear()
                log(f"MSG: {(msg.get('text') or '')[:60]} from {msg.get('from',{}).get('username','?')}")
                threading.Thread(target=handle, args=(msg,), daemon=True).start()
        except Exception as e:
            log(f"Poll err: {e}")
            time.sleep(5)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FATAL: {e}\n{traceback.format_exc()}")
