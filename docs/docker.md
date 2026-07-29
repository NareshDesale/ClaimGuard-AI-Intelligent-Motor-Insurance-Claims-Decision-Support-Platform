# Docker Setup

ClaimGuard AI uses one local image for both services:

- `backend`: FastAPI on port `8000`
- `streamlit`: Streamlit dashboard on port `8501`

The image does not copy `.env`, uploaded documents, SQLite databases,
model binaries, or generated FAISS vector indexes.

## Required Local Files

Before running Docker Compose, make sure these local paths exist:

- `models/fraud_model.joblib`
- `vector_store/policy.index`
- `vector_store/policy_chunks.json`

They are mounted read-only into the backend container:

- `./models:/app/models:ro`
- `./vector_store:/app/vector_store:ro`

Runtime claim data is persisted through:

- `./data:/app/data`

## Run

```bash
docker compose up --build
```

The Compose file can be checked without starting containers:

```bash
docker compose config
```

This was validated during the local final polish pass. Full
container startup still requires free host ports `8000` and `8501`,
Docker Desktop running, and any required model/vector files available
through the mounted folders.

Backend:

```text
http://localhost:8000
```

Streamlit:

```text
http://localhost:8501
```

## Environment

Use `.env.example` as a template for local values. Do not put real
secrets in source control.

The local Compose setup defaults to SQLite:

```text
sqlite:////app/data/claimguard.db
```

EasyOCR and PyTorch run on CPU in this MVP image. The image sets
`HF_HOME` and `TORCH_HOME` under `/app/data` so downloaded model cache
files can persist through the `data` volume.
