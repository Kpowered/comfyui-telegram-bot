$ErrorActionPreference = 'SilentlyContinue'

$WS = 'C:\Users\admin\.openclaw\workspace'
$LOG = Join-Path $WS 'watchdog.log'
$BOT_PY = Join-Path $WS 'comfy_bot.py'
$BOT_PID = Join-Path $WS 'comfy_bot.pid'
$PY = 'D:\ComfyUI\ComfyUI_windows_portable\python_embeded\python.exe'
$COMFY_MAIN = 'D:\ComfyUI\ComfyUI_windows_portable\ComfyUI\main.py'
$COMFY_PORT = 8188
$COMFY_URL = 'http://127.0.0.1:8188/system_stats'
$LOCK = Join-Path $WS 'watchdog.lock'

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Add-Content -Path $LOG -Value $line -Encoding UTF8
}

function Test-ComfyAlive {
    try {
        $r = Invoke-WebRequest -Uri $COMFY_URL -UseBasicParsing -TimeoutSec 5
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Get-ComfyProcess {
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and $_.CommandLine -like '*ComfyUI\main.py*' -and $_.CommandLine -like '*--port 8188*'
    }
}

function Get-BotProcess {
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and $_.CommandLine -like '*comfy_bot.py*'
    }
}

function Start-Comfy {
    if (Get-ComfyProcess) {
        Log 'ComfyUI already running process found, skip start'
        return
    }
    Log 'Starting ComfyUI'
    Start-Process -FilePath $PY -ArgumentList @('-s', $COMFY_MAIN, '--listen', '127.0.0.1', '--port', '8188', '--output-directory', 'D:\ComfyUI\ComfyUI_windows_portable\ComfyUI\output') -WindowStyle Hidden
}

function Start-Bot {
    if (Get-BotProcess) {
        Log 'Telegram bot already running process found, skip start'
        return
    }
    if (Test-Path $BOT_PID) {
        try {
            $oldPid = [int](Get-Content $BOT_PID -ErrorAction Stop)
            if (Get-Process -Id $oldPid -ErrorAction SilentlyContinue) {
                Log "Bot pid file points to live PID $oldPid, skip start"
                return
            } else {
                Remove-Item $BOT_PID -Force -ErrorAction SilentlyContinue
                Log "Removed stale bot pid file $oldPid"
            }
        } catch {
            Remove-Item $BOT_PID -Force -ErrorAction SilentlyContinue
            Log 'Removed invalid bot pid file'
        }
    }
    Log 'Starting Telegram bot'
    Start-Process -FilePath $PY -ArgumentList @($BOT_PY) -WindowStyle Hidden
}

# single-instance guard
$lockHandle = $null
try {
    $lockHandle = [System.IO.File]::Open($LOCK, 'OpenOrCreate', 'ReadWrite', 'None')
} catch {
    exit 0
}

try {
    if (-not (Test-ComfyAlive)) {
        Log 'ComfyUI health check failed'
        Start-Comfy
    }
    Start-Sleep -Seconds 2
    Start-Bot
} finally {
    if ($lockHandle) { $lockHandle.Close() }
}
