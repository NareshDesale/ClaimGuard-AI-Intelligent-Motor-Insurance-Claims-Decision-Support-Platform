import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import (
    AuditLog,
    Claim,
    Document,
    FieldResult,
    ReviewDecision,
    utc_now,
)

SENSITIVE_EVENT_KEYS = {
    "api_key",
    "apikey",
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
}


def model_to_dict(model: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}

    for column in model.__table__.columns:
        value = getattr(model, column.name)

        if hasattr(value, "isoformat"):
            value = value.isoformat()

        result[column.name] = value

    return result


def redact_event_data(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}

        for key, nested_value in value.items():
            normalized_key = str(key).lower()

            if normalized_key in SENSITIVE_EVENT_KEYS:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_event_data(nested_value)

        return redacted

    if isinstance(value, list):
        return [
            redact_event_data(item)
            for item in value
        ]

    return value


def safe_event_data(
    event_data: dict[str, Any] | None,
) -> str | None:
    if event_data is None:
        return None

    return json.dumps(
        redact_event_data(event_data),
        ensure_ascii=False,
        default=str,
    )


def add_audit_log(
    db: Session,
    claim_id: str,
    event_type: str,
    event_data: dict[str, Any] | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        claim_id=claim_id,
        event_type=event_type,
        event_data=safe_event_data(event_data),
    )

    db.add(audit_log)

    return audit_log


def audit_log_to_dict(
    audit_log: AuditLog,
) -> dict[str, Any]:
    result = model_to_dict(audit_log)
    raw_event_data = result.get("event_data")

    if raw_event_data:
        try:
            result["event_data"] = json.loads(raw_event_data)
        except json.JSONDecodeError:
            result["event_data"] = raw_event_data

    return result


def list_audit_logs(
    db: Session,
    claim_id: str,
) -> list[AuditLog]:
    return list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.claim_id == claim_id)
            .order_by(AuditLog.created_at.desc())
        )
    )


def get_claim(
    db: Session,
    claim_id: str,
) -> Claim | None:
    return db.scalar(
        select(Claim).where(
            Claim.claim_id == claim_id
        )
    )


def create_claim(
    db: Session,
    claim_data: dict[str, Any],
) -> Claim:
    claim = Claim(**claim_data)

    db.add(claim)
    db.flush()
    add_audit_log(
        db=db,
        claim_id=claim.claim_id,
        event_type="claim_created",
        event_data={
            "claim_id": claim.claim_id,
            "status": claim.status,
        },
    )
    db.commit()
    db.refresh(claim)

    return claim


def get_or_create_claim(
    db: Session,
    claim_id: str,
) -> Claim:
    claim = get_claim(
        db=db,
        claim_id=claim_id,
    )

    if claim is not None:
        return claim

    return create_claim(
        db=db,
        claim_data={
            "claim_id": claim_id,
            "status": "open",
        },
    )


def list_claims(
    db: Session,
) -> list[Claim]:
    return list(
        db.scalars(
            select(Claim).order_by(
                Claim.created_at.desc()
            )
        )
    )


def update_claim(
    db: Session,
    claim: Claim,
    updates: dict[str, Any],
) -> Claim:
    for field_name, value in updates.items():
        setattr(
            claim,
            field_name,
            value,
        )

    claim.updated_at = utc_now()
    add_audit_log(
        db=db,
        claim_id=claim.claim_id,
        event_type="claim_updated",
        event_data={
            "updated_fields": sorted(updates.keys()),
        },
    )
    db.commit()
    db.refresh(claim)

    return claim


def create_document(
    db: Session,
    document_data: dict[str, Any],
) -> Document:
    document = Document(
        document_id=document_data["document_id"],
        claim_id=document_data["claim_id"],
        document_type=document_data["document_type"],
        original_filename=document_data["original_filename"],
        stored_filename=document_data["stored_filename"],
        content_type=document_data.get("content_type"),
        size_bytes=document_data["size_bytes"],
        storage_path=document_data["storage_path"],
        extraction_status="not_started",
        fields_status="not_started",
    )

    db.add(document)
    db.flush()
    add_audit_log(
        db=db,
        claim_id=document.claim_id,
        event_type="document_uploaded",
        event_data={
            "document_id": document.document_id,
            "document_type": document.document_type,
            "original_filename": document.original_filename,
            "size_bytes": document.size_bytes,
        },
    )
    db.commit()
    db.refresh(document)

    return document


