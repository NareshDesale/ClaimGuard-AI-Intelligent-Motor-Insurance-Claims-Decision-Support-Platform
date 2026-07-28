from __future__ import annotations

import json
import time
from typing import Any

from google import genai
from google.genai import types

from src.assessment.service import found_field_values
from src.config import get_settings


PROMPT_VERSION = "claim_assistant_v1"
MAX_CONTEXT_CHARS = 12000


def _compact_json(payload: dict[str, Any]) -> str:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        default=str,
        indent=2,
    )

    if len(text) <= MAX_CONTEXT_CHARS:
        return text

    return text[:MAX_CONTEXT_CHARS].rstrip() + "\n... [truncated]"


def build_claim_context(
    claim_metadata: dict[str, Any],
    documents: list[dict[str, Any]],
    validation_documents: list[dict[str, Any]],
    completeness_result: dict[str, Any],
    validation_result: dict[str, Any] | None = None,
    assessment_result: dict[str, Any] | None = None,
    policy_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a safe claim context for deterministic or LLM briefing."""

    failed_rules = [
        rule
        for rule in (validation_result or {}).get("results", [])
        if rule.get("status") == "failed"
    ]
    not_evaluable_rules = [
        rule
        for rule in (validation_result or {}).get("results", [])
        if rule.get("status") == "not_evaluable"
    ]

    return {
        "claim": {
            "claim_id": claim_metadata.get("claim_id"),
            "policy_number": claim_metadata.get("policy_number"),
            "customer_name": claim_metadata.get("customer_name"),
            "vehicle_number": claim_metadata.get("vehicle_number"),
            "accident_date": claim_metadata.get("accident_date"),
            "reported_date": claim_metadata.get("reported_date"),
            "claimed_amount": claim_metadata.get("claimed_amount"),
            "status": claim_metadata.get("status"),
        },
        "documents": [
            {
                "document_id": document.get("document_id"),
                "document_type": document.get("document_type"),
                "original_filename": document.get("original_filename"),
                "extraction_status": document.get("extraction_status"),
                "fields_status": document.get("fields_status"),
            }
            for document in documents
        ],
        "document_completeness": completeness_result,
        "extracted_values": found_field_values(validation_documents),
        "validation": {
            "status": (validation_result or {}).get("status"),
            "rule_count": (validation_result or {}).get("rule_count", 0),
            "failed_rule_count": (
                (validation_result or {}).get("failed_rule_count", 0)
            ),
            "failed_rules": failed_rules,
            "not_evaluable_rule_count": len(not_evaluable_rules),
        },
        "assessment": {
            "status": (assessment_result or {}).get("status"),
            "recommended_next_action": (
                (assessment_result or {}).get("recommended_next_action")
            ),
            "recommendation_reasons": (
                (assessment_result or {}).get("recommendation_reasons", [])
            ),
            "fraud_risk": (assessment_result or {}).get("fraud_risk"),
        },
        "policy_context": policy_context
        or {
            "status": "not_requested",
            "sources": [],
        },
    }


def create_deterministic_brief(
    question: str,
    context: dict[str, Any],
) -> str:
    """Create a reviewer briefing without calling an LLM."""

    claim = context["claim"]
    completeness = context["document_completeness"]
    validation = context["validation"]
    assessment = context["assessment"]
    policy_context = context["policy_context"]

    lines = [
        f"Claim {claim.get('claim_id')} reviewer briefing.",
        (
            "Question: "
            f"{question.strip()}"
        ),
        (
            "Claim summary: "
            f"customer={claim.get('customer_name') or 'not recorded'}, "
            f"policy={claim.get('policy_number') or 'not recorded'}, "
            f"vehicle={claim.get('vehicle_number') or 'not recorded'}, "
            f"accident_date={claim.get('accident_date') or 'not recorded'}, "
            f"claimed_amount={claim.get('claimed_amount') or 'not recorded'}."
        ),
        (
            "Document completeness: "
            f"{completeness.get('status', 'unknown')} "
            f"({completeness.get('completion_percentage', 0)}%)."
        ),
    ]

    missing_required = completeness.get(
        "missing_required_documents",
        [],
    )
    if missing_required:
        lines.append(
            "Missing required documents: "
            + ", ".join(map(str, missing_required))
            + "."
        )

    failed_rules = validation.get("failed_rules", [])
    if failed_rules:
        lines.append(
            f"Validation issues found: {len(failed_rules)} failed rule(s)."
        )
        for rule in failed_rules[:5]:
            lines.append(
                "- "
                + str(rule.get("severity", "unknown")).upper()
                + ": "
                + str(rule.get("message", rule.get("rule_id")))
            )
    else:
        lines.append("Validation issues found: none recorded.")

    recommended_action = assessment.get("recommended_next_action")
    if recommended_action:
        lines.append(
            f"Current recommended next action: {recommended_action}."
        )

    fraud_risk = assessment.get("fraud_risk") or {}
    if fraud_risk:
        lines.append(
            "Fraud risk signal: "
            f"{fraud_risk.get('risk_level', 'not assessed')} "
            f"(status={fraud_risk.get('status', 'unknown')})."
        )

    if policy_context.get("sources"):
        pages = sorted(
            {
                str(source.get("page"))
                for source in policy_context["sources"]
                if source.get("page") is not None
            }
        )
        lines.append(
            "Policy context included from page(s): "
            + ", ".join(pages)
            + "."
        )
    elif policy_context.get("status") == "retrieved":
        lines.append(
            "Policy context was requested but no sufficient policy "
            "sources were retrieved."
        )

    lines.append(
        "Safety note: this is decision support only; a human reviewer "
        "must make the final claim decision."
    )

    return "\n".join(lines)


def generate_llm_answer(
    question: str,
    context: dict[str, Any],
) -> tuple[str, str]:
    """Generate a grounded claim-assistant answer with Gemini."""

    settings = get_settings()

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing from the .env file."
        )

    client = genai.Client(api_key=settings.gemini_api_key)
    context_json = _compact_json(context)

    prompt = f"""
You are ClaimGuard AI's claim review assistant.

The user is asking about one motor-insurance claim. Use only the
provided claim context. Do not use outside insurance knowledge. Do not
invent values. Do not approve or reject the claim. Do not describe a
fraud probability as proof of fraud. Keep a human reviewer in control.

USER QUESTION:
{question}

CLAIM CONTEXT:
{context_json}

PROMPT VERSION:
{PROMPT_VERSION}

Answer in clear reviewer-facing English. Include the most relevant
missing documents, inconsistencies, policy source pages, and next review
action when they are present in context.
"""

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=900,
            ),
        )
    except Exception as error:
        raise RuntimeError(
            f"Gemini claim-assistant generation failed: {error}"
        ) from error

    answer = (response.text or "").strip()

    if not answer:
        answer = "Gemini returned an empty response."

    return answer, settings.gemini_model


def run_claim_assistant(
    question: str,
    claim_metadata: dict[str, Any],
    documents: list[dict[str, Any]],
    validation_documents: list[dict[str, Any]],
    completeness_result: dict[str, Any],
    validation_result: dict[str, Any] | None = None,
    assessment_result: dict[str, Any] | None = None,
    policy_context: dict[str, Any] | None = None,
    use_llm: bool = False,
) -> dict[str, Any]:
    """Run deterministic or optional LLM-backed claim assistance."""

    start_time = time.perf_counter()
    context = build_claim_context(
        claim_metadata=claim_metadata,
        documents=documents,
        validation_documents=validation_documents,
        completeness_result=completeness_result,
        validation_result=validation_result,
        assessment_result=assessment_result,
        policy_context=policy_context,
    )
    warnings: list[str] = []
    model_name: str | None = None

    if use_llm:
        try:
            answer, model_name = generate_llm_answer(
                question=question,
                context=context,
            )
            mode = "llm_grounded"
        except RuntimeError as error:
            warnings.append(str(error))
            answer = create_deterministic_brief(
                question=question,
                context=context,
            )
            mode = "deterministic_fallback"
    else:
        answer = create_deterministic_brief(
            question=question,
            context=context,
        )
        mode = "deterministic"

    return {
        "claim_id": claim_metadata.get("claim_id"),
        "question": question,
        "answer": answer,
        "mode": mode,
        "model": model_name,
        "prompt_version": PROMPT_VERSION if use_llm else None,
        "context_summary": {
            "document_count": len(context["documents"]),
            "extracted_field_count": len(context["extracted_values"]),
            "failed_validation_rule_count": (
                context["validation"]["failed_rule_count"]
            ),
            "policy_source_count": len(
                context["policy_context"].get("sources", [])
            ),
            "recommended_next_action": (
                context["assessment"].get("recommended_next_action")
            ),
        },
        "warnings": warnings,
        "latency_ms": round(
            (time.perf_counter() - start_time) * 1000,
            2,
        ),
        "decision_support_notice": (
            "This assistant provides decision-support guidance only. "
            "A human reviewer must make the final claim decision."
        ),
    }
