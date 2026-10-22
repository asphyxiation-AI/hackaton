# =============================================================================
# start_project.ps1 - single launch script for Ollama + Streamlit project
# Works only in Windows PowerShell.
# Can be run as .ps1 or packed into .exe via PS2EXE.
# =============================================================================
$ErrorActionPreference = "Continue"

# --- Determine project directory (works both as .ps1 and as PS2EXE .exe) ---
function Get-ScriptDirectory {
    # 1) If packed into .exe via PS2EXE -> use exe location
    try {
        $exePath = [System.Reflection.Assembly]::GetEntryAssembly().Location
        if ($exePath -and (Test-Path $exePath)) {
            return Split-Path -Parent $exePath
        }
    } catch { }

    # 2) If running as plain .ps1 -> use script location
    if ($PSScriptRoot) { return $PSScriptRoot }

    # 3) Fallback: current working directory
    return (Get-Location).Path
}

$projectDir = Get-ScriptDirectory
Set-Location $projectDir

Write-Host "+---------------------------------------------------------------+" -ForegroundColor Cyan
Write-Host "|  Launching AI assistant for energy sector (IT/IB digests)      |" -ForegroundColor Cyan
Write-Host "+---------------------------------------------------------------+" -ForegroundColor Cyan
Write-Host "Project directory: $projectDir" -ForegroundColor DarkGray
Write-Host ""

# -----------------------------------------------------------------------------
# 0. Sanity check: is app.py and venv here?
# -----------------------------------------------------------------------------
if (-not (Test-Path (Join-Path $projectDir "app.py"))) {
    Write-Host "ERROR: app.py not found in $projectDir" -ForegroundColor Red
    Write-Host "Make sure StartDigest.exe is placed in the 'prototip' folder next to app.py." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

$streamlitExe = Join-Path $projectDir "venv\Scripts\streamlit.exe"
if (-not (Test-Path $streamlitExe)) {
    Write-Host "ERROR: venv\Scripts\streamlit.exe not found in $projectDir" -ForegroundColor Red
    Write-Host "Create venv and install dependencies first." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# -----------------------------------------------------------------------------
# 1. Ollama server
# -----------------------------------------------------------------------------
Write-Host "[1/3] Checking Ollama server (http://localhost:11434)..." -ForegroundColor Cyan
$ollamaResp = try {
    Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 -ErrorAction Stop
} catch {
    $null
}

if (-not $ollamaResp) {
    Write-Host "   Ollama server is not responding. Starting 'ollama serve' in background..." -ForegroundColor Yellow
    try {
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden -ErrorAction Stop
    } catch {
        Write-Host "   ERROR: 'ollama' command not found. Install Ollama from https://ollama.com" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Start-Sleep -Seconds 5
    $ollamaResp = try {
        Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5 -ErrorAction Stop
    } catch {
        Write-Host "   ERROR: Ollama server failed to start. Check Ollama installation." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}
Write-Host "   Ollama server is available." -ForegroundColor Green

# -----------------------------------------------------------------------------
# 2. Model
# -----------------------------------------------------------------------------
Write-Host "[2/3] Checking model qwen2.5:7b..." -ForegroundColor Cyan
$models = try {
    (Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5).models.name
} catch {
    @()
}

if ($models -notcontains "qwen2.5:7b") {
    Write-Host "   Model qwen2.5:7b not found. Downloading (may take a while)..." -ForegroundColor Yellow
    ollama pull qwen2.5:7b
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   ERROR: failed to download model qwen2.5:7b." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
} else {
    Write-Host "   Model qwen2.5:7b is already available." -ForegroundColor Green
}

# -----------------------------------------------------------------------------
# 3. Streamlit
# -----------------------------------------------------------------------------
Write-Host "[3/3] Starting Streamlit on http://localhost:8501 ..." -ForegroundColor Cyan
Write-Host "   Browser will open automatically. Press Ctrl+C to stop." -ForegroundColor Gray
Write-Host ""
& $streamlitExe run (Join-Path $projectDir "app.py")