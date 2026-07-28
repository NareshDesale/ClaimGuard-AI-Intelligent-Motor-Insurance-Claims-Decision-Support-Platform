import json
from datetime import date
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_ROOT = PROJECT_ROOT / "data" / "validation"

CRITICAL_FIELDS = (
    "policy_number",
    "vehicle_registration_number",
    "accident_date",
    "claim_amount",
)

HIGH_CLAIM_AMOUNT_THRESHOLD = 500000.0


def normalize_text(value: Any) -> str:
    return str(value).strip().upper()


def parse_date(value: Any) -> date | None:
    if value is None:
        return None

    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def parse_amount(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def rule_result(
    rule_id: str,
    severity: str,
    status: str,
    message: str,
    documents: list[str] | None = None,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "status": status,
        "message": message,
        "documents": documents or [],
        "evidence": evidence or [],
    }


def document_id(document: dict[str, Any]) -> str:
    return str(document.get("document_id", "unknown"))


def document_label(
    occurrence: dict[str, Any],
) -> str:
    return (
        f"{occurrence['document_id']}"
        f"({occurrence.get('document_type', 'unknown')})"
    )


def field_value(
    field_data: dict[str, Any],
) -> Any:
    if field_data.get("status") != "found":
        return None

    return field_data.get("value")


def collect_field_occurrences(
    documents: list[dict[str, Any]],
    field_name: str,
) -> list[dict[str, Any]]:
    occurrences: list[dict[str, Any]] = []

    for document in documents:
        fields = document.get("fields", {})
        field_data = fields.get(field_name, {})
        value = field_value(field_data)

        if value is None:
            continue

        occurrences.append(
            {
                "document_id": document_id(document),
                "document_type": document.get(
                    "document_type",
                    "unknown",
                ),
                "field_name": field_name,
                "value": value,
                "raw_value": field_data.get("raw_value"),
                "evidence": field_data.get("evidence"),
            }
        )

    return occurrences


def values_by_normalized_text(
    occurrences: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}

    for occurrence in occurrences:
        normalized_value = normalize_text(
            occurrence["value"]
        )
        grouped.setdefault(
            normalized_value,
            [],
        ).append(occurrence)

    return grouped


def evidence_from_occurrences(
    occurrences: list[dict[str, Any]],
) -> list[str]:
    return [
        (
            f"{document_label(occurrence)} "
            f"{occurrence['field_name']}="
            f"{occurrence['value']}"
        )
        for occurrence in occurrences
    ]


def compare_single_field_consistency(
    documents: list[dict[str, Any]],
    field_name: str,
    rule_id: str,
    severity: str,
    display_name: str,
) -> dict[str, Any]:
    occurrences = collect_field_occurrences(
        documents=documents,
        field_name=field_name,
    )

    if len(occurrences) < 2:
        return rule_result(
            rule_id=rule_id,
            severity=severity,
            status="not_evaluable",
            message=(
                f"At least two {display_name} values are "
                "needed for cross-document comparison."
            ),
            documents=[
                occurrence["document_id"]
                for occurrence in occurrences
            ],
            evidence=evidence_from_occurrences(
                occurrences
            ),
        )

    grouped_values = values_by_normalized_text(
        occurrences
    )

    if len(grouped_values) == 1:
        return rule_result(
            rule_id=rule_id,
            severity=severity,
            status="passed",
            message=f"{display_name} is consistent.",
            documents=[
                occurrence["document_id"]
                for occurrence in occurrences
            ],
            evidence=evidence_from_occurrences(
                occurrences
            ),
        )

    return rule_result(
        rule_id=rule_id,
        severity=severity,
        status="failed",
        message=f"{display_name} mismatch detected.",
        documents=[
            occurrence["document_id"]
            for occurrence in occurrences
        ],
        evidence=evidence_from_occurrences(
            occurrences
        ),
    )


def validate_claim_amount_vs_invoice(
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    claim_amounts = collect_field_occurrences(
        documents,
        "claim_amount",
    )
    repair_amounts = collect_field_occurrences(
        documents,
        "repair_amount",
    )

    if not claim_amounts or not repair_amounts:
        return rule_result(
            rule_id="claim_amount_invoice_amount_consistency",
            severity="medium",
            status="not_evaluable",
            message=(
                "Claim amount and invoice or repair amount are "
                "both required for comparison."
            ),
            documents=[
                occurrence["document_id"]
                for occurrence in claim_amounts + repair_amounts
            ],
            evidence=evidence_from_occurrences(
                claim_amounts + repair_amounts
            ),
        )

    max_claim_amount = max(
        parse_amount(occurrence["value"]) or 0.0
        for occurrence in claim_amounts
    )
    max_repair_amount = max(
        parse_amount(occurrence["value"]) or 0.0
        for occurrence in repair_amounts
    )
    tolerance = max(
        100.0,
        max_repair_amount * 0.05,
    )

    occurrences = claim_amounts + repair_amounts

    if max_claim_amount > max_repair_amount + tolerance:
        return rule_result(
            rule_id="claim_amount_invoice_amount_consistency",
            severity="medium",
            status="failed",
            message=(
                "Claim amount is materially higher than the "
                "invoice or repair amount."
            ),
            documents=[
                occurrence["document_id"]
                for occurrence in occurrences
            ],
            evidence=evidence_from_occurrences(
                occurrences
            ),
        )

    return rule_result(
        rule_id="claim_amount_invoice_amount_consistency",
        severity="medium",
        status="passed",
        message=(
            "Claim amount is consistent with the invoice or "
            "repair amount."
        ),
        documents=[
            occurrence["document_id"]
            for occurrence in occurrences
        ],
        evidence=evidence_from_occurrences(
            occurrences
        ),
    )


def validate_date_relationship(
    documents: list[dict[str, Any]],
    left_field: str,
    right_field: str,
    rule_id: str,
    severity: str,
    failure_message: str,
    passed_message: str,
    comparison: str,
) -> dict[str, Any]:
    left_occurrences = collect_field_occurrences(
        documents,
        left_field,
    )
    right_occurrences = collect_field_occurrences(
        documents,
        right_field,
    )
    occurrences = left_occurrences + right_occurrences

    if not left_occurrences or not right_occurrences:
        return rule_result(
            rule_id=rule_id,
            severity=severity,
            status="not_evaluable",
            message=(
                f"{left_field} and {right_field} are required "
                "for this validation."
            ),
            documents=[
                occurrence["document_id"]
                for occurrence in occurrences
            ],
            evidence=evidence_from_occurrences(
                occurrences
            ),
        )

    left_dates = [
        parse_date(occurrence["value"])
        for occurrence in left_occurrences
    ]
    right_dates = [
        parse_date(occurrence["value"])
        for occurrence in right_occurrences
    ]

    if any(value is None for value in left_dates + right_dates):
        return rule_result(
            rule_id=rule_id,
            severity=severity,
            status="failed",
            message="One or more date values could not be parsed.",
            documents=[
                occurrence["document_id"]
                for occurrence in occurrences
            ],
            evidence=evidence_from_occurrences(
                occurrences
            ),
        )

    if comparison == "before":
        left = min(
            value
            for value in left_dates
            if value is not None
        )
        right = max(
            value
            for value in right_dates
            if value is not None
        )
        failed = left < right
    else:
        left = max(
            value
            for value in left_dates
            if value is not None
        )
        right = min(
            value
            for value in right_dates
            if value is not None
        )
        failed = left > right

    if failed:
        return rule_result(
            rule_id=rule_id,
            severity=severity,
            status="failed",
            message=failure_message,
            documents=[
                occurrence["document_id"]
                for occurrence in occurrences
            ],
            evidence=evidence_from_occurrences(
                occurrences
            ),
        )

    return rule_result(
        rule_id=rule_id,
        severity=severity,
        status="passed",
        message=passed_message,
        documents=[
            occurrence["document_id"]
            for occurrence in occurrences
        ],
        evidence=evidence_from_occurrences(
            occurrences
        ),
    )


def validate_duplicate_invoice_number(
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    occurrences = collect_field_occurrences(
        documents,
        "invoice_number",
    )

    if len(occurrences) < 2:
        return rule_result(
            rule_id="duplicate_invoice_number",
            severity="medium",
            status="not_evaluable",
            message=(
                "At least two invoice numbers are needed to "
                "detect duplicates."
            ),
            documents=[
                occurrence["document_id"]
                for occurrence in occurrences
            ],
            evidence=evidence_from_occurrences(
                occurrences
            ),
        )

    grouped = values_by_normalized_text(
        occurrences
    )
    duplicates = [
        occurrence
        for group in grouped.values()
        if len(group) > 1
        for occurrence in group
    ]

    if duplicates:
        return rule_result(
            rule_id="duplicate_invoice_number",
            severity="medium",
            status="failed",
            message="Duplicate invoice number detected.",
            documents=[
                occurrence["document_id"]
                for occurrence in duplicates
            ],
            evidence=evidence_from_occurrences(
                duplicates
            ),
        )

    return rule_result(
        rule_id="duplicate_invoice_number",
        severity="medium",
        status="passed",
        message="No duplicate invoice numbers were detected.",
        documents=[
            occurrence["document_id"]
            for occurrence in occurrences
        ],
        evidence=evidence_from_occurrences(
            occurrences
        ),
    )


def validate_duplicate_document_id(
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    document_ids = [
        document_id(document)
        for document in documents
    ]
    duplicate_ids = sorted(
        {
            value
            for value in document_ids
            if document_ids.count(value) > 1
        }
    )

    if duplicate_ids:
        return rule_result(
            rule_id="duplicate_document_id",
            severity="high",
            status="failed",
            message="Duplicate document ID detected.",
            documents=duplicate_ids,
            evidence=[
                f"document_id={value}"
                for value in duplicate_ids
            ],
        )

    return rule_result(
        rule_id="duplicate_document_id",
        severity="high",
        status="passed",
        message="Document IDs are unique.",
        documents=document_ids,
        evidence=[
            f"document_id={value}"
            for value in document_ids
        ],
    )


def validate_missing_critical_fields(
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    missing_fields = [
        field_name
        for field_name in CRITICAL_FIELDS
        if not collect_field_occurrences(
            documents,
            field_name,
        )
    ]

    if missing_fields:
        return rule_result(
            rule_id="missing_critical_fields",
            severity="high",
            status="failed",
            message=(
                "Missing critical fields: "
                + ", ".join(missing_fields)
            ),
            documents=[
                document_id(document)
                for document in documents
            ],
            evidence=[
                f"missing={field_name}"
                for field_name in missing_fields
            ],
        )

    return rule_result(
        rule_id="missing_critical_fields",
        severity="high",
        status="passed",
        message="Critical claim fields are present.",
        documents=[
            document_id(document)
            for document in documents
        ],
        evidence=[
            f"present={field_name}"
            for field_name in CRITICAL_FIELDS
        ],
    )


def validate_invalid_date_ranges(
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    start_occurrences = collect_field_occurrences(
        documents,
        "policy_start_date",
    )
    expiry_occurrences = collect_field_occurrences(
        documents,
        "policy_expiry_date",
    )
    occurrences = start_occurrences + expiry_occurrences

    if not start_occurrences or not expiry_occurrences:
        return rule_result(
            rule_id="invalid_date_ranges",
            severity="high",
            status="not_evaluable",
            message=(
                "Policy start and expiry dates are required "
                "to validate date ranges."
            ),
            documents=[
                occurrence["document_id"]
                for occurrence in occurrences
            ],
            evidence=evidence_from_occurrences(
                occurrences
            ),
        )

    start_dates = [
        parse_date(occurrence["value"])
        for occurrence in start_occurrences
    ]
    expiry_dates = [
        parse_date(occurrence["value"])
        for occurrence in expiry_occurrences
    ]

    if any(value is None for value in start_dates + expiry_dates):
        return rule_result(
            rule_id="invalid_date_ranges",
            severity="high",
            status="failed",
            message="One or more policy dates could not be parsed.",
            documents=[
                occurrence["document_id"]
                for occurrence in occurrences
            ],
            evidence=evidence_from_occurrences(
                occurrences
            ),
        )

    latest_start = max(
        value
        for value in start_dates
        if value is not None
    )
    earliest_expiry = min(
        value
        for value in expiry_dates
        if value is not None
    )

    if latest_start > earliest_expiry:
        return rule_result(
            rule_id="invalid_date_ranges",
            severity="high",
            status="failed",
            message="Policy start date is after policy expiry date.",
            documents=[
                occurrence["document_id"]
                for occurrence in occurrences
            ],
            evidence=evidence_from_occurrences(
                occurrences
            ),
        )

    return rule_result(
        rule_id="invalid_date_ranges",
        severity="high",
        status="passed",
        message="Policy date range is valid.",
        documents=[
            occurrence["document_id"]
            for occurrence in occurrences
        ],
        evidence=evidence_from_occurrences(
            occurrences
        ),
    )


def validate_unusually_high_claim_amount(
    documents: list[dict[str, Any]],
    threshold: float = HIGH_CLAIM_AMOUNT_THRESHOLD,
) -> dict[str, Any]:
    occurrences = collect_field_occurrences(
        documents,
        "claim_amount",
    )

    if not occurrences:
        return rule_result(
            rule_id="unusually_high_claimed_amount",
            severity="medium",
            status="not_evaluable",
            message="Claim amount is required for this validation.",
        )

    high_amounts = [
        occurrence
        for occurrence in occurrences
        if (parse_amount(occurrence["value"]) or 0.0) > threshold
    ]

    if high_amounts:
        return rule_result(
            rule_id="unusually_high_claimed_amount",
            severity="medium",
            status="failed",
            message=(
                "Claimed amount is above the configured review "
                f"threshold of {threshold:.2f}."
            ),
            documents=[
                occurrence["document_id"]
                for occurrence in high_amounts
            ],
            evidence=evidence_from_occurrences(
                high_amounts
            ),
        )

    return rule_result(
        rule_id="unusually_high_claimed_amount",
        severity="medium",
        status="passed",
        message="Claimed amount is within the configured threshold.",
        documents=[
            occurrence["document_id"]
            for occurrence in occurrences
        ],
        evidence=evidence_from_occurrences(
            occurrences
        ),
    )


def validate_inconsistent_customer_identity(
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    occurrences = (
        collect_field_occurrences(documents, "insured_name")
        + collect_field_occurrences(documents, "customer_name")
    )

    if len(occurrences) < 2:
        return rule_result(
            rule_id="inconsistent_customer_identity",
            severity="medium",
            status="not_evaluable",
            message=(
                "At least two customer or insured names are "
                "needed for identity consistency validation."
            ),
            documents=[
                occurrence["document_id"]
                for occurrence in occurrences
            ],
            evidence=evidence_from_occurrences(
                occurrences
            ),
        )

    grouped = values_by_normalized_text(
        occurrences
    )

    if len(grouped) > 1:
        return rule_result(
            rule_id="inconsistent_customer_identity",
            severity="medium",
            status="failed",
            message=(
                "Customer or insured identity values are "
                "inconsistent across documents."
            ),
            documents=[
                occurrence["document_id"]
                for occurrence in occurrences
            ],
            evidence=evidence_from_occurrences(
                occurrences
            ),
        )

    return rule_result(
        rule_id="inconsistent_customer_identity",
        severity="medium",
        status="passed",
        message="Customer identity is consistent.",
        documents=[
            occurrence["document_id"]
            for occurrence in occurrences
        ],
        evidence=evidence_from_occurrences(
            occurrences
        ),
    )


def run_cross_document_validation(
    claim_id: str,
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    results = [
        compare_single_field_consistency(
            documents,
            "vehicle_registration_number",
            "vehicle_registration_mismatch",
            "high",
            "Vehicle registration number",
        ),
        compare_single_field_consistency(
            documents,
            "policy_number",
            "policy_number_mismatch",
            "high",
            "Policy number",
        ),
        compare_single_field_consistency(
            documents,
            "insured_name",
            "insured_name_mismatch",
            "medium",
            "Insured name",
        ),
        compare_single_field_consistency(
            documents,
            "accident_date",
            "accident_date_mismatch",
            "medium",
            "Accident date",
        ),
        validate_claim_amount_vs_invoice(documents),
        validate_date_relationship(
            documents,
            "accident_date",
            "policy_start_date",
            "accident_before_policy_start",
            "high",
            "Accident date is before policy start date.",
            "Accident date is not before policy start date.",
            "before",
        ),
        validate_date_relationship(
            documents,
            "accident_date",
            "policy_expiry_date",
            "accident_after_policy_expiry",
            "high",
            "Accident date is after policy expiry date.",
            "Accident date is not after policy expiry date.",
            "after",
        ),
        validate_date_relationship(
            documents,
            "invoice_date",
            "accident_date",
            "invoice_date_before_accident_date",
            "medium",
            "Invoice date is before accident date.",
            "Invoice date is not before accident date.",
            "before",
        ),
        validate_duplicate_invoice_number(documents),
        validate_duplicate_document_id(documents),
        validate_missing_critical_fields(documents),
        validate_invalid_date_ranges(documents),
        validate_unusually_high_claim_amount(documents),
        validate_inconsistent_customer_identity(documents),
    ]

    failed_count = sum(
        1
        for result in results
        if result["status"] == "failed"
    )
    high_severity_failed_count = sum(
        1
        for result in results
        if result["status"] == "failed"
        and result["severity"] == "high"
    )

    return {
        "claim_id": claim_id,
        "status": (
            "failed"
            if failed_count
            else "passed"
        ),
        "rule_count": len(results),
        "failed_rule_count": failed_count,
        "high_severity_failed_rule_count": high_severity_failed_count,
        "results": results,
    }


def save_validation_result(
    claim_id: str,
    result: dict[str, Any],
) -> Path:
    output_directory = VALIDATION_ROOT
    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )
    output_path = output_directory / f"{claim_id}.json"

    try:
        result["validation_result_path"] = str(
            output_path.relative_to(PROJECT_ROOT)
        )
    except ValueError:
        result["validation_result_path"] = str(output_path)

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            result,
            output_file,
            indent=2,
            ensure_ascii=False,
        )

    return output_path


def load_validation_result(
    claim_id: str,
) -> dict[str, Any]:
    result_path = VALIDATION_ROOT / f"{claim_id}.json"

    if not result_path.exists():
        raise FileNotFoundError(
            "No saved validation result was found for this claim."
        )

    with result_path.open(
        "r",
        encoding="utf-8",
    ) as result_file:
        return json.load(result_file)
