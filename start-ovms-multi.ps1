# start-ovms-multi.ps1 — Start OVMS with multiple registered models.
#
# Uses env vars:
#   MODEL_IDS      comma-separated model ids (e.g. OpenVINO/Qwen3-14B-int4-ov,OpenVINO/Qwen3-1.7B-fp16-ov)
#   TARGET_DEVICE  optional, default GPU
#   REST_PORT      optional, default 8000

$OVMS_DIR      = "$PSScriptRoot\ovms"
$MODEL_REPO    = "$PSScriptRoot\models"
$TARGET_DEVICE = if ($env:TARGET_DEVICE) { $env:TARGET_DEVICE } else { "GPU" }
$REST_PORT     = if ($env:REST_PORT) { $env:REST_PORT } else { "8000" }
$CONFIG_PATH   = "$PSScriptRoot\ovms\multi-model-config.json"

if (-not (Test-Path "$OVMS_DIR\ovms.exe")) {
    Write-Error "ovms.exe not found at $OVMS_DIR\ovms.exe"
    exit 1
}

$setupvars = "$OVMS_DIR\setupvars.ps1"
if (Test-Path $setupvars) {
    . $setupvars
} else {
    Write-Error "setupvars.ps1 not found at $setupvars"
    exit 1
}

$env:ZES_ENABLE_SYSMAN = "1"

$modelIdsRaw = if ($env:MODEL_IDS) { $env:MODEL_IDS } else { "" }
$modelIds = @()
if ($modelIdsRaw) {
    $modelIds = $modelIdsRaw.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
}

if ($modelIds.Count -eq 0) {
    Write-Error "No MODEL_IDS provided."
    exit 1
}

Write-Host "Preparing multi-model OVMS startup"
Write-Host "  Target device : $TARGET_DEVICE"
Write-Host "  Rest port     : $REST_PORT"
Write-Host "  Models count  : $($modelIds.Count)"

# Generate missing graph.pbtxt for each selected model.
$preparedModels = @()
foreach ($modelId in $modelIds) {
    Write-Host "Ensuring OVMS graph for $modelId"
    & "$OVMS_DIR\ovms.exe" --pull --source_model $modelId --model_repository_path $MODEL_REPO --task text_generation --target_device $TARGET_DEVICE
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Skipping model due to prepare failure: $modelId"
        continue
    }
    $preparedModels += $modelId
}

$modelConfigList = @()
foreach ($modelId in $preparedModels) {
    $basePath = Join-Path $MODEL_REPO ($modelId -replace "/", "\\")
    $graphPath = Join-Path $basePath "graph.pbtxt"
    $xmlPath = Join-Path $basePath "openvino_model.xml"
    $binPath = Join-Path $basePath "openvino_model.bin"
    if ((Test-Path $graphPath) -and (Test-Path $xmlPath) -and (Test-Path $binPath)) {
        $modelConfigList += @{ config = @{ name = $modelId; base_path = $basePath } }
    } else {
        Write-Warning "Skipping invalid model artifacts: $modelId"
    }
}

if ($modelConfigList.Count -eq 0) {
    Write-Error "No valid models with graph.pbtxt found for multi-model config."
    exit 1
}

$configObject = @{ model_config_list = $modelConfigList }
$json = $configObject | ConvertTo-Json -Depth 8
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($CONFIG_PATH, $json, $utf8NoBom)

Write-Host "Multi-model config written: $CONFIG_PATH"
Write-Host "Starting OVMS with config_path..."

& "$OVMS_DIR\ovms.exe" --config_path $CONFIG_PATH --rest_port $REST_PORT
