param(
    [switch]$RecreateVenv,
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

Write-Host "ClaimGuard AI Windows setup"
Write-Host "Project: $ProjectRoot"

function Remove-VenvSafely {
    if (-not (Test-Path ".venv")) {
        return
    }

    $attempts = 3

    for ($attempt = 1; $attempt -le $attempts; $attempt++) {
        try {
            Write-Host "Removing existing .venv to avoid mixed Python ABI packages... attempt $attempt of $attempts"
            Remove-Item -LiteralPath ".venv" -Recurse -Force -ErrorAction Stop
            return
        }
        catch {
            if ($attempt -lt $attempts) {
                Start-Sleep -Seconds 2
                continue
            }

            Write-Error @"
Could not remove .venv because Windows is still locking one or more files.

Close anything using this project, especially:
  - FastAPI / uvicorn terminal
  - Streamlit terminal
  - Python shells
  - VS Code test/debug sessions

Then run:
  taskkill /F /IM python.exe
  taskkill /F /IM pythonw.exe
  .\scripts\setup_windows.ps1 -RecreateVenv

Original error:
$($_.Exception.Message)
"@
        }
    }
}

function Resolve-Python311 {
    param([string]$ExplicitPythonPath)

    $candidates = @()

    if ($ExplicitPythonPath) {
        $resolvedPythonPath = Resolve-Path $ExplicitPythonPath
        $candidates += @("`"$($resolvedPythonPath.Path)`"")
    }

    $candidates += @(
        "py -3.11",
        "python",
        "python3"
    )

    foreach ($candidate in $candidates) {
        try {
            $version = & cmd /c "$candidate -c `"import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')`"" 2>$null
            if ($LASTEXITCODE -eq 0 -and "$version".StartsWith("3.11.")) {
                return $candidate
            }
        }
        catch {
            continue
        }
    }

    Write-Error @"
Python 3.11 was not found.

Install Python 3.11 from https://www.python.org/downloads/release/python-3119/
or rerun with an explicit executable path, for example:
  .\scripts\setup_windows.ps1 -RecreateVenv -PythonPath "C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe"
"@
}

$PythonCommand = Resolve-Python311 -ExplicitPythonPath $PythonPath
$pythonCheck = & cmd /c "$PythonCommand --version"
Write-Host "Using $pythonCheck via '$PythonCommand'"

if ($RecreateVenv -and (Test-Path ".venv")) {
    Remove-VenvSafely
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating .venv with Python 3.11..."
    & cmd /c "$PythonCommand -m venv .venv"
}

Write-Host "Verifying .venv Python version..."
$venvVersion = & .\.venv\Scripts\python.exe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
if (-not "$venvVersion".StartsWith("3.11.")) {
    Write-Error "The .venv is using Python $venvVersion. Delete .venv and recreate it with Python 3.11."
}

Write-Host "Upgrading pip..."
& .\.venv\Scripts\python.exe -m pip install --upgrade pip

Write-Host "Installing dependencies..."
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "Checking installed packages..."
& .\.venv\Scripts\python.exe -m pip check

if (-not (Test-Path ".env")) {
    Write-Host "Creating .env from .env.example..."
    Copy-Item .env.example .env
}

Write-Host "Generating synthetic demo data..."
& .\.venv\Scripts\python.exe scripts\generate_demo_data.py

Write-Host ""
Write-Host "Setup complete."
Write-Host "Run backend:"
Write-Host "  .\.venv\Scripts\python.exe -m uvicorn app:app --reload --host 127.0.0.1 --port 8000"
Write-Host "Run Streamlit:"
Write-Host "  .\.venv\Scripts\python.exe -m streamlit run frontend\streamlit_app.py --server.address=127.0.0.1 --server.port=8501"
