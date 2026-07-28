# Limitations

ClaimGuard AI is a demo decision-support system. It is not validated for
production insurance decisions.

## Decision Support Only

Fraud scores are signals for human reviewers. They are not proof of
fraud and must not be used as automatic approval or rejection decisions.

Allowed assessment actions are reviewer workflow recommendations, not
claim outcomes:

- `ready_for_normal_review`
- `request_more_documents`
- `manual_policy_review`
- `fraud_investigation_review`
- `data_correction_required`

## Synthetic And Demo Data

The project is intended for synthetic/demo documents and datasets. Do
not upload real customer data or identity documents without proper
privacy, legal, and security controls.

## Fraud Model Limits

- The model expects fixed training features.
- Uploaded documents do not naturally provide all model features.
- Manual feature input may be required.
- The model may not be calibrated for new regions, products, or time
  periods.
- Explainability is limited unless a stable model-compatible method is
  added and validated.

## RAG Limits

- Policy answers depend on the indexed PDF and retrieval quality.
- RAG answers are not legal advice.
- The system refuses unrelated or insufficient-evidence questions where
  possible, but retrieval can still miss relevant text.
- Gemini integration depends on external API availability and
  configured credentials.

## OCR And Extraction Limits

- OCR accuracy depends on image quality, language, layout, and scan
  quality.
- Structured field extraction is deterministic and rule-based, so it can
  miss unusual layouts.
- The extractor returns `not_found` instead of guessing.

## Security Limits

The upload flow validates filename, extension, MIME type, signature,
size, PDF page count, and image dimensions. It does not include
antivirus scanning, malware sandboxing, authentication, authorization,
or encryption-at-rest controls.

## Deployment Limits

- SQLite is suitable for local MVP/demo use only.
- Docker Compose must work before Kubernetes is treated as deployable.
- Kubernetes manifests require a real image registry strategy and
  cluster-specific model/vector artifact handling.
- Secrets examples are placeholders only.
