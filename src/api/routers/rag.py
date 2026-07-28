from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.dependencies import get_policy_rag_service
from src.api.schemas import PolicyQuestionRequest
from src.claims.repository import (
    add_audit_log,
    get_claim,
)
from src.database import get_db


router = APIRouter(tags=["rag"])


@router.get("/rag/health")
def rag_health() -> dict[str, Any]:
    """Check whether policy RAG dependencies are ready."""

    try:
        service = get_policy_rag_service()
        return service.health()

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"RAG health check failed: {error}",
        ) from error


@router.post("/rag/ask")
def ask_policy_question(
    request: PolicyQuestionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve relevant policy clauses and generate a grounded answer."""

    try:
        service = get_policy_rag_service()
        result = service.answer(
            question=request.question,
            top_k=request.top_k,
            min_similarity_score=request.min_similarity_score,
        )

        if request.claim_id:
            claim = get_claim(db=db, claim_id=request.claim_id)

            if claim is None:
                raise HTTPException(
                    status_code=404,
                    detail="Claim not found for RAG audit logging.",
                )

            add_audit_log(
                db=db,
                claim_id=request.claim_id,
                event_type="rag_query",
                event_data={
                    "question_length": len(request.question),
                    "top_k": request.top_k,
                    "min_similarity_score": (
                        request.min_similarity_score
                    ),
                    "answerable": result.get("answerable"),
                    "retrieved_chunk_count": result.get(
                        "retrieved_chunk_count"
                    ),
                    "latency_ms": result.get("latency_ms"),
                    "model": result.get("model"),
                    "prompt_version": result.get(
                        "prompt_version"
                    ),
                },
            )
            db.commit()

        return result

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Policy RAG failed: {error}",
        ) from error


@router.post("/rag/retrieve")
def retrieve_policy_sources(
    request: PolicyQuestionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve policy sources without calling Gemini."""

    try:
        service = get_policy_rag_service()
        result = service.retrieve_with_metadata(
            question=request.question,
            top_k=request.top_k,
            min_similarity_score=request.min_similarity_score,
        )

        if request.claim_id:
            claim = get_claim(db=db, claim_id=request.claim_id)

            if claim is None:
                raise HTTPException(
                    status_code=404,
                    detail="Claim not found for RAG audit logging.",
                )

            add_audit_log(
                db=db,
                claim_id=request.claim_id,
                event_type="rag_query",
                event_data={
                    "question_length": len(request.question),
                    "top_k": request.top_k,
                    "min_similarity_score": (
                        request.min_similarity_score
                    ),
                    "answerable": result.get("answerable"),
                    "retrieved_chunk_count": result.get(
                        "retrieved_chunk_count"
                    ),
                    "latency_ms": result.get("latency_ms"),
                    "retrieval_method": result.get(
                        "retrieval_method"
                    ),
                },
            )
            db.commit()

        return result

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Policy retrieval failed: {error}",
        ) from error
