# Evaluation

ClaimGuard AI evaluation is split into unit tests, deterministic service
tests, RAG retrieval evaluation, and optional integration tests.

## Unit And Service Tests

Run:

```bash
python -m pytest tests -v --tb=short -m "not integration"
```

Normal tests should not call Gemini. They use mocks for RAG answers and
OCR where practical.

Covered areas include:

- health and root endpoints
- model feature endpoint
- fraud prediction validation
- RAG retrieval logic
- mocked RAG API answer
- upload validation
- text extraction helpers
- OCR helper using mocks
- structured field extraction
- completeness checker
- cross-document validation
- claim repository
- audit logs
- human review
- assessment generation

## Gemini Integration Test

The optional integration test is marked with `integration` and skips
when `GEMINI_API_KEY` is absent.

Run:

```bash
python -m pytest tests/test_rag_gemini_integration.py -v -m integration
```

## RAG Evaluation Dataset

Dataset:

```text
data/evaluation/rag_questions.json
```

Each entry contains:

- `question`
- `expected_pages`
- `expected_keywords`
- `answerable`
- `category`

## RAG Metrics

Script:

```bash
python scripts/evaluate_rag.py
```

Reported metrics:

- `Recall@K`
- `MRR`
- source-page hit rate
- answer refusal accuracy

## Fraud Model Evaluation

Training code in `src/train_model.py` reports model metrics such as
classification report, confusion matrix, ROC-AUC, and PR-AUC. These
metrics describe behavior on the training/evaluation dataset only. They
do not validate the system for real insurance decisions.

## Known Evaluation Gaps

- No production calibration study.
- No reviewer outcome study.
- No privacy or fairness certification.
- Limited RAG evaluation dataset.
- No antivirus validation.
- No end-to-end test requiring a live Kubernetes cluster.
