from __future__ import annotations

from typing import Any

from src.claims.repository import model_to_dict
from src.documents.fields import load_field_result


def build_validation_documents(
    claim_id: str,
    documents: list[Any],
) -> list[dict[str, Any]]:
    """Build validation-ready document payloads from DB documents."""

    validation_documents: list[dict[str, Any]] = []

    for document in documents:
        document_data = model_to_dict(document)
        document_id = document_data["document_id"]

        try:
            field_result = load_field_result(
                claim_id=claim_id,
                document_id=document_id,
            )
            fields = field_result.get(
                "fields",
                {},
            )
        except FileNotFoundError:
            fields = {}

        validation_documents.append(
            {
                "document_id": document_id,
                "document_type": document_data.get(
                    "document_type",
                    "unknown",
                ),
                "fields": fields,
            }
        )

    return validation_documents
