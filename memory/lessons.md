# 踩坑教训

## 🔴 致命级

### [2026-03-07] ComfyUI 显存不足导致崩溃
**问题**：原始 Moody 工作流包含 ZIB + ZIT + UltimateSDUpscale 三阶段，RTX 3090 24GB 显存不够

**根本原因**：
- 基础分辨率 640x960
- Latent Upscale 1.7x → 1088x1632
- UltimateSDUpscale 再放大 → 显存爆炸

**解决方案**：
- 去掉所有 upscale 步骤
- 直接生成目标分辨率（1920x1080）
- ZIB（9 steps, end=7）→ ZIT（9 steps, start=4）
- 显存占用降至 12-15GB（安全范围）

**教训**：
- 不要盲目堆叠 upscale 步骤
- 直接生成目标分辨率比多次放大更稳定
- 显存不足时优先简化工作流，而非降低分辨率

---

### [2026-03-07] Telegram Bot 子进程 IPC 会导致“已出图但 no output / 一直 Generating”
**问题**：ComfyUI 后台已经成功出图，workspace 里也已经复制出了 `img_*.png` / `moody_*.png`，但 Telegram Bot 仍然返回 `Error: no output`，或者永远卡在 `Generating`。

**根本原因**：
- 旧架构使用 `subprocess.Popen([PY, "-u", "-c", script], ...)` 启动子进程执行 `cmd_handler.handle()`
- 再依赖 stdout/stderr + JSON 标记把结果传回主进程
- 在 Windows 上，这条链路会被 stdout/stderr 缓冲、编码、调试输出污染、子进程退出时机等问题放大
- 结果就是：ComfyUI 已出图，但 Bot 拿不到结果，误报 `no output`

**错误修复路线（浪费时间）**：
- 给子进程加 `-u`
- 加线程异步读 stdout/stderr
- 加 `communicate()`
- 用 `__RESULT_START__` / `__RESULT_END__` 提取 JSON
- 继续往 stdout 打调试日志

这些都只是补丁，不是根治。

**最终解决方案（正确）**：
- 彻底删除 `python -c` 子进程 + stdout/JSON 回传链路
- 在 `comfy_bot.py` 主进程内直接调用 `cmd_handler.handle()`
- 结果直接以 Python dict 返回，不再走 IPC
- 同时静音 `cmd_handler.py` / `comfyui_api.py` 的调试 `print`

**教训**：
- 如果出现“ComfyUI 已出图，但 Bot 还在 Generating / no output”，第一怀疑对象应该是 **Bot 的进程间通信**，不是 ComfyUI
- Windows 下用 stdout/stderr 给主进程回传业务结果，极不稳
- **业务结果不要走 stdout 管道，能进程内直调就别起子进程**

---

### [2026-03-07] 长中文 `/img` 提示词先整段翻译会卡死在翻译阶段
**问题**：长 `/img` 提示词时，Bot 显示 `Generating` 很久，但 ComfyUI 队列是空的，根本没有任务提交。

**根本原因**：
- 原顺序是：`全文翻译 -> 英文截断`
- 超长中文 prompt 会先整段送到 Ollama 做翻译
- 结果在翻译阶段就可能挂住或极慢，ComfyUI 根本收不到任务

**最终解决方案**：
- 改成：`原文先截断 -> 再翻译 -> 英文再截断`
- 当前阈值：原文先截到 500 字符，英文再截到 380 字符
- 放弃“智能压缩优先”，改为“硬截断优先”

**教训**：
- 长 prompt 的稳定性优化，先考虑**减少进入翻译模型的输入长度**，不是先考虑压缩花活
- 对 `/img` 这类生产命令，稳定性优先级高于“更聪明的压缩”

---

### [2026-03-07] Bot 子进程日志缓冲导致无法排查
**问题**：Bot 启动子进程执行命令，但日志无法实时输出，卡住时看不到内部发生了什么

**根本原因**：
- Python 子进程的标准输出被缓冲
- `subprocess.Popen([PY, "-c", script], ...)` 默认行缓冲
- 导致 `print()` 输出不会立即刷新到日志文件

