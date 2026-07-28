from dataclasses import dataclass
from typing import Any, Iterable


REQUIRED_DOCUMENT_TYPES = (
    "claim_form",
    "policy_document",
    "repair_invoice",
)

CONDITIONAL_DOCUMENT_TYPES = (
    "accident_report",
    "identity_document",
)

OPTIONAL_DOCUMENT_TYPES = (
    "vehicle_image",
    "other",
)


@dataclass(frozen=True)
class DocumentRequirementRules:
    required: tuple[str, ...] = REQUIRED_DOCUMENT_TYPES
    conditional: tuple[str, ...] = CONDITIONAL_DOCUMENT_TYPES
    optional: tuple[str, ...] = OPTIONAL_DOCUMENT_TYPES


def extract_document_type(document: str | dict[str, Any] | Any) -> str:
    """
    Read a document type from a string, dictionary, or ORM object.
    """

    if isinstance(document, str):
        document_type = document
    elif isinstance(document, dict):
        document_type = str(document.get("document_type", ""))
    else:
        document_type = str(
            getattr(document, "document_type", "")
        )

    return document_type.strip().lower()


def unique_document_types(
    documents: Iterable[str | dict[str, Any] | Any],
) -> list[str]:
    document_types = {
        extract_document_type(document)
        for document in documents
    }

    document_types.discard("")

    return sorted(document_types)


def build_recommendations(
    missing_required_documents: list[str],
    missing_conditional_documents: list[str],
) -> list[str]:
    recommendations: list[str] = []

    if missing_required_documents:
        recommendations.append(
            "Request the missing required documents before "
            "continuing claim assessment."
        )

    if missing_conditional_documents:
        recommendations.append(
            "Check whether conditional documents are applicable "
            "to this claim and request them if needed."
        )

    if not recommendations:
        recommendations.append(
            "Required documents are present. Continue with "
            "extraction, validation, and human review."
        )

    return recommendations


def evaluate_document_completeness(
    claim_id: str,
    documents: Iterable[str | dict[str, Any] | Any],
    rules: DocumentRequirementRules | None = None,
) -> dict[str, Any]:
    """
    Evaluate whether a claim has the core documents needed for
    assessment.

    Conditional documents are reported separately because their
    applicability depends on claim context that may not be known yet.
    They do not block the core complete/incomplete status.
    """

    active_rules = rules or DocumentRequirementRules()
    uploaded_document_types = unique_document_types(
        documents
    )
    uploaded_set = set(uploaded_document_types)

    missing_required_documents = [
        document_type
        for document_type in active_rules.required
        if document_type not in uploaded_set
    ]

    missing_conditional_documents = [
        document_type
        for document_type in active_rules.conditional
        if document_type not in uploaded_set
    ]

    required_count = len(active_rules.required)
    present_required_count = (
        required_count
        - len(missing_required_documents)
    )
    completion_percentage = (
        100
        if required_count == 0
        else round(
            (present_required_count / required_count) * 100,
            2,
        )
    )

    status = (
        "complete"
        if not missing_required_documents
        else "incomplete"
    )

    return {
        "claim_id": claim_id,
        "status": status,
        "uploaded_document_types": uploaded_document_types,
        "missing_required_documents": missing_required_documents,
        "missing_conditional_documents": missing_conditional_documents,
        "completion_percentage": completion_percentage,
        "recommendations": build_recommendations(
            missing_required_documents=missing_required_documents,
            missing_conditional_documents=missing_conditional_documents,
        ),
    }
