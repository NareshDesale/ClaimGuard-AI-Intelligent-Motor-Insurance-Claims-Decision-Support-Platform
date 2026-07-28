from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.schemas import (
    ClaimCreateRequest,
    ClaimUpdateRequest,
)
from src.claims.repository import (
    create_claim,
    get_claim,
    list_claim_documents,
    list_claims,
    model_to_dict,
    update_claim,
)
from src.database import get_db


router = APIRouter(tags=["claims"])


@router.post("/claims")
def create_claim_endpoint(
    request: ClaimCreateRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    existing_claim = get_claim(
        db=db,
        claim_id=request.claim_id,
    )

    if existing_claim is not None:
        raise HTTPException(
            status_code=409,
            detail="A claim with this claim_id already exists.",
        )

    claim = create_claim(
        db=db,
        claim_data=request.model_dump(),
    )

    return model_to_dict(claim)


@router.get("/claims")
def list_claims_endpoint(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    claims = list_claims(db=db)

    return {
        "claims": [
            model_to_dict(claim)
            for claim in claims
        ],
        "count": len(claims),
    }


@router.get("/claims/{claim_id}")
def get_claim_endpoint(
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

    return model_to_dict(claim)


@router.patch("/claims/{claim_id}")
def update_claim_endpoint(
    claim_id: str,
    request: ClaimUpdateRequest,
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

    updates = request.model_dump(
        exclude_unset=True,
    )

    if not updates:
        return model_to_dict(claim)

    updated_claim = update_claim(
        db=db,
        claim=claim,
        updates=updates,
    )

    return model_to_dict(updated_claim)


@router.get("/claims/{claim_id}/documents")
def list_claim_documents_endpoint(
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

    return {
        "claim_id": claim_id,
        "documents": [
            model_to_dict(document)
            for document in documents
        ],
        "count": len(documents),
    }