**解决方案**：
```python
proc = subprocess.Popen([PY, "-u", "-c", script], ...)
```
添加 `-u` 参数（unbuffered），强制实时输出

**教训**：
- 子进程调试时必须添加 `-u` 参数
- 否则日志延迟会让你以为程序卡住了
- 但更深一层的教训是：**别让业务正确性依赖子进程 stdout**

---

### [2026-03-07] poll_history 逻辑错误导致永久等待
**问题**：任务已完成，图片已生成，但 Bot 一直显示"生成中"

**根本原因**：
- 原代码只检查 `/history/{prompt_id}`
- 但任务执行期间不在 history 中，只在 queue 中
- 任务完成后才会出现在 history
- 如果只检查 history，会错过"任务还在队列中"的状态

**解决方案**：
```python
def poll_history(prompt_id, timeout=600):
    # 1. 先检查 /queue，如果任务还在队列中就等待
    queue_status = requests.get(f"{API}/queue").json()
    if is_in_queue(queue_status, prompt_id):
        continue
    
    # 2. 任务不在队列了，再检查 /history
    history = requests.get(f"{API}/history/{prompt_id}").json()
    if prompt_id in history:
        return history[prompt_id]
```

**教训**：
- ComfyUI 的任务状态分两个阶段：queue → history
- 必须先检查队列，再检查 history
- 否则会错过"正在执行"的状态

---

## 🟡 中等级

### [2026-03-07] Telegram editMessageText 失败导致结果不发送
**问题**：Bot 任务完成后试图编辑"生成中"的消息，但如果消息已被删除，编辑失败（HTTP 400），导致后续的 `send_result` 没有执行

**根本原因**：
- `edit_msg()` 函数没有错误处理
- 编辑失败时抛出异常，中断了后续流程

**解决方案**：
```python
def edit_msg(cid, msg_id, text):
    try:
        return tg("editMessageText", {"chat_id": cid, "message_id": msg_id, "text": text})
    except Exception as e:
        log(f"edit_msg failed: {e}")
        return None  # 继续执行
```

**教训**：
- 所有外部 API 调用都要加错误处理
- 非关键操作失败不应中断主流程
- 编辑消息是"锦上添花"，发送结果才是核心

---

## 🟢 轻微级

### [2026-03-07] 工作流 JSON 中的 EmptyLatentImage vs EmptySD3LatentImage
**问题**：不同模型需要不同的 Latent 节点

**解决方案**：
- SD 1.5/2.x：`EmptyLatentImage`
- SD 3.x / Flux / Z-Image：`EmptySD3LatentImage`

**教训**：
- 复制工作流时注意模型架构差异
- 错误的 Latent 节点会导致维度不匹配

---

## 排查工具箱

### ComfyUI 状态检查
```powershell
# 检查队列
curl http://127.0.0.1:8188/queue | ConvertFrom-Json

# 检查 history（最新任务）
$h = curl http://127.0.0.1:8188/history 2>&1 | ConvertFrom-Json
$latest = $h.PSObject.Properties | Select-Object -First 1
Write-Host "ID: $($latest.Name)"
Write-Host "Status: $($latest.Value.status.status_str)"

# 检查最新图片
Get-ChildItem "D:\ComfyUI\ComfyUI_windows_portable\ComfyUI\output" -Filter "moody*.png" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
```

### Bot 排查
```powershell
# 实时查看 Bot 日志
Get-Content C:\Users\admin\.openclaw\workspace\comfy_bot.log -Tail 50 -Wait

# 检查卡住的子进程
Get-Process python | ForEach-Object { 
    $cmd = (Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
    if ($cmd -like "*cmd_handler*") { 
        [PSCustomObject]@{PID=$_.Id; StartTime=$_.StartTime; Runtime=[math]::Round(((Get-Date) - $_.StartTime).TotalMinutes, 1)} 
    } 
}

# 杀掉卡住的子进程
Stop-Process -Id <PID> -Force
```

### 显存监控
```powershell
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
```
