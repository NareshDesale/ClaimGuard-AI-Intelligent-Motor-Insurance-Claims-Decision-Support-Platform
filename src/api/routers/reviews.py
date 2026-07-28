from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.schemas import (
    ALLOWED_REVIEW_DECISIONS,
    FieldCorrectionRequest,
    ReviewDecisionRequest,
)
from src.claims.repository import (
    audit_log_to_dict,
    correct_field_result,
    create_review_decision,
    get_claim,
    get_document,
    list_audit_logs,
    list_review_decisions,
    model_to_dict,
)
from src.database import get_db


router = APIRouter(tags=["reviews"])


@router.post("/claims/{claim_id}/review")
def create_claim_review_endpoint(
    claim_id: str,
    request: ReviewDecisionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    claim = get_claim(db=db, claim_id=claim_id)

    if claim is None:
        raise HTTPException(
            status_code=404,
            detail="Claim not found.",
        )

    decision = request.decision.strip()

    if decision not in ALLOWED_REVIEW_DECISIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid review decision. Allowed values are: "
                + ", ".join(sorted(ALLOWED_REVIEW_DECISIONS))
            ),
        )

    review_decision = create_review_decision(
        db=db,
        claim_id=claim_id,
        reviewer_name=request.reviewer_name,
        decision=decision,
        comment=request.comment,
    )

    result = model_to_dict(review_decision)
    result["comment"] = result.pop("comments")

    return result


@router.get("/claims/{claim_id}/reviews")
def list_claim_reviews_endpoint(
    claim_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    claim = get_claim(db=db, claim_id=claim_id)

    if claim is None:
        raise HTTPException(
            status_code=404,
            detail="Claim not found.",
        )

    reviews = []

    for review_decision in list_review_decisions(
        db=db,
        claim_id=claim_id,
    ):
        review_data = model_to_dict(review_decision)
        review_data["comment"] = review_data.pop("comments")
        reviews.append(review_data)

    return {
        "claim_id": claim_id,
        "reviews": reviews,
        "count": len(reviews),
    }


@router.get("/claims/{claim_id}/audit-log")
def get_claim_audit_log_endpoint(
    claim_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    claim = get_claim(db=db, claim_id=claim_id)

    if claim is None:
        raise HTTPException(
            status_code=404,
            detail="Claim not found.",
        )

    audit_logs = [
        audit_log_to_dict(audit_log)
        for audit_log in list_audit_logs(
            db=db,
            claim_id=claim_id,
        )
    ]

    return {
        "claim_id": claim_id,
        "audit_logs": audit_logs,
        "count": len(audit_logs),
    }


@router.patch(
    "/claims/{claim_id}/documents/"
    "{document_id}/fields/{field_name}"
)
def correct_document_field_endpoint(
    claim_id: str,
    document_id: str,
    field_name: str,
    request: FieldCorrectionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    claim = get_claim(db=db, claim_id=claim_id)

    if claim is None:
        raise HTTPException(
            status_code=404,
            detail="Claim not found.",
        )

    document = get_document(
        db=db,
        claim_id=claim_id,
        document_id=document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    try:
        field_result = correct_field_result(
            db=db,
            claim_id=claim_id,
            document_id=document_id,
            field_name=field_name,
            reviewer_name=request.reviewer_name,
            corrected_value=request.corrected_value,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    return {
        "claim_id": claim_id,
        "document_id": document_id,
        "field_name": field_name,
        "original_value": field_result.value,
        "corrected_value": field_result.reviewer_corrected_value,
        "reviewer_name": request.reviewer_name,
        "reviewed_at": (
            field_result.reviewed_at.isoformat()
            if field_result.reviewed_at
            else None
        ),
        "status": "corrected",
    }
