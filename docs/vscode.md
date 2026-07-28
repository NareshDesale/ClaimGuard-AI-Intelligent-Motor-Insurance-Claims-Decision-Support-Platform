# Running ClaimGuard AI In VS Code

Open this folder in VS Code:

```text
C:\Users\Admin\OneDrive\Desktop\ClaimGuard AI — Intelligent Motor Insurance Claims Decision-Support Platform
```

## 1. Select Python Interpreter

Use:

```text
Ctrl+Shift+P -> Python: Select Interpreter
```

Choose:

```text
.venv\Scripts\python.exe
```

If `.venv` does not exist, create it from the VS Code terminal:

```powershell
py -3.11 -m venv .venv
```

If Python 3.11 is not installed, install Python 3.11 first. The local
repair environment used during development was Python 3.12, but the
project target is Python 3.11.

## 2. Install Dependencies

Recommended repair/setup command:

```powershell
.\scripts\setup_windows.ps1 -RecreateVenv
```

If `py -3.11` is not available but Python 3.11 is installed, pass the
executable path:

```powershell
.\scripts\setup_windows.ps1 -RecreateVenv -PythonPath "C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe"
```

Use that command if you see errors such as:

- `numpy C-extensions failed`
- `cp312-win_amd64` inside a Python 3.11 venv
- `ImportError: cannot import name '_imaging' from 'PIL'`

Those errors mean `.venv` contains packages compiled for the wrong
Python version. The fix is to delete and recreate `.venv`, not to keep
installing over it.

Manual install:

```powershell
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 3. Create `.env`

```powershell
Copy-Item .env.example .env
```

Set `GEMINI_API_KEY` only if you want live Gemini policy answers.

## 4. Generate Demo Data

```powershell
.venv\Scripts\python.exe scripts\generate_demo_data.py
```

## 5. Run Backend

```powershell
.\scripts\run_backend.ps1
```

Open:

```text
http://127.0.0.1:8000/docs
```

Health check:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing
```

## 6. Run Streamlit Dashboard

Open a second terminal:

```powershell
.\scripts\run_frontend.ps1
```

Open:

```text
http://127.0.0.1:8501
```

## 7. Run Tests

```powershell
.venv\Scripts\python.exe -m pytest tests -v --tb=short -m "not integration"
```

The real RAG retrieval tests skip when the Hugging Face embedding model
is not cached locally and network access is unavailable. The Gemini
integration test is deselected unless explicitly requested.

## 8. VS Code Tasks

Use:

```text
Terminal -> Run Task
```

Available tasks:

- `ClaimGuard: create .venv`
- `ClaimGuard: install dependencies`
- `ClaimGuard: generate demo data`
- `ClaimGuard: run backend`
- `ClaimGuard: run Streamlit`
- `ClaimGuard: run tests`
- `ClaimGuard: syntax check`
- `ClaimGuard: Docker Compose config`
- `ClaimGuard: Docker Compose up`

## 9. Debug Configurations

Use the Run and Debug panel:

- `ClaimGuard: FastAPI`
- `ClaimGuard: Streamlit`

## 10. Docker

Docker commands require Docker Desktop to be running:

```powershell
docker compose config --quiet
docker compose up --build
```

Backend:

```text
http://127.0.0.1:8000
```

Streamlit:

```text
http://127.0.0.1:8501
```
