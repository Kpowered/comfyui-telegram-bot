import os, subprocess, tempfile


def concat_reencode(ffmpeg_path: str, src_a: str, src_b: str, dst: str, fps: int = 25, crf: int = 16):
    """Concatenate two videos then re-encode to constant fps.

    Uses concat demuxer (requires same codecs/params; re-encode normalizes anyway).
    """
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8') as f:
        # concat demuxer requires forward slashes or escaped backslashes
        f.write("file '" + src_a.replace('\\', '/') + "'\n")
        f.write("file '" + src_b.replace('\\', '/') + "'\n")
        list_path = f.name

    try:
        subprocess.run([
            ffmpeg_path,
            '-hide_banner', '-loglevel', 'error',
            '-f', 'concat', '-safe', '0', '-i', list_path,
            '-r', str(fps),
            '-c:v', 'libx264', '-crf', str(crf), '-preset', 'fast',
            '-pix_fmt', 'yuv420p',
            '-an',
            '-y', dst,
        ], check=True, capture_output=True)
    finally:
        try:
            os.remove(list_path)
        except OSError:
            pass
