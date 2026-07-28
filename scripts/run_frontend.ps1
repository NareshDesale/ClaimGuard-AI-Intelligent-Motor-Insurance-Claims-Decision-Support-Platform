$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Error "Virtual environment not found. Run .\scripts\setup_windows.ps1 -RecreateVenv first."
}

if (-not $env:CLAIMGUARD_API_URL) {
    $env:CLAIMGUARD_API_URL = "http://127.0.0.1:8000"
}

Write-Host "Starting ClaimGuard AI Streamlit frontend on http://127.0.0.1:8501"
& .\.venv\Scripts\python.exe -m streamlit run frontend\streamlit_app.py --server.address=127.0.0.1 --server.port=8501
