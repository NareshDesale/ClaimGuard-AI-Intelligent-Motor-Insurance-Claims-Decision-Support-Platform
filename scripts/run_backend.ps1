$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Error "Virtual environment not found. Run .\scripts\setup_windows.ps1 -RecreateVenv first."
}

Write-Host "Starting ClaimGuard AI FastAPI backend on http://127.0.0.1:8000"
& .\.venv\Scripts\python.exe -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
