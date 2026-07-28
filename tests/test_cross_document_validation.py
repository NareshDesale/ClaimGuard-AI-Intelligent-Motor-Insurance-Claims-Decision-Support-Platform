from pathlib import Path

from src.validation import cross_document
from src.validation.cross_document import (
    load_validation_result,
    run_cross_document_validation,
    save_validation_result,
)


def found(value: object) -> dict[str, object]:
    return {
        "status": "found",
        "value": value,
        "raw_value": str(value),
        "confidence": 0.9,
        "source_page": 1,
        "evidence": f"value {value}",
    }


def doc(
    document_id: str,
    document_type: str,
    fields: dict[str, object],
) -> dict[str, object]:
    return {
        "document_id": document_id,
        "document_type": document_type,
        "fields": fields,
    }


def result_for(
    documents: list[dict[str, object]],
    rule_id: str,
) -> dict[str, object]:
    result = run_cross_document_validation(
        claim_id="CLM-VAL-001",
        documents=documents,
    )

    return next(
        rule
        for rule in result["results"]
        if rule["rule_id"] == rule_id
    )


def base_fields() -> dict[str, object]:
    return {
        "policy_number": found("POL-1"),
        "vehicle_registration_number": found("MH12AB1234"),
        "insured_name": found("Asha Rao"),
        "customer_name": found("Asha Rao"),
        "accident_date": found("2026-08-12"),
        "policy_start_date": found("2026-01-01"),
        "policy_expiry_date": found("2026-12-31"),
        "invoice_date": found("2026-08-14"),
        "invoice_number": found("INV-1"),
        "claim_amount": found(10000.0),
        "repair_amount": found(9800.0),
    }


def test_vehicle_registration_mismatch() -> None:
    fields_a = base_fields()
    fields_b = base_fields() | {
        "vehicle_registration_number": found("MH12XY9999")
    }

    rule = result_for(
        [
            doc("a", "claim_form", fields_a),
            doc("b", "policy_document", fields_b),
        ],
        "vehicle_registration_mismatch",
    )

    assert rule["status"] == "failed"


def test_policy_number_mismatch() -> None:
    fields_b = base_fields() | {
        "policy_number": found("POL-2")
    }

    rule = result_for(
        [
            doc("a", "claim_form", base_fields()),
            doc("b", "policy_document", fields_b),
        ],
        "policy_number_mismatch",
    )

    assert rule["status"] == "failed"


def test_insured_name_mismatch() -> None:
    fields_b = base_fields() | {
        "insured_name": found("Ravi Rao")
    }

    rule = result_for(
        [
            doc("a", "claim_form", base_fields()),
            doc("b", "policy_document", fields_b),
        ],
        "insured_name_mismatch",
    )

    assert rule["status"] == "failed"


def test_accident_date_mismatch() -> None:
    fields_b = base_fields() | {
        "accident_date": found("2026-08-13")
    }

    rule = result_for(
        [
            doc("a", "claim_form", base_fields()),
            doc("b", "accident_report", fields_b),
        ],
        "accident_date_mismatch",
    )

    assert rule["status"] == "failed"


def test_claim_amount_versus_invoice_amount_inconsistency() -> None:
    fields_a = base_fields() | {
        "claim_amount": found(12000.0),
        "repair_amount": found(10000.0),
    }

    rule = result_for(
        [doc("a", "repair_invoice", fields_a)],
        "claim_amount_invoice_amount_consistency",
    )

    assert rule["status"] == "failed"


def test_accident_before_policy_start() -> None:
    fields_a = base_fields() | {
        "accident_date": found("2025-12-31"),
        "policy_start_date": found("2026-01-01"),
    }

    rule = result_for(
        [doc("a", "claim_form", fields_a)],
        "accident_before_policy_start",
    )

    assert rule["status"] == "failed"


def test_accident_after_policy_expiry() -> None:
    fields_a = base_fields() | {
        "accident_date": found("2027-01-01"),
        "policy_expiry_date": found("2026-12-31"),
    }

    rule = result_for(
        [doc("a", "claim_form", fields_a)],
        "accident_after_policy_expiry",
    )

    assert rule["status"] == "failed"


def test_invoice_date_before_accident_date() -> None:
    fields_a = base_fields() | {
        "accident_date": found("2026-08-12"),
        "invoice_date": found("2026-08-11"),
    }

    rule = result_for(
        [doc("a", "repair_invoice", fields_a)],
        "invoice_date_before_accident_date",
    )

    assert rule["status"] == "failed"


def test_duplicate_invoice_number() -> None:
    rule = result_for(
        [
            doc("a", "repair_invoice", base_fields()),
            doc("b", "repair_invoice", base_fields()),
        ],
        "duplicate_invoice_number",
    )

    assert rule["status"] == "failed"


def test_duplicate_document_id() -> None:
    rule = result_for(
        [
            doc("a", "claim_form", base_fields()),
            doc("a", "policy_document", base_fields()),
        ],
        "duplicate_document_id",
    )

    assert rule["status"] == "failed"


def test_missing_critical_fields() -> None:
    rule = result_for(
        [
            doc(
                "a",
                "claim_form",
                {
                    "policy_number": found("POL-1"),
                },
            )
        ],
        "missing_critical_fields",
    )

    assert rule["status"] == "failed"
    assert "vehicle_registration_number" in rule["message"]


def test_invalid_date_ranges() -> None:
    fields_a = base_fields() | {
        "policy_start_date": found("2027-01-01"),
        "policy_expiry_date": found("2026-12-31"),
    }

    rule = result_for(
        [doc("a", "policy_document", fields_a)],
        "invalid_date_ranges",
    )

    assert rule["status"] == "failed"


def test_unusually_high_claimed_amount() -> None:
    fields_a = base_fields() | {
        "claim_amount": found(600000.0),
    }

    rule = result_for(
        [doc("a", "claim_form", fields_a)],
        "unusually_high_claimed_amount",
    )

    assert rule["status"] == "failed"


def test_inconsistent_customer_identity() -> None:
    fields_a = base_fields() | {
        "insured_name": found("Asha Rao"),
        "customer_name": found("Ravi Rao"),
    }

    rule = result_for(
        [doc("a", "claim_form", fields_a)],
        "inconsistent_customer_identity",
    )

    assert rule["status"] == "failed"


def test_save_and_load_validation_result(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        cross_document,
        "VALIDATION_ROOT",
        tmp_path,
    )
    result = run_cross_document_validation(
        claim_id="CLM-VAL-002",
        documents=[doc("a", "claim_form", base_fields())],
    )

    save_validation_result(
        claim_id="CLM-VAL-002",
        result=result,
    )
    loaded = load_validation_result(
        claim_id="CLM-VAL-002",
    )

    assert loaded["claim_id"] == "CLM-VAL-002"
    assert loaded["rule_count"] == 14
