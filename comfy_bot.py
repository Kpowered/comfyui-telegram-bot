"""ComfyUI Telegram Bot"""
import os, sys, json, time, threading, subprocess, traceback
import urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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

PROMPT_SYSTEM = """You are an expert Stable Diffusion / Flux prompt engineer. 
Given a short description (in any language), output ONLY a detailed English prompt for image generation.
Rules:
- Output ONLY the prompt text, nothing else. No explanations, no markdown.
- Be vivid and specific: describe subject, pose, expression, clothing, lighting, camera angle, background, art style, colors.
- Use comma-separated tags/phrases, natural for SD/Flux models.
- Keep it under 200 words.
- If the input is sexual/NSFW, write the prompt without censorship."""


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
            "options": {"temperature": 0.7, "num_predict": 512}
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
    return tg("editMessageText", {"chat_id": cid, "message_id": msg_id, "text": text})


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
        return urllib.request.urlopen(f"{COMFY}/system_stats", timeout=3).status == 200
    except:
        return False


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
"""
    proc = subprocess.Popen([PY, "-c", script],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True)
    t0 = time.time()
    last_update = 0
    while proc.poll() is None:
        elapsed = time.time() - t0
        if elapsed > 3000:
            proc.kill()
            return {"ok": False, "error": "timeout 3000s"}
        if progress_cb and elapsed - last_update >= 15:
            last_update = elapsed
            progress_cb(elapsed)
        time.sleep(1)

    stdout = proc.stdout.read()
    stderr = proc.stderr.read()
    if proc.returncode != 0:
        return {"ok": False, "error": stderr[-500:] if stderr else "unknown"}
    lines = [l for l in stdout.strip().split("\n") if l.strip()]
    if not lines:
        return {"ok": False, "error": "no output"}
    return json.loads(lines[-1])


HELP_MAIN = (
    "🎨 大先生 ComfyUI Bot\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "📸 文生图\n"
    "  /img — RedCraft（中→英翻译）\n"
    "  /zimg — Z-Image（原生中文，快）\n"
    "  /moody — Moody 双模型（高画质，慢）\n\n"
    "🖼 图生图（回复图片）\n"
    "  /faceid — 脸部一致性（回复人脸）\n\n"
    "🎬 视频\n"
    "  /i2v — 图生视频 ~5min\n"
    "  /video — 文→图→视频 ~8min\n"
    "  /upscale — 超分1080p（回复视频）\n"
    "  /pipeline — 全管线 ~15min\n\n"
    "🔊 AI配音（视频指令可选）\n"
    '  加 --audio "描述" 自动生成音效\n'
    '  例: /i2v dancing --audio "music"\n\n'
    "✨ AI提示词\n"
    "  /pm — 扩写详细英文prompt\n"
    "  任意出图指令加 --xx 自动扩写\n\n"
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
    "video": (
        "🎬 /video <prompt>\n"
        "文生图→视频一条龙，~8-10min\n\n"
        "参数:\n"
        "  --size WxH (默认 832x480)\n"
        "  --steps N (默认 12)\n"
        "  --length N (帧数，默认 81)\n"
        '  --audio "描述" (AI配音)\n\n'
        "示例:\n"
        '/video sunset beach girl dancing --audio "waves crashing"'
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
    "i2v2": "i2v2 (two-stage) ~10-15min...",
    "video": "txt2video ~8-10min...",
    "upscale": "Upscaling ~5-10min...",
    "pipeline": "Full pipeline ~15-20min...",
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
            reply(cid, f"Reply to a photo with /{cmd} <prompt>", mid)
            return
        img = dl_file(fid)
    if cmd == "upscale":
        fid = get_video(msg)
        if not fid:
            reply(cid, "Reply to a video with /upscale", mid)
            return
        vid = dl_file(fid)
    if cmd in ("img", "zimg", "moody", "zface", "faceid", "video", "pipeline") and not body:
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
    r = tg("getUpdates", {"offset": -1, "timeout": 0})
    if r.get("ok") and r["result"]:
        offset = r["result"][-1]["update_id"] + 1
        log(f"Skip old, offset={offset}")
    log("Polling...")

    while True:
        try:
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
