# Operations Notes

This project currently targets local MVP operation.

## Local Runtime

- Backend: `uvicorn app:app --reload`
- Frontend: `streamlit run frontend/streamlit_app.py`
- Database: SQLite at `data/claimguard.db` by default

## Generated Artifacts

These paths are intentionally ignored by Git:

- `data/uploads/`
- `data/extracted/`
- `data/fields/`
- `data/validation/`
- `data/assessments/`
- `data/*.db`
- `models/*.joblib`
- `vector_store/`

## Secrets

`.env` is ignored. Use `.env.example` as a template and keep real
credentials outside source control.

## Logging

`LOG_LEVEL` controls Python logging. The backend also returns an
`X-Request-ID` response header for request tracing.

## Production Gaps

Before real deployment, add authentication, authorization, encrypted
storage, secret management, database migrations, monitoring, backups,
and formal model governance.
