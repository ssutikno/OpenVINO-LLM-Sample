# start-manager.ps1 — Launch the OVMS Model Manager (Streamlit) app.
#
# Uses the project .venv Python environment.
# Run from the project root:
#   powershell.exe -ExecutionPolicy Bypass -File start-manager.ps1

$ScriptDir = $PSScriptRoot
$Streamlit  = "$ScriptDir\.venv\Scripts\streamlit.exe"
$AppPath    = "$ScriptDir\tools\model_manager_app.py"

if (-not (Test-Path $Streamlit)) {
    Write-Error "Streamlit not found at $Streamlit"
    Write-Host "Install dependencies first:"
    Write-Host "  .\.venv\Scripts\pip.exe install -r .\tools\requirements-model-manager.txt"
    exit 1
}

Write-Host "Starting OVMS Model Manager..."
Write-Host "  App    : $AppPath"
Write-Host "  Python : $ScriptDir\.venv"
Write-Host "  URL    : http://localhost:8501"
Write-Host ""

& $Streamlit run $AppPath --server.headless true
