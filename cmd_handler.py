"""
ComfyUI 指令处理器 - 纯机械化，不经过 AI 模型
"""
import sys, os, re, json, urllib.request, urllib.parse

# 强制 UTF-8 编码，避免 Windows GBK 编码问题
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_runner


def has_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def compress_prompt(text, max_chars=380):
    """压缩过长的提示词，保留核心要素"""
    if len(text) <= max_chars:
        return text, False
    
    print(f"[COMPRESS] Starting compression: {len(text)} chars", flush=True)
    
    # 如果超过 1000 字符，先截断再压缩（避免 Ollama 处理时间过长）
    if len(text) > 1000:
        print(f"[COMPRESS] Text too long, pre-truncating to 800 chars", flush=True)
        text = text[:800]
    
    try:
        url = "http://127.0.0.1:11434/api/chat"
        payload = {
            "model": "qwen3:8b",
            "messages": [
                {"role": "system", "content": "You are a prompt compression expert. Compress the image generation prompt to under 380 characters while keeping all key visual elements, style, lighting, and composition details. Output ONLY the compressed prompt, no explanations."},
                {"role": "user", "content": text}
            ],
            "stream": False
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
            compressed = result.get("message", {}).get("content", "").strip()
            if compressed and len(compressed) < len(text):
                print(f"[COMPRESS] Success: {len(text)} → {len(compressed)} chars", flush=True)
                return compressed, True
            else:
                print(f"[COMPRESS] No improvement, using truncation", flush=True)
    except Exception as e:
        print(f"[COMPRESS] Failed: {e}, using truncation", flush=True)
    
    # 压缩失败，直接截断
    truncated = text[:max_chars]
    print(f"[COMPRESS] Truncated to {len(truncated)} chars", flush=True)
    return truncated, True


def translate_zh2en(text):
    if not has_chinese(text):
        return text
    try:
        # 使用本地 Ollama Qwen3 翻译
        url = "http://127.0.0.1:11434/api/chat"
        payload = {
            "model": "qwen3:8b",
            "messages": [
                {"role": "system", "content": "You are a professional translator."},
                {"role": "user", "content": f"Translate to English: {text}"}
            ],
            "stream": False
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), 
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read())
            content = result.get("message", {}).get("content", "").strip()
            return content if content else text
    except Exception:
        return text


def parse_args(text):
    opts = {}
    # 先提取引号包裹的参数: --key "value with spaces"
    for m in re.finditer(r'--(\w+)\s+"([^"]*)"', text):
        opts[m.group(1)] = m.group(2)
    text = re.sub(r'--\w+\s+"[^"]*"', '', text)
    # 再提取普通参数: --key value
    for m in re.finditer(r'--(\w+)\s+(\S+)', text):
        if m.group(1) not in opts:
            opts[m.group(1)] = m.group(2)
    prompt = re.sub(r'--\w+\s+\S+', '', text).strip()
    return prompt, opts


def parse_size(s, dw, dh):
    if s and 'x' in s:
        p = s.lower().split('x')
        return int(p[0]), int(p[1])
    return dw, dh


def _r(r, t, p):
    if r["ok"]:
        r["type"] = t
    r["prompt_en"] = p
    return r


def handle(cmd, body, image_path=None, video_path=None):
    cmd = cmd.lower().strip('/')
    raw, opts = parse_args(body)
    en = translate_zh2en(raw) if raw else ""
    
    # 记录翻译结果
    if raw and has_chinese(raw):
        print(f"[TRANSLATE]\nChinese: {raw}\nEnglish: {en}\n", flush=True)
    
    # 自动压缩过长提示词（CLIP 模型限制约 400 字符）
    compressed = False
    if cmd in ("img",) and len(en) > 400:
        en, compressed = compress_prompt(en, max_chars=380)
        if compressed:
            print(f"[INFO] Prompt compressed due to CLIP limit", flush=True)

    if cmd == "img":
        w, h = parse_size(opts.get("size"), 1920, 1080)
        result = _r(comfy_runner.txt2img(en, w, h, int(opts.get("steps", 5))),
                    "image", en)
        # 添加压缩提示
        if compressed and result.get("ok"):
            result["compressed"] = True
        return result



    if cmd == "md":
        w, h = parse_size(opts.get("size"), 1920, 1080)
        # Moody 原生中文，不翻译
        return _r(comfy_runner.moody_txt2img(raw, w, h), "image", raw)

    if cmd == "t2v":
        w, h = parse_size(opts.get("size"), 832, 480)
        steps = int(opts.get("steps", 4))
        return _r(comfy_runner.txt2video(en, w, h,
                  int(opts.get("length", 81)), steps), "video", en)

    if cmd == "i2v":
        if not image_path:
            return {"ok": False, "error": "need image"}
        w, h = parse_size(opts.get("size"), 640, 640)
        steps = int(opts.get("steps", 4))
        return _r(comfy_runner.img2video(en, image_path, w, h,
                  int(opts.get("length", 81)), steps), "video", en)

    if cmd == "id":
        if not image_path:
            return {"ok": False, "error": "need face image (reply to face photo)"}
        # Klein9b FaceID 需要两张图：face_image (回复的图) + target_image (--target 参数)
        target = opts.get("target")
        if not target:
            return {"ok": False, "error": "need --target <target_image_path>"}
        w, h = parse_size(opts.get("size"), 1024, 1024)
        steps = int(opts.get("steps", 20))
        return _r(comfy_runner.klein_faceid(en, image_path, target, w, h, steps),
                  "image", en)



    return {"ok": False, "error": f"unknown cmd: /{cmd}"}
