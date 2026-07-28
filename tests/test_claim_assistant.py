from src.llm.claim_assistant import (
    build_claim_context,
    run_claim_assistant,
)


def sample_context_inputs():
    claim_metadata = {
        "claim_id": "CLM-AI-001",
        "policy_number": "POL-001",
        "customer_name": "Demo Customer",
        "vehicle_number": "MH12AB1234",
        "accident_date": "2026-07-01",
        "claimed_amount": 45000.0,
        "status": "open",
    }
    documents = [
        {
            "document_id": "doc-1",
            "document_type": "claim_form",
            "original_filename": "claim.pdf",
            "extraction_status": "completed",
            "fields_status": "completed",
        }
    ]
    validation_documents = [
        {
            "document_id": "doc-1",
            "document_type": "claim_form",
            "fields": {
                "policy_number": {
                    "status": "found",
                    "value": "POL-001",
                    "raw_value": "POL-001",
                    "confidence": 0.95,
                    "source_page": 1,
                    "evidence": "Policy Number: POL-001",
                }
            },
        }
    ]
    completeness_result = {
        "status": "incomplete",
        "completion_percentage": 33,
        "missing_required_documents": [
            "policy_document",
            "repair_invoice",
        ],
    }
    validation_result = {
        "status": "validation_completed",
        "rule_count": 2,
        "failed_rule_count": 1,
        "results": [
            {
                "rule_id": "missing_critical_fields",
                "severity": "high",
                "status": "failed",
                "message": "Critical claim fields are missing.",
            }
        ],
    }
    assessment_result = {
        "status": "assessment_generated",
        "recommended_next_action": "request_more_documents",
        "recommendation_reasons": [
            "Required claim documents are missing.",
        ],
        "fraud_risk": {
            "status": "manual_features_required",
            "risk_level": "NOT_ASSESSED",
        },
    }

    return (
        claim_metadata,
        documents,
        validation_documents,
        completeness_result,
        validation_result,
        assessment_result,
    )


def test_build_claim_context_limits_to_safe_summary() -> None:
    (
        claim_metadata,
        documents,
        validation_documents,
        completeness_result,
        validation_result,
        assessment_result,
    ) = sample_context_inputs()

    context = build_claim_context(
        claim_metadata=claim_metadata,
        documents=documents,
        validation_documents=validation_documents,
        completeness_result=completeness_result,
        validation_result=validation_result,
        assessment_result=assessment_result,
    )

    assert context["claim"]["claim_id"] == "CLM-AI-001"
    assert context["documents"][0]["document_type"] == "claim_form"
    assert "policy_number" in context["extracted_values"]
    assert context["validation"]["failed_rule_count"] == 1
    assert (
        context["assessment"]["recommended_next_action"]
        == "request_more_documents"
    )


def test_run_claim_assistant_deterministic_mode() -> None:
    (
        claim_metadata,
        documents,
        validation_documents,
        completeness_result,
        validation_result,
        assessment_result,
    ) = sample_context_inputs()

    result = run_claim_assistant(
        question="What should the reviewer check next?",
        claim_metadata=claim_metadata,
        documents=documents,
        validation_documents=validation_documents,
        completeness_result=completeness_result,
        validation_result=validation_result,
        assessment_result=assessment_result,
        use_llm=False,
    )

    assert result["mode"] == "deterministic"
    assert "Missing required documents" in result["answer"]
    assert result["context_summary"]["document_count"] == 1
    assert (
        result["context_summary"]["recommended_next_action"]
        == "request_more_documents"
    )
    assert "human reviewer" in result["decision_support_notice"]


def test_run_claim_assistant_falls_back_without_gemini_key(
    monkeypatch,
) -> None:
    class SettingsWithoutGemini:
        gemini_api_key = None
        gemini_model = "mock-gemini"

    monkeypatch.setattr(
        "src.llm.claim_assistant.get_settings",
        lambda: SettingsWithoutGemini(),
    )

    (
        claim_metadata,
        documents,
        validation_documents,
        completeness_result,
        validation_result,
        assessment_result,
    ) = sample_context_inputs()

    result = run_claim_assistant(
        question="Summarize this claim.",
        claim_metadata=claim_metadata,
        documents=documents,
        validation_documents=validation_documents,
        completeness_result=completeness_result,
        validation_result=validation_result,
        assessment_result=assessment_result,
        use_llm=True,
    )

    assert result["mode"] == "deterministic_fallback"
    assert result["warnings"]
    assert "GEMINI_API_KEY" in result["warnings"][0]
