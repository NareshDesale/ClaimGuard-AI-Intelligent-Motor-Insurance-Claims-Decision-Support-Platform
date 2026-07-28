from src.validation.completeness import (
    evaluate_document_completeness,
)


def test_no_documents_is_incomplete() -> None:
    result = evaluate_document_completeness(
        claim_id="CLM-COMP-001",
        documents=[],
    )

    assert result["status"] == "incomplete"
    assert result["uploaded_document_types"] == []
    assert result["missing_required_documents"] == [
        "claim_form",
        "policy_document",
        "repair_invoice",
    ]
    assert result["completion_percentage"] == 0


def test_partially_complete_claim() -> None:
    result = evaluate_document_completeness(
        claim_id="CLM-COMP-002",
        documents=[
            {"document_type": "claim_form"},
            {"document_type": "repair_invoice"},
        ],
    )

    assert result["status"] == "incomplete"
    assert result["uploaded_document_types"] == [
        "claim_form",
        "repair_invoice",
    ]
    assert result["missing_required_documents"] == [
        "policy_document",
    ]
    assert result["completion_percentage"] == 66.67


def test_complete_claim_with_required_documents() -> None:
    result = evaluate_document_completeness(
        claim_id="CLM-COMP-003",
        documents=[
            "claim_form",
            "policy_document",
            "repair_invoice",
        ],
    )

    assert result["status"] == "complete"
    assert result["missing_required_documents"] == []
    assert result["missing_conditional_documents"] == [
        "accident_report",
        "identity_document",
    ]
    assert result["completion_percentage"] == 100


def test_duplicate_document_types_are_counted_once() -> None:
    result = evaluate_document_completeness(
        claim_id="CLM-COMP-004",
        documents=[
            {"document_type": "claim_form"},
            {"document_type": "claim_form"},
            {"document_type": "policy_document"},
            {"document_type": "repair_invoice"},
            {"document_type": "vehicle_image"},
        ],
    )

    assert result["status"] == "complete"
    assert result["uploaded_document_types"] == [
        "claim_form",
        "policy_document",
        "repair_invoice",
        "vehicle_image",
    ]
    assert result["completion_percentage"] == 100
