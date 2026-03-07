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
$CHECK_INTERVAL = 180
$COMFY_GRACE_SECONDS = 45
$BOT_GRACE_SECONDS = 20

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

function Ensure-Comfy {
    if (Test-ComfyAlive) {
        Log 'ComfyUI healthy'
        return
    }
    Log 'ComfyUI health check failed'
    Start-Comfy
    Start-Sleep -Seconds $COMFY_GRACE_SECONDS
    if (Test-ComfyAlive) {
        Log 'ComfyUI recovered'
    } else {
        Log 'ComfyUI still down after grace period'
    }
}

function Ensure-Bot {
    if (Get-BotProcess) {
        Log 'Telegram bot healthy'
        return
    }
    Log 'Telegram bot missing'
    Start-Bot
    Start-Sleep -Seconds $BOT_GRACE_SECONDS
    if (Get-BotProcess) {
        Log 'Telegram bot recovered'
    } else {
        Log 'Telegram bot still missing after grace period'
    }
}

# single-instance guard
$lockHandle = $null
try {
    $lockHandle = [System.IO.File]::Open($LOCK, 'OpenOrCreate', 'ReadWrite', 'None')
} catch {
    exit 0
}

try {
    Log "Watchdog started (interval=${CHECK_INTERVAL}s)"
    while ($true) {
        Ensure-Comfy
        Ensure-Bot
        Start-Sleep -Seconds $CHECK_INTERVAL
    }
} finally {
    if ($lockHandle) { $lockHandle.Close() }
}
