# Troubleshooting

## Mixed Python Wheel Error

Symptoms:

```text
ImportError: Unable to import required dependencies:
numpy

compiled module files exist, but seem incompatible
_multiarray_umath.cp312-win_amd64.pyd
Python 3.11
```

or:

```text
ImportError: cannot import name '_imaging' from 'PIL'
```

Cause:

`.venv` contains packages compiled for a different Python version. In
the example above, Python 3.11 is trying to import Python 3.12 wheels.

Fix:

```powershell
Remove-Item -Recurse -Force .venv
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

Or run:

```powershell
.\scripts\setup_windows.ps1 -RecreateVenv
```

If `py -3.11 --version` says `No installed Python found`, install
Python 3.11 first and make sure the `py.exe` launcher can see it.

## Uvicorn Reloader Shows A Child Process Traceback

When using `--reload`, Uvicorn starts a child process. If the child
process fails with NumPy/Pillow import errors, fix the virtual
environment first using the steps above.

## Hugging Face RAG Model Not Cached

Real policy retrieval uses:

```text
sentence-transformers/all-MiniLM-L6-v2
```

If network access is unavailable and the model is not cached locally,
the real retrieval tests skip and `/rag/retrieve` can return `503`.
Mocked RAG API/unit tests still run without this external download.
