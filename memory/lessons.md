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
