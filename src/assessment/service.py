import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSESSMENT_ROOT = PROJECT_ROOT / "data" / "assessments"

ALLOWED_NEXT_ACTIONS = {
    "ready_for_normal_review",
    "request_more_documents",
    "manual_policy_review",
    "fraud_investigation_review",
    "data_correction_required",
}


def found_field_values(
    validation_documents: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    extracted_values: dict[str, list[dict[str, Any]]] = {}

    for document in validation_documents:
        document_id = str(document.get("document_id", "unknown"))
        document_type = str(document.get("document_type", "unknown"))

        for field_name, field_data in document.get("fields", {}).items():
            if field_data.get("status") != "found":
                continue

            extracted_values.setdefault(field_name, []).append(
                {
                    "document_id": document_id,
                    "document_type": document_type,
                    "value": field_data.get("value"),
                    "raw_value": field_data.get("raw_value"),
                    "confidence": field_data.get("confidence", 0.0),
                    "source_page": field_data.get("source_page"),
                    "evidence": field_data.get("evidence"),
                }
            )

    return extracted_values


def failed_validation_rules(
    validation_result: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        rule
        for rule in validation_result.get("results", [])
        if rule.get("status") == "failed"
    ]


def summarize_policy_findings(
    policy_findings: dict[str, Any] | None,
) -> dict[str, Any]:
    if not policy_findings:
        return {
            "status": "not_requested",
            "findings": [],
            "requires_manual_policy_review": False,
        }

    answerable = policy_findings.get("answerable")

    return {
        "status": (
            "answered"
            if answerable is not False
            else "insufficient_evidence"
        ),
        "findings": policy_findings.get(
            "sources",
            policy_findings.get("findings", []),
        ),
        "requires_manual_policy_review": answerable is False,
        "answer": policy_findings.get("answer"),
        "question": policy_findings.get("question"),
    }


def recommend_next_action(
    completeness_result: dict[str, Any],
    validation_result: dict[str, Any],
    fraud_risk: dict[str, Any] | None,
    policy_findings: dict[str, Any],
) -> tuple[str, list[str]]:
    reasons: list[str] = []

    if completeness_result.get("status") == "incomplete":
        reasons.append("Required claim documents are missing.")
        return "request_more_documents", reasons

    failed_rules = failed_validation_rules(validation_result)
    high_failed_rules = [
        rule
        for rule in failed_rules
        if rule.get("severity") == "high"
    ]

    if high_failed_rules:
        reasons.append(
            "High-severity cross-document validation issues "
            "need correction or reviewer confirmation."
        )
        return "data_correction_required", reasons

    if fraud_risk and fraud_risk.get("risk_level") == "HIGH":
        reasons.append(
            "Fraud model produced a high risk signal that "
            "requires human investigation review."
        )
        return "fraud_investigation_review", reasons

    if policy_findings.get("requires_manual_policy_review"):
        reasons.append(
            "Policy RAG did not find sufficient evidence for "
            "the policy question."
        )
        return "manual_policy_review", reasons

    if failed_rules:
        reasons.append(
            "Non-blocking validation issues should be checked "
            "during normal review."
        )

    if fraud_risk and fraud_risk.get("status") == (
        "manual_features_required"
    ):
        reasons.append(
            "Fraud risk assessment could not run until manual "
            "model features are supplied."
        )

    if not reasons:
        reasons.append(
            "Required documents are present and no blocking "
            "validation or risk issues were detected."
        )

    return "ready_for_normal_review", reasons


def build_claim_summary(
    claim_metadata: dict[str, Any],
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "claim_id": claim_metadata.get("claim_id"),
        "policy_number": claim_metadata.get("policy_number"),
        "customer_name": claim_metadata.get("customer_name"),
        "vehicle_number": claim_metadata.get("vehicle_number"),
        "accident_date": claim_metadata.get("accident_date"),
        "reported_date": claim_metadata.get("reported_date"),
        "claimed_amount": claim_metadata.get("claimed_amount"),
        "status": claim_metadata.get("status"),
        "document_count": len(documents),
    }


def generate_claim_assessment(
    claim_metadata: dict[str, Any],
    documents: list[dict[str, Any]],
    validation_documents: list[dict[str, Any]],
    completeness_result: dict[str, Any],
    validation_result: dict[str, Any],
    fraud_risk: dict[str, Any] | None = None,
    policy_findings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy_summary = summarize_policy_findings(policy_findings)
    next_action, reasons = recommend_next_action(
        completeness_result=completeness_result,
        validation_result=validation_result,
        fraud_risk=fraud_risk,
        policy_findings=policy_summary,
    )

    return {
        "claim_id": claim_metadata.get("claim_id"),
        "status": "assessment_generated",
        "claim_summary": build_claim_summary(
            claim_metadata=claim_metadata,
            documents=documents,
        ),
        "document_completeness": completeness_result,
        "extracted_values": found_field_values(validation_documents),
        "inconsistencies": failed_validation_rules(validation_result),
        "fraud_risk": fraud_risk
        or {
            "status": "not_requested",
            "risk_level": "NOT_ASSESSED",
        },
        "policy_findings": policy_summary,
        "recommended_next_action": next_action,
        "recommendation_reasons": reasons,
        "allowed_next_actions": sorted(ALLOWED_NEXT_ACTIONS),
        "decision_support_notice": (
            "This decision-support assessment supports human review "
            "only. It must not automatically approve or reject real "
            "insurance claims."
        ),
    }


def save_assessment_result(
    claim_id: str,
    result: dict[str, Any],
) -> Path:
    ASSESSMENT_ROOT.mkdir(parents=True, exist_ok=True)
    output_path = ASSESSMENT_ROOT / f"{claim_id}.json"

    try:
        result["assessment_result_path"] = str(
            output_path.relative_to(PROJECT_ROOT)
        )
    except ValueError:
        result["assessment_result_path"] = str(output_path)

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(result, output_file, indent=2, ensure_ascii=False)

    return output_path


def load_assessment_result(
    claim_id: str,
) -> dict[str, Any]:
    result_path = ASSESSMENT_ROOT / f"{claim_id}.json"

    if not result_path.exists():
        raise FileNotFoundError(
            "No saved assessment result was found for this claim."
        )

    with result_path.open("r", encoding="utf-8") as result_file:
        return json.load(result_file)
