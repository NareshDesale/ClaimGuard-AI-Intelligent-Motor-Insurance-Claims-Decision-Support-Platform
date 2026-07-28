# Demo Script

This script demonstrates the reviewer workflow with synthetic/demo
claim data. Do not use real customer data.

## 1. Generate Demo Data

Generate safe synthetic documents first:

```bash
python scripts/generate_demo_data.py
```

The script writes ignored runtime files under `data/demo/` and creates
a `manifest.json` describing every scenario.

## 2. Start Backend

```bash
uvicorn app:app --reload
```

Confirm health:

```bash
curl http://localhost:8000/health
```

## 3. Start Dashboard

```bash
streamlit run frontend/streamlit_app.py
```

Open:

```text
http://localhost:8501
```

## 4. Create Claim

Use the Streamlit `New Claim` page or call:

```bash
curl -X POST http://localhost:8000/claims \
  -H "Content-Type: application/json" \
  -d "{\"claim_id\":\"CLM-DEMO-001\",\"policy_number\":\"POL-2026-001\",\"customer_name\":\"Demo Customer\",\"vehicle_number\":\"MH12AB1234\",\"accident_date\":\"2026-08-12\",\"reported_date\":\"2026-08-14\",\"claimed_amount\":42500,\"status\":\"open\"}"
```

## 5. Upload Documents

Upload at least:

- `claim_form`
- `policy_document`
- `repair_invoice`

Supported file types are PDF, PNG, JPG, and JPEG.

## 6. Extract Text

For each uploaded document, run text extraction from the Claim Details
page or call:

```bash
curl -X POST http://localhost:8000/claims/CLM-DEMO-001/documents/DOCUMENT_ID/extract
```

## 7. Extract Structured Fields

```bash
curl -X POST http://localhost:8000/claims/CLM-DEMO-001/documents/DOCUMENT_ID/fields
```

Review extracted values and evidence snippets.

## 8. Check Completeness

```bash
curl http://localhost:8000/claims/CLM-DEMO-001/completeness
```

Expected outcome for a complete demo claim:

```text
status: complete
completion_percentage: 100
```

## 9. Run Cross-Document Validation

```bash
curl -X POST http://localhost:8000/claims/CLM-DEMO-001/validate
```

Check failed rules and severity.

## 10. Run Risk Assessment

Provide any model features that cannot be derived from claim metadata or
documents:

```bash
curl -X POST http://localhost:8000/claims/CLM-DEMO-001/risk-assessment \
  -H "Content-Type: application/json" \
  -d "{\"manual_features\":{\"Age\":34}}"
```

Treat the output as a reviewer signal only.

## 11. Ask A Policy Question

```bash
curl -X POST http://localhost:8000/rag/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"What third-party liabilities are covered?\",\"top_k\":4,\"claim_id\":\"CLM-DEMO-001\"}"
```

Review answer citations and source pages.

## 12. Generate Assessment

```bash
curl -X POST http://localhost:8000/claims/CLM-DEMO-001/assessment \
  -H "Content-Type: application/json" \
  -d "{\"manual_features\":{\"Age\":34}}"
```

The recommendation is a next reviewer action, not a claim decision.

## 13. Human Review

Record the reviewer decision:

```bash
curl -X POST http://localhost:8000/claims/CLM-DEMO-001/review \
  -H "Content-Type: application/json" \
  -d "{\"reviewer_name\":\"Reviewer One\",\"decision\":\"normal_review\",\"comment\":\"Demo review complete.\"}"
```

## 14. Audit Log

```bash
curl http://localhost:8000/claims/CLM-DEMO-001/audit-log
```

Confirm that major actions were recorded.
