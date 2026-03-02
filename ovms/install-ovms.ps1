# install-ovms.ps1 — Download and extract the OVMS v2026.0 Windows binary package.
#
# Run once after cloning the repository to populate the ovms\ folder with the
# OVMS runtime binaries (ovms.exe, DLLs, bundled Python, etc.).
#
# These binaries are excluded from source control (.gitignore) because of their
# size (~124 MB zip). This script re-downloads them on demand.
#
# Usage (from the project root or from within the ovms\ folder):
#   powershell.exe -ExecutionPolicy Bypass -File .\ovms\install-ovms.ps1
#
# Prerequisites:
#   - Internet access
#   - Microsoft Visual C++ Redistributable x64
#     https://aka.ms/vs/17/release/VC_redst.x64.exe

# ── Configuration ─────────────────────────────────────────────────────────────
$OVMS_VERSION = "v2026.0"
$OVMS_ZIP     = "ovms_windows_python_on.zip"
$OVMS_URL     = "https://github.com/openvinotoolkit/model_server/releases/download/$OVMS_VERSION/$OVMS_ZIP"

# This script lives inside the ovms\ subfolder; the project root is one level up.
$OVMS_DIR     = $PSScriptRoot                         # …\project-root\ovms
$PROJECT_ROOT = (Resolve-Path "$PSScriptRoot\..").Path # …\project-root

# ── Skip if already installed ─────────────────────────────────────────────────
if (Test-Path "$OVMS_DIR\ovms.exe") {
    Write-Host "OVMS is already installed at $OVMS_DIR\ovms.exe"
    Write-Host "Delete ovms.exe (and the DLLs) then re-run to force a reinstall."
    exit 0
}

# ── Download ──────────────────────────────────────────────────────────────────
$zipPath = Join-Path $env:TEMP $OVMS_ZIP
Write-Host ""
Write-Host "Downloading OVMS $OVMS_VERSION..."
Write-Host "  From : $OVMS_URL"
Write-Host "  To   : $zipPath"
Write-Host ""

try {
    # Use curl.exe (ships with Windows 10+) for reliable large-file downloads
    $curlResult = & curl.exe -L --progress-bar -o $zipPath $OVMS_URL
    if ($LASTEXITCODE -ne 0) {
        throw "curl.exe exited with code $LASTEXITCODE"
    }
} catch {
    # Fallback: PowerShell Invoke-WebRequest
    Write-Host "curl.exe failed, falling back to Invoke-WebRequest..."
    Invoke-WebRequest -Uri $OVMS_URL -OutFile $zipPath -UseBasicParsing
}

if (-not (Test-Path $zipPath)) {
    Write-Error "Download failed — file not found at $zipPath"
    exit 1
}

$zipSize = (Get-Item $zipPath).Length / 1MB
Write-Host "Downloaded: $([Math]::Round($zipSize, 1)) MB"

# ── Extract ───────────────────────────────────────────────────────────────────
# The zip contains an 'ovms\' top-level directory.
# Extracting to $PROJECT_ROOT places everything into $PROJECT_ROOT\ovms\.
Write-Host ""
Write-Host "Extracting to $PROJECT_ROOT ..."

try {
    tar -xf $zipPath -C $PROJECT_ROOT
    if ($LASTEXITCODE -ne 0) { throw "tar exited with code $LASTEXITCODE" }
} catch {
    # Fallback: Expand-Archive (slower but always available)
    Write-Host "tar failed, falling back to Expand-Archive..."
    Expand-Archive -Path $zipPath -DestinationPath $PROJECT_ROOT -Force
}

# ── Cleanup ───────────────────────────────────────────────────────────────────
Remove-Item $zipPath -ErrorAction SilentlyContinue
Write-Host "Removed temporary zip."

# ── Verify ────────────────────────────────────────────────────────────────────
Write-Host ""
if (Test-Path "$OVMS_DIR\ovms.exe") {
    $exeVer = (Get-Item "$OVMS_DIR\ovms.exe").VersionInfo.FileVersion
    Write-Host "Installation complete."
    Write-Host "  ovms.exe  : $OVMS_DIR\ovms.exe"
    Write-Host "  Version   : $exeVer"
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1. Start the model manager  :  .\start-manager.ps1"
    Write-Host "  2. Start OVMS (multi-model) :  .\start-ovms-multi.ps1"
} else {
    Write-Error "ovms.exe not found after extraction. Check the archive structure."
    exit 1
}
