from pathlib import Path

from src.assessment import service as assessment_service
from src.assessment.service import (
    generate_claim_assessment,
    load_assessment_result,
    save_assessment_result,
)


def completeness(status: str) -> dict[str, object]:
    return {
        "claim_id": "CLM-A-001",
        "status": status,
        "uploaded_document_types": [],
        "missing_required_documents": (
            ["repair_invoice"]
            if status == "incomplete"
            else []
        ),
        "missing_conditional_documents": [],
        "completion_percentage": 66.67
        if status == "incomplete"
        else 100,
        "recommendations": [],
    }


def validation(*rules: dict[str, object]) -> dict[str, object]:
    return {
        "claim_id": "CLM-A-001",
        "status": "failed"
        if rules
        else "passed",
        "rule_count": len(rules),
        "failed_rule_count": len(rules),
        "high_severity_failed_rule_count": len(
            [
                rule
                for rule in rules
                if rule["severity"] == "high"
            ]
        ),
        "results": list(rules),
    }


def failed_rule(severity: str) -> dict[str, object]:
    return {
        "rule_id": f"{severity}_issue",
        "severity": severity,
        "status": "failed",
        "message": "Issue found.",
        "documents": ["doc-1"],
        "evidence": ["evidence"],
    }


def claim_metadata() -> dict[str, object]:
    return {
        "claim_id": "CLM-A-001",
        "policy_number": "POL-1",
        "customer_name": "Asha Rao",
        "vehicle_number": "MH12AB1234",
        "accident_date": "2026-08-12",
        "reported_date": "2026-08-14",
        "claimed_amount": 10000.0,
        "status": "open",
    }


def documents() -> list[dict[str, object]]:
    return [
        {
            "document_id": "doc-1",
            "document_type": "claim_form",
        }
    ]


def validation_documents() -> list[dict[str, object]]:
    return [
        {
            "document_id": "doc-1",
            "document_type": "claim_form",
            "fields": {
                "policy_number": {
                    "status": "found",
                    "value": "POL-1",
                    "raw_value": "POL-1",
                    "confidence": 0.9,
                    "source_page": 1,
                    "evidence": "Policy Number: POL-1",
                }
            },
        }
    ]


def assessment_for(
    completeness_status: str = "complete",
    validation_result: dict[str, object] | None = None,
    fraud_risk: dict[str, object] | None = None,
    policy_findings: dict[str, object] | None = None,
) -> dict[str, object]:
    return generate_claim_assessment(
        claim_metadata=claim_metadata(),
        documents=documents(),
        validation_documents=validation_documents(),
        completeness_result=completeness(completeness_status),
        validation_result=validation_result or validation(),
        fraud_risk=fraud_risk,
        policy_findings=policy_findings,
    )


def test_assessment_requests_more_documents_first() -> None:
    result = assessment_for(
        completeness_status="incomplete",
        validation_result=validation(failed_rule("high")),
    )

    assert result["recommended_next_action"] == (
        "request_more_documents"
    )


def test_assessment_requires_data_correction_for_high_validation() -> None:
    result = assessment_for(
        validation_result=validation(failed_rule("high")),
    )

    assert result["recommended_next_action"] == (
        "data_correction_required"
    )


def test_assessment_escalates_high_fraud_risk() -> None:
    result = assessment_for(
        fraud_risk={
            "status": "assessed",
            "risk_level": "HIGH",
        }
    )

    assert result["recommended_next_action"] == (
        "fraud_investigation_review"
    )


def test_assessment_requests_policy_review_when_rag_insufficient() -> None:
    result = assessment_for(
        policy_findings={
            "question": "Is this covered?",
            "answerable": False,
            "answer": "Insufficient evidence.",
            "sources": [],
        }
    )

    assert result["recommended_next_action"] == (
        "manual_policy_review"
    )


def test_assessment_ready_for_normal_review() -> None:
    result = assessment_for()

    assert result["recommended_next_action"] == (
        "ready_for_normal_review"
    )
    assert "decision-support" in result["decision_support_notice"]
    assert result["extracted_values"]["policy_number"][0][
        "value"
    ] == "POL-1"


def test_save_and_load_assessment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        assessment_service,
        "ASSESSMENT_ROOT",
        tmp_path,
    )
    result = assessment_for()

    save_assessment_result(
        claim_id="CLM-A-001",
        result=result,
    )
    loaded = load_assessment_result("CLM-A-001")

    assert loaded["claim_id"] == "CLM-A-001"
    assert loaded["assessment_result_path"]
