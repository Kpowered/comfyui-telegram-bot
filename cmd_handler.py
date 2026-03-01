"""
ComfyUI 指令处理器 - 纯机械化，不经过 AI 模型
"""
import sys, os, re, json, urllib.request, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_runner


def has_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def translate_zh2en(text):
    if not has_chinese(text):
        return text
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = urllib.parse.urlencode({
            "client": "gtx", "sl": "zh-CN", "tl": "en",
            "dt": "t", "q": text
        })
        req = urllib.request.Request(f"{url}?{params}")
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            return "".join(seg[0] for seg in data[0] if seg[0])
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

    if cmd == "img":
        w, h = parse_size(opts.get("size"), 1024, 1024)
        return _r(comfy_runner.txt2img(en, w, h, int(opts.get("steps", 5))),
                  "image", en)

    if cmd == "zimg":
        w, h = parse_size(opts.get("size"), 1024, 1024)
        # Z-Image-Turbo 原生中文，不翻译
        return _r(comfy_runner.zimg_txt2img(raw, w, h, int(opts.get("steps", 8))),
                  "image", raw)

    if cmd == "zface":
        if not image_path:
            return {"ok": False, "error": "need face image (reply photo)"}
        w, h = parse_size(opts.get("size"), 1024, 1024)
        return _r(comfy_runner.zimg_faceref(raw, image_path, w, h,
                  int(opts.get("steps", 8))), "image", raw)

    if cmd == "faceid":
        if not image_path:
            return {"ok": False, "error": "need face image (reply photo)"}
        w, h = parse_size(opts.get("size"), 640, 960)
        return _r(comfy_runner.pulid_faceid(raw, image_path, w, h,
                  int(opts.get("steps", 20)),
                  float(opts.get("weight", 1.0))),
                  "image", raw)

    if cmd == "moody":
        w, h = parse_size(opts.get("size"), 640, 960)
        # Moody 原生中文，不翻译
        return _r(comfy_runner.moody_txt2img(raw, w, h), "image", raw)

    if cmd == "i2v":
        if not image_path:
            return {"ok": False, "error": "need image"}
        # 默认按竖图（A：人像）更稳：576x1024，默认 5 秒（source_fps=16 → length=80）
        w, h = parse_size(opts.get("size"), 576, 1024)
        steps = int(opts.get("steps", 10))
        audio = opts.get("audio")
        return _r(comfy_runner.img2video(en, image_path, w, h,
                  int(opts.get("length", 80)), steps,
                  high_steps=steps // 2,
                  audio_prompt=audio), "video", en)

    if cmd == "i2v2":
        if not image_path:
            return {"ok": False, "error": "need image"}
        w, h = parse_size(opts.get("size"), 576, 1024)
        steps = int(opts.get("steps", 10))
        # A 段 / B 段 prompt：用 ||| 分隔
        if "|||" not in en:
            return {"ok": False, "error": "need two prompts separated by |||"}
        a, b = [x.strip() for x in en.split("|||", 1)]
        len_a = int(opts.get("len_a", 48))
        len_b = int(opts.get("len_b", 32))
        fps = int(opts.get("fps", 25))
        return _r(comfy_runner.i2v_two_stage(a, b, image_path, w, h,
                  length_a=len_a, length_b=len_b,
                  steps=steps, high_steps=steps // 2,
                  fps=fps), "video", en)

    if cmd == "upscale":
        if not video_path:
            return {"ok": False, "error": "need video path"}
        return _r(comfy_runner.upscale(video_path,
                  resolution=int(opts.get("res", 1080))), "video", "")

    if cmd == "pipeline":
        w, h = parse_size(opts.get("size"), 832, 480)
        steps = int(opts.get("steps", 12))
        audio = opts.get("audio")
        return _r(comfy_runner.pipeline(en, w, h,
                  int(opts.get("length", 81)), steps,
                  high_steps=steps // 2,
                  resolution=int(opts.get("res", 1080)),
                  audio_prompt=audio), "video", en)

    return {"ok": False, "error": f"unknown cmd: /{cmd}"}
