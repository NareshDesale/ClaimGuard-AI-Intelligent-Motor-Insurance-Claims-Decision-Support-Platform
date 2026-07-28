# API Reference

Base URL for local development:

```text
http://localhost:8000
```

Interactive docs:

```text
http://localhost:8000/docs
```

## General

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Basic API message |
| `GET` | `/health` | Health and model-load status |

## Claim Registry

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/claims` | Create a claim record |
| `GET` | `/claims` | List claims |
| `GET` | `/claims/{claim_id}` | Get one claim |
| `PATCH` | `/claims/{claim_id}` | Update claim metadata |
| `GET` | `/claims/{claim_id}/documents` | List documents for a claim |

Example create request:

```json
{
  "claim_id": "CLM-DEMO-001",
  "policy_number": "POL-2026-001",
  "customer_name": "Demo Customer",
  "vehicle_number": "MH12AB1234",
  "accident_date": "2026-08-12",
  "reported_date": "2026-08-14",
  "claimed_amount": 42500,
  "status": "open"
}
```

## Fraud Model

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/model/features` | Return expected model features |
| `POST` | `/predict` | Predict risk from a full model feature payload |
| `POST` | `/claims/{claim_id}/risk-assessment` | Build risk assessment from claim data and optional manual features |

Risk assessment request:

```json
{
  "manual_features": {
    "Age": 34
  }
}
```

Risk assessment output is not a final fraud decision.

## Policy RAG

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/rag/health` | Check policy index and Gemini configuration |
| `POST` | `/rag/ask` | Retrieve sources and generate grounded answer |
| `POST` | `/rag/retrieve` | Retrieve sources without calling Gemini |

Example:

```json
{
  "question": "What third-party liabilities are covered?",
  "top_k": 4,
  "min_similarity_score": 0.25,
  "claim_id": "CLM-DEMO-001"
}
```

## Documents

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/documents/types` | List supported document types |
| `POST` | `/claims/{claim_id}/documents` | Upload one PDF or image |
| `POST` | `/claims/{claim_id}/documents/{document_id}/extract` | Extract text |
| `GET` | `/claims/{claim_id}/documents/{document_id}/extraction` | Get saved extraction |
| `POST` | `/claims/{claim_id}/documents/{document_id}/fields` | Extract structured fields |
| `GET` | `/claims/{claim_id}/documents/{document_id}/fields` | Get saved fields |

Supported document types:

- `claim_form`
- `policy_document`
- `repair_invoice`
- `accident_report`
- `identity_document`
- `vehicle_image`
- `other`

## Validation

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/claims/{claim_id}/completeness` | Check required documents |
| `POST` | `/claims/{claim_id}/validate` | Run cross-document validation |
| `GET` | `/claims/{claim_id}/validation` | Get saved validation result |

Validation rule output shape:

```json
{
  "rule_id": "vehicle_registration_mismatch",
  "severity": "high",
  "status": "failed",
  "message": "Vehicle registration values do not match.",
  "documents": ["doc1(claim_form)", "doc2(repair_invoice)"],
  "evidence": ["MH12AB1234", "MH14CD5678"]
}
```

## Assessment

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/claims/{claim_id}/assessment` | Generate consolidated assessment |
| `GET` | `/claims/{claim_id}/assessment` | Get saved assessment |

Allowed next actions:

- `ready_for_normal_review`
- `request_more_documents`
- `manual_policy_review`
- `fraud_investigation_review`
- `data_correction_required`

## Claim AI Assistant

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/claims/{claim_id}/assistant` | Ask a claim-aware assistant using claim metadata, documents, fields, validation, assessment, and optional policy RAG context |

Example:

```json
{
  "question": "What should the reviewer check next?",
  "use_llm": false,
  "include_policy_context": true,
  "top_k": 4,
  "min_similarity_score": 0.25
}
```

When `use_llm` is `false`, the endpoint returns a deterministic
reviewer briefing. When `use_llm` is `true`, Gemini is used if
`GEMINI_API_KEY` is configured; otherwise the endpoint safely falls back
to the deterministic briefing. The result is decision support only.

## Human Review And Audit

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/claims/{claim_id}/review` | Record review decision |
| `GET` | `/claims/{claim_id}/reviews` | List review decisions |
| `PATCH` | `/claims/{claim_id}/documents/{document_id}/fields/{field_name}` | Correct extracted field |
| `GET` | `/claims/{claim_id}/audit-log` | List audit events |

Review decisions:

- `normal_review`
- `request_documents`
- `escalate_investigation`
- `data_correction`
- `policy_review`
- `closed_demo`
