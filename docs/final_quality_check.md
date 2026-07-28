# Final Quality Check

This document records the current completion status for ClaimGuard AI.

## Verified In This Workspace

- Python syntax check passed for:
  - `app.py`
  - `src/`
  - `tests/`
  - `frontend/`
  - `scripts/`
- PowerShell parse check passed for:
  - `scripts/setup_windows.ps1`
  - `scripts/run_backend.ps1`
  - `scripts/run_frontend.ps1`
- Streamlit dashboard styling was upgraded to a light, branded UI.
- Claim-aware AI assistant was added with deterministic mode, optional
  Gemini generation, and optional policy RAG context.
- Backend refactor has started incrementally: API schemas and cached
  route dependencies were moved out of root `app.py` into `src/api/`
  without changing existing endpoint paths.
- The first API router was extracted: `/`, `/health`, and
  `/model/features` now live in `src/api/routers/health.py`.
- Fraud API routes were extracted: `/predict` and
  `/claims/{claim_id}/risk-assessment` now live in
  `src/api/routers/fraud.py`; shared claim validation context building
  lives in `src/api/claim_context.py`.
- Claim registry routes were extracted: `/claims`,
  `/claims/{claim_id}`, and `/claims/{claim_id}/documents` now live in
  `src/api/routers/claims.py`.
- Validation routes were extracted: completeness, validation execution,
  and saved validation retrieval now live in
  `src/api/routers/validation.py`.
- Assessment and claim-assistant routes now live in
  `src/api/routers/assessment.py`.
- Human review, field correction, and audit-log routes now live in
  `src/api/routers/reviews.py`.
- Policy RAG routes now live in `src/api/routers/rag.py`.
- Document type, upload, extraction, and field extraction routes now
  live in `src/api/routers/documents.py`.
- Root `app.py` is now a thin FastAPI setup file with router
  registration, request-ID middleware, and startup initialization.
- VS Code tasks now use the project scripts instead of long raw commands.
- `.gitignore` excludes virtual environments, `.env`, uploads, extracted files,
  field outputs, demo data, databases, model binaries, and vector stores.

## Local Machine Checks To Run

These checks require a healthy local Python 3.11 virtual environment:

```powershell
.\scripts\setup_windows.ps1 -RecreateVenv
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest tests -v --tb=short -m "not integration"
```

Start the backend:

```powershell
.\scripts\run_backend.ps1
```

Start the dashboard in a second terminal:

```powershell
.\scripts\run_frontend.ps1
```

Open:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8501
```

## External Dependencies

- Docker runtime verification requires Docker Desktop to be running.
- Live Gemini answer generation requires `GEMINI_API_KEY` in `.env`.
- Real RAG embedding retrieval may need the Hugging Face embedding model cached
  locally or network access to download it.

## Demo Safety Notes

- Fraud probabilities are decision-support signals, not proof of fraud.
- Policy answers are informational and not legal advice.
- The system must keep a human reviewer in the final claim decision process.
- The project uses synthetic/demo data and is not validated for production
  insurance decisions.
