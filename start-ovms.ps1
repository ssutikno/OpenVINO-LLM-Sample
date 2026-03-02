# start-ovms.ps1 — Run OpenVINO Model Server (OVMS) natively on Windows.
#
# Usage (run from project directory):
#   powershell.exe -ExecutionPolicy Bypass -File start-ovms.ps1
#
# On first run this script:
#   1. Downloads the OVMS v2026.0 Windows binary package (~124 MB)
#   2. Downloads the model from HuggingFace to .\models\ (~9.7 GB for Qwen3-14B-int4)
#
# Subsequent runs skip both downloads and start immediately.
#
# Prerequisites:
#   - Microsoft Visual C++ Redistributable x64 installed
#     https://aka.ms/vs/17/release/VC_redst.x64.exe
#   - Internet access for first-time model download

# ── Configuration ────────────────────────────────────────────────────────────
$OVMS_VERSION    = "v2026.0"
$OVMS_ZIP        = "ovms_windows_python_on.zip"
$OVMS_URL        = "https://github.com/openvinotoolkit/model_server/releases/download/$OVMS_VERSION/$OVMS_ZIP"
$OVMS_DIR        = "$PSScriptRoot\ovms"
$MODEL_REPO      = "$PSScriptRoot\models"

# Model to serve — must be an OpenVINO-exported HuggingFace repo.
# Change this to any model from https://huggingface.co/OpenVINO
$MODEL_ID        = if ($env:MODEL_ID)       { $env:MODEL_ID }       else { "OpenVINO/Qwen3-14B-int4-ov" }
$TARGET_DEVICE   = if ($env:TARGET_DEVICE)  { $env:TARGET_DEVICE }  else { "GPU" }
$REST_PORT       = if ($env:REST_PORT)      { $env:REST_PORT }      else { "8000" }

# Optional HuggingFace token for gated models
# $env:HF_TOKEN = "hf_..."

# ── Step 1: Download OVMS if not already present ─────────────────────────────
if (-not (Test-Path "$OVMS_DIR\ovms.exe")) {
    Write-Host "OVMS binary not found. Downloading $OVMS_VERSION..."
    $zipPath = "$PSScriptRoot\$OVMS_ZIP"
    curl.exe -L $OVMS_URL -o $zipPath
    Write-Host "Extracting..."
    tar -xf $zipPath -C $PSScriptRoot
    Remove-Item $zipPath -ErrorAction SilentlyContinue
    Write-Host "OVMS extracted to $OVMS_DIR"
} else {
    Write-Host "OVMS found: $OVMS_DIR\ovms.exe"
}

# ── Step 2: Set OVMS environment variables ───────────────────────────────────
# setupvars.ps1 must run in the current shell to export env vars correctly.
$setupvars = "$OVMS_DIR\setupvars.ps1"
if (Test-Path $setupvars) {
    . $setupvars
} else {
    Write-Error "setupvars.ps1 not found at $setupvars"
    exit 1
}

# ── Step 3: Enable Intel GPU Sysman interface ────────────────────────────────
$env:ZES_ENABLE_SYSMAN = "1"

# ── Step 4: Start OVMS ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Starting OpenVINO Model Server..."
Write-Host "  Model    : $MODEL_ID"
Write-Host "  Device   : $TARGET_DEVICE"
Write-Host "  API base : http://localhost:$REST_PORT/v3"
Write-Host "  Models   : $MODEL_REPO"
Write-Host ""
Write-Host "On first run the model (~9.7 GB) will be downloaded to: $MODEL_REPO\$MODEL_ID"
Write-Host "Wait for 'Server started on port' message before sending requests."
Write-Host ""

# --source_model   : HuggingFace repo to download & serve (auto-downloads on first run)
# --model_repository_path : local directory where models are stored
# --task           : text_generation enables the LLM / continuous-batching pipeline
# --target_device  : GPU uses the Intel Arc GPU directly (no WSL2 restrictions)
# --rest_port      : HTTP port for the OpenAI-compatible /v3 API
ovms.exe `
    --source_model         $MODEL_ID `
    --model_repository_path $MODEL_REPO `
    --task                 text_generation `
    --target_device        $TARGET_DEVICE `
    --rest_port            $REST_PORT
