from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.claim_context import build_validation_documents
from src.api.dependencies import (
    MODEL_PATH,
    get_expected_features,
    get_policy_rag_service,
    load_fraud_model,
)
from src.api.schemas import (
    AssessmentRequest,
    ClaimAssistantRequest,
)
from src.assessment.service import (
    generate_claim_assessment,
    load_assessment_result,
    save_assessment_result,
)
from src.claims.repository import (
    add_audit_log,
    get_claim,
    list_claim_documents,
    model_to_dict,
)
from src.database import get_db
from src.llm.claim_assistant import run_claim_assistant
from src.risk.service import run_claim_risk_assessment
from src.validation.completeness import evaluate_document_completeness
from src.validation.cross_document import (
    load_validation_result,
    run_cross_document_validation,
    save_validation_result,
)


router = APIRouter(tags=["assessment"])


@router.post("/claims/{claim_id}/assessment")
def generate_claim_assessment_endpoint(
    claim_id: str,
    request: AssessmentRequest | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    claim = get_claim(db=db, claim_id=claim_id)

    if claim is None:
        raise HTTPException(
            status_code=404,
            detail="Claim not found.",
        )

    documents = list_claim_documents(db=db, claim_id=claim_id)
    document_payloads = [
        model_to_dict(document)
        for document in documents
    ]
    validation_documents = build_validation_documents(
        claim_id=claim_id,
        documents=documents,
    )
    completeness_result = evaluate_document_completeness(
        claim_id=claim_id,
        documents=documents,
    )

    try:
        validation_result = load_validation_result(claim_id)
    except FileNotFoundError:
        validation_result = run_cross_document_validation(
            claim_id=claim_id,
            documents=validation_documents,
        )
        save_validation_result(
            claim_id=claim_id,
            result=validation_result,
        )

    request_data = request or AssessmentRequest()
    try:
        fraud_risk = run_claim_risk_assessment(
            claim_id=claim_id,
            claim=model_to_dict(claim),
            documents=validation_documents,
            manual_features=request_data.manual_features,
            expected_features=get_expected_features(),
            model=load_fraud_model(),
            model_path=MODEL_PATH,
        )
    except RuntimeError as error:
        fraud_risk = {
            "claim_id": claim_id,
            "status": "model_unavailable",
            "fraud_probability": None,
            "prediction": None,
            "risk_level": "NOT_ASSESSED",
            "threshold": 0.5,
            "model_version": None,
            "features_used": {},
            "missing_features": get_expected_features(),
            "warnings": [str(error)],
            "important_risk_factors": [],
        }

    result = generate_claim_assessment(
        claim_metadata=model_to_dict(claim),
        documents=document_payloads,
        validation_documents=validation_documents,
        completeness_result=completeness_result,
        validation_result=validation_result,
        fraud_risk=fraud_risk,
        policy_findings=request_data.policy_findings,
    )
    save_assessment_result(
        claim_id=claim_id,
        result=result,
    )

    add_audit_log(
        db=db,
        claim_id=claim_id,
        event_type="assessment_generation",
        event_data={
            "recommended_next_action": result[
                "recommended_next_action"
            ],
            "inconsistency_count": len(result["inconsistencies"]),
        },
    )
    db.commit()

    return result


@router.get("/claims/{claim_id}/assessment")
def get_claim_assessment_endpoint(
    claim_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    claim = get_claim(db=db, claim_id=claim_id)

    if claim is None:
        raise HTTPException(
            status_code=404,
            detail="Claim not found.",
        )

    try:
        return load_assessment_result(claim_id)
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error


@router.post("/claims/{claim_id}/assistant")
def run_claim_assistant_endpoint(
    claim_id: str,
    request: ClaimAssistantRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Answer reviewer questions using claim context, validation,
    assessment, and optional policy RAG sources.
    """

    claim = get_claim(db=db, claim_id=claim_id)

    if claim is None:
        raise HTTPException(
            status_code=404,
            detail="Claim not found.",
        )

    documents = list_claim_documents(db=db, claim_id=claim_id)
    document_payloads = [
        model_to_dict(document)
        for document in documents
    ]
    validation_documents = build_validation_documents(
        claim_id=claim_id,
        documents=documents,
    )
    completeness_result = evaluate_document_completeness(
        claim_id=claim_id,
        documents=documents,
    )

    try:
        validation_result = load_validation_result(claim_id)
    except FileNotFoundError:
        validation_result = run_cross_document_validation(
            claim_id=claim_id,
            documents=validation_documents,
        )

    try:
        assessment_result = load_assessment_result(claim_id)
    except FileNotFoundError:
        assessment_result = None

    policy_context: dict[str, Any] | None = None
    policy_warning: str | None = None

    if request.include_policy_context:
        try:
            service = get_policy_rag_service()
            policy_context = service.retrieve_with_metadata(
                question=request.question,
                top_k=request.top_k,
                min_similarity_score=request.min_similarity_score,
            )
            policy_context["status"] = "retrieved"
        except Exception as error:
            policy_warning = (
                "Policy context could not be retrieved: "
                f"{error}"
            )
            policy_context = {
                "status": "unavailable",
                "sources": [],
                "warning": policy_warning,
            }

    result = run_claim_assistant(
        question=request.question,
        claim_metadata=model_to_dict(claim),
        documents=document_payloads,
        validation_documents=validation_documents,
        completeness_result=completeness_result,
        validation_result=validation_result,
        assessment_result=assessment_result,
        policy_context=policy_context,
        use_llm=request.use_llm,
    )

    if policy_warning:
        result["warnings"].append(policy_warning)

    add_audit_log(
        db=db,
        claim_id=claim_id,
        event_type="claim_assistant_query",
        event_data={
            "question_length": len(request.question),
            "use_llm": request.use_llm,
            "include_policy_context": request.include_policy_context,
            "mode": result["mode"],
            "latency_ms": result["latency_ms"],
            "warning_count": len(result["warnings"]),
        },
    )
    db.commit()

    return result