def list_claim_documents(
    db: Session,
    claim_id: str,
) -> list[Document]:
    return list(
        db.scalars(
            select(Document)
            .where(Document.claim_id == claim_id)
            .order_by(Document.created_at.desc())
        )
    )


def get_document(
    db: Session,
    claim_id: str,
    document_id: str,
) -> Document | None:
    return db.scalar(
        select(Document).where(
            Document.claim_id == claim_id,
            Document.document_id == document_id,
        )
    )


def mark_document_extracted(
    db: Session,
    claim_id: str,
    document_id: str,
) -> None:
    get_or_create_claim(
        db=db,
        claim_id=claim_id,
    )

    document = get_document(
        db=db,
        claim_id=claim_id,
        document_id=document_id,
    )

    if document is not None:
        document.extraction_status = "extracted"

    add_audit_log(
        db=db,
        claim_id=claim_id,
        event_type="text_extracted",
        event_data={
            "document_id": document_id,
        },
    )
    db.commit()


def save_field_results(
    db: Session,
    claim_id: str,
    document_id: str,
    fields: dict[str, Any],
) -> None:
    get_or_create_claim(
        db=db,
        claim_id=claim_id,
    )

    document = get_document(
        db=db,
        claim_id=claim_id,
        document_id=document_id,
    )

    if document is not None:
        db.query(FieldResult).filter(
            FieldResult.document_id == document_id
        ).delete()

        for field_name, field_data in fields.items():
            db.add(
                FieldResult(
                    document_id=document_id,
                    field_name=field_name,
                    value=(
                        None
                        if field_data.get("value") is None
                        else str(field_data.get("value"))
                    ),
                    raw_value=field_data.get("raw_value"),
                    confidence=float(
                        field_data.get("confidence", 0.0)
                    ),
                    source_page=field_data.get("source_page"),
                    evidence=field_data.get("evidence"),
                )
            )

        document.fields_status = "fields_extracted"

    add_audit_log(
        db=db,
        claim_id=claim_id,
        event_type="field_extraction",
        event_data={
            "document_id": document_id,
            "field_count": len(fields),
        },
    )
    db.commit()


def create_review_decision(
    db: Session,
    claim_id: str,
    reviewer_name: str,
    decision: str,
    comment: str | None,
) -> ReviewDecision:
    review_decision = ReviewDecision(
        claim_id=claim_id,
        reviewer_name=reviewer_name,
        decision=decision,
        comments=comment,
    )

    db.add(review_decision)
    db.flush()
    add_audit_log(
        db=db,
        claim_id=claim_id,
        event_type="review_decision",
        event_data={
            "reviewer_name": reviewer_name,
            "decision": decision,
        },
    )
    db.commit()
    db.refresh(review_decision)

    return review_decision


def list_review_decisions(
    db: Session,
    claim_id: str,
) -> list[ReviewDecision]:
    return list(
        db.scalars(
            select(ReviewDecision)
            .where(ReviewDecision.claim_id == claim_id)
            .order_by(ReviewDecision.created_at.desc())
        )
    )


def get_field_result(
    db: Session,
    document_id: str,
    field_name: str,
) -> FieldResult | None:
    return db.scalar(
        select(FieldResult).where(
            FieldResult.document_id == document_id,
            FieldResult.field_name == field_name,
        )
    )


def correct_field_result(
    db: Session,
    claim_id: str,
    document_id: str,
    field_name: str,
    reviewer_name: str,
    corrected_value: str,
) -> FieldResult:
    field_result = get_field_result(
        db=db,
        document_id=document_id,
        field_name=field_name,
    )

    if field_result is None:
        raise ValueError(
            "No structured field result was found for this "
            "document and field name."
        )

    original_value = field_result.value
    field_result.reviewer_corrected_value = corrected_value
    field_result.reviewed_at = utc_now()

    add_audit_log(
        db=db,
        claim_id=claim_id,
        event_type="human_correction",
        event_data={
            "document_id": document_id,
            "field_name": field_name,
            "reviewer_name": reviewer_name,
            "original_value": original_value,
            "corrected_value": corrected_value,
        },
    )
    db.commit()
    db.refresh(field_result)

    return field_result
