# Data Dictionary

ClaimGuard AI stores registry and review metadata in SQLite and stores
large/generated document artifacts as files.

## Database Tables

### `claims`

| Column | Description |
| --- | --- |
| `id` | Internal numeric primary key |
| `claim_id` | External claim identifier |
| `policy_number` | Policy number supplied or extracted |
| `customer_name` | Customer or insured name |
| `vehicle_number` | Vehicle registration number |
| `accident_date` | Accident date as text |
| `reported_date` | Claim reported date as text |
| `claimed_amount` | Claimed amount when available |
| `status` | Claim workflow status |
| `created_at` | Creation timestamp |
| `updated_at` | Last update timestamp |

### `documents`

| Column | Description |
| --- | --- |
| `id` | Internal numeric primary key |
| `document_id` | Server-generated document identifier |
| `claim_id` | Parent claim identifier |
| `document_type` | Supported claim document type |
| `original_filename` | Sanitized original filename |
| `stored_filename` | Server-generated stored filename |
| `content_type` | Uploaded MIME type |
| `size_bytes` | Uploaded file size |
| `storage_path` | Relative storage path |
| `extraction_status` | Text extraction status |
| `fields_status` | Structured field status |
| `created_at` | Upload timestamp |

### `field_results`

| Column | Description |
| --- | --- |
| `id` | Internal numeric primary key |
| `document_id` | Source document identifier |
| `field_name` | Extracted field key |
| `value` | Normalized extracted value |
| `raw_value` | Raw matched value |
| `confidence` | Rule confidence score |
| `source_page` | Source page number |
| `evidence` | Short evidence text |
| `reviewer_corrected_value` | Human correction |
| `reviewed_at` | Correction timestamp |

### `review_decisions`

| Column | Description |
| --- | --- |
| `id` | Internal numeric primary key |
| `claim_id` | Reviewed claim |
| `reviewer_name` | Reviewer name |
| `decision` | Human review decision |
| `comments` | Reviewer comments |
| `created_at` | Review timestamp |

### `audit_logs`

| Column | Description |
| --- | --- |
| `id` | Internal numeric primary key |
| `claim_id` | Claim associated with the event |
| `event_type` | Structured event type |
| `event_data` | Redacted JSON metadata |
| `created_at` | Event timestamp |

## Extracted Structured Fields

The deterministic field extractor attempts these fields:

| Field | Meaning |
| --- | --- |
| `policy_number` | Insurance policy number |
| `claim_number` | Claim reference number |
| `insured_name` | Insured person name |
| `customer_name` | Customer name |
| `vehicle_registration_number` | Vehicle registration number |
| `vehicle_make` | Vehicle make |
| `vehicle_model` | Vehicle model |
| `chassis_number` | Chassis/VIN-like number |
| `engine_number` | Engine number |
| `accident_date` | Accident date |
| `accident_time` | Accident time |
| `accident_location` | Accident location |
| `policy_start_date` | Policy start date |
| `policy_expiry_date` | Policy expiry date |
| `invoice_number` | Repair invoice number |
| `invoice_date` | Repair invoice date |
| `claim_amount` | Claimed amount |
| `repair_amount` | Repair amount |
| `garage_name` | Repair garage name |
| `driving_licence_number` | Driving licence number |
| `driver_name` | Driver name |
| `police_report_number` | Police/FIR report number |

Each field result includes:

- `status`
- `value`
- `raw_value`
- `confidence`
- `source_page`
- `evidence`

The extractor returns `not_found` instead of inventing values.

## File Storage

| Path | Purpose |
| --- | --- |
| `data/uploads/` | Uploaded PDFs and images |
| `data/extracted/` | Text extraction JSON |
| `data/fields/` | Structured field JSON |
| `data/validation/` | Cross-document validation JSON |
| `data/assessments/` | Consolidated assessment JSON |
| `models/` | Local trained model artifacts |
| `vector_store/` | Generated FAISS policy index |
