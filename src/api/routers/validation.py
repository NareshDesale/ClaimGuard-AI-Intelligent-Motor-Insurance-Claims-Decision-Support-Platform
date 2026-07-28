from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.claim_context import build_validation_documents
from src.claims.repository import (
    add_audit_log,
    get_claim,
    list_claim_documents,
)
from src.database import get_db
from src.validation.completeness import (
    evaluate_document_completeness,
)
from src.validation.cross_document import (
    load_validation_result,
    run_cross_document_validation,
    save_validation_result,
)


router = APIRouter(tags=["validation"])


@router.get("/claims/{claim_id}/completeness")
def get_claim_completeness_endpoint(
    claim_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    claim = get_claim(
        db=db,
        claim_id=claim_id,
    )

    if claim is None:
        raise HTTPException(
            status_code=404,
            detail="Claim not found.",
        )

    documents = list_claim_documents(
        db=db,
        claim_id=claim_id,
    )

    return evaluate_document_completeness(
        claim_id=claim_id,
        documents=documents,
    )


@router.post("/claims/{claim_id}/validate")
def validate_claim_endpoint(
    claim_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    claim = get_claim(
        db=db,
        claim_id=claim_id,
    )

    if claim is None:
        raise HTTPException(
            status_code=404,
            detail="Claim not found.",
        )

    documents = list_claim_documents(
        db=db,
        claim_id=claim_id,
    )
    validation_documents = build_validation_documents(
        claim_id=claim_id,
        documents=documents,
    )
    result = run_cross_document_validation(
        claim_id=claim_id,
        documents=validation_documents,
    )

    save_validation_result(
        claim_id=claim_id,
        result=result,
    )

    add_audit_log(
        db=db,
        claim_id=claim_id,
        event_type="validation",
        event_data={
            "rule_count": result["rule_count"],
            "failed_rule_count": result["failed_rule_count"],
        },
    )
    db.commit()

    return result


@router.get("/claims/{claim_id}/validation")
def get_claim_validation_endpoint(
    claim_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    claim = get_claim(
        db=db,
        claim_id=claim_id,
    )

    if claim is None:
        raise HTTPException(
            status_code=404,
            detail="Claim not found.",
        )

    try:
        return load_validation_result(
            claim_id=claim_id,
        )
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
