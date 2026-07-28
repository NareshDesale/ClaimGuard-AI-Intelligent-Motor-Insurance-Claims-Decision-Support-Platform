import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from sqlalchemy.orm import Session

from src.config import configure_logging
from src.api.dependencies import (
    MODEL_PATH,
    get_expected_features,
    get_fraud_model_or_503,
    get_policy_rag_service,
    load_fraud_model,
)
from src.api.schemas import (
    ALLOWED_REVIEW_DECISIONS,
    AssessmentRequest,
    ClaimAssistantRequest,
    ClaimCreateRequest,
    ClaimRequest,
    ClaimUpdateRequest,
    FieldCorrectionRequest,
    PolicyQuestionRequest,
    PredictionResponse,
    ReviewDecisionRequest,
    RiskAssessmentRequest,
)
from src.assessment.service import (
    generate_claim_assessment,
    load_assessment_result,
    save_assessment_result,
)
from src.llm.claim_assistant import run_claim_assistant
from src.risk.service import (
    run_claim_risk_assessment,
)
from src.claims.repository import (
    add_audit_log,
    audit_log_to_dict,
    correct_field_result,
    create_claim,
    create_document,
    create_review_decision,
    get_claim,
    get_document,
    get_or_create_claim,
    list_claim_documents,
    list_claims,
    list_audit_logs,
    list_review_decisions,
    mark_document_extracted,
    model_to_dict,
    save_field_results,
    update_claim,
)
from src.database import (
    get_db,
    init_database,
)
from src.validation.completeness import (
    evaluate_document_completeness,
)
from src.validation.cross_document import (
    load_validation_result,
    run_cross_document_validation,
    save_validation_result,
)

from src.documents.service import (
    ALLOWED_DOCUMENT_TYPES,
    save_claim_document,
)

from src.documents.extraction import (
    extract_document_text,
    load_extraction_result,
)

from src.documents.fields import (
    extract_structured_fields,
    load_field_result,
)

# ---------------------------------------------------------
# Project paths and fraud model
# ---------------------------------------------------------

configure_logging()
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent


# ---------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------

app = FastAPI(
    title="ClaimGuard AI API",
    description=(
        "Decision-support API for motor-insurance fraud risk "
        "prediction and policy-document question answering."
    ),
    version="1.0.0",
)


@app.middleware("http")
async def add_request_id(
    request: Request,
    call_next: Any,
) -> Response:
    request_id = request.headers.get(
        "X-Request-ID",
        uuid4().hex,
    )
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    logger.info(
        "request_id=%s method=%s path=%s status_code=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
    )

    return response


@app.on_event("startup")
def startup() -> None:
    init_database()


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

def get_risk_level(probability: float) -> str:
    """
    Convert fraud probability into a readable risk level.
    """

    if probability < 0.30:
        return "LOW"

    if probability < 0.70:
        return "MEDIUM"

    return "HIGH"


# ---------------------------------------------------------
# General endpoints
# ---------------------------------------------------------

@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "ClaimGuard AI API is running",
        "documentation": "/docs",
    }


@app.get("/health")
def health_check() -> dict[str, Any]:
    expected_features = get_expected_features()
    fraud_model_loaded = MODEL_PATH.exists()

    return {
        "status": (
            "healthy"
            if fraud_model_loaded
            else "degraded"
        ),
        "fraud_model_loaded": fraud_model_loaded,
        "expected_feature_count": len(expected_features),
        "model_path": str(MODEL_PATH.relative_to(PROJECT_ROOT)),
        "model_message": (
            "Fraud model is available."
            if fraud_model_loaded
            else (
                "Fraud model is not present. Run "
                "'python -m src.train_model' before using "
                "prediction endpoints."
            )
        ),
    }


# ---------------------------------------------------------
# Claim registry endpoints
# ---------------------------------------------------------

@app.post("/claims")
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


@app.get("/claims")
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


@app.get("/claims/{claim_id}")
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


@app.patch("/claims/{claim_id}")
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


@app.get("/claims/{claim_id}/documents")
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


@app.get("/claims/{claim_id}/completeness")
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


def build_validation_documents(
    claim_id: str,
    documents: list[Any],
) -> list[dict[str, Any]]:
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


@app.post("/claims/{claim_id}/validate")
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


@app.get("/claims/{claim_id}/validation")
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


@app.post("/claims/{claim_id}/assessment")
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


@app.get("/claims/{claim_id}/assessment")
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


@app.post("/claims/{claim_id}/assistant")
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


@app.post("/claims/{claim_id}/review")
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


@app.get("/claims/{claim_id}/reviews")
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


@app.get("/claims/{claim_id}/audit-log")
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


@app.patch(
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


# ---------------------------------------------------------
# Fraud-model endpoints
# ---------------------------------------------------------

@app.get("/model/features")
def get_model_features() -> dict[str, Any]:
    expected_features = get_expected_features()

    return {
        "feature_count": len(expected_features),
        "features": expected_features,
        "source": (
            "model"
            if MODEL_PATH.exists()
            else "training_dataset_schema"
        ),
    }


@app.post(
    "/predict",
    response_model=PredictionResponse,
)
def predict_fraud(
    request: ClaimRequest,
) -> PredictionResponse:
    """
    Estimate the fraud probability of a vehicle-insurance claim.
    """

    claim_data = request.claim
    expected_features = get_expected_features()

    missing_features = [
        feature
        for feature in expected_features
        if feature not in claim_data
    ]

    if missing_features:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Required claim features are missing.",
                "missing_features": missing_features,
            },
        )

    fraud_model = get_fraud_model_or_503()

    # Ignore unknown fields and preserve the training column order.
    ordered_claim = {
        feature: claim_data[feature]
        for feature in expected_features
    }

    claim_dataframe = pd.DataFrame(
        [ordered_claim]
    )

    try:
        probabilities = fraud_model.predict_proba(
            claim_dataframe
        )[0]

        classes = list(fraud_model.classes_)

        if 1 not in classes:
            raise ValueError(
                "Fraud class 1 was not found in model classes."
            )

        fraud_class_index = classes.index(1)

        fraud_probability = float(
            probabilities[fraud_class_index]
        )

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Prediction failed: {error}",
        ) from error

    threshold = 0.50
    prediction = int(
        fraud_probability >= threshold
    )

    return PredictionResponse(
        prediction=prediction,
        prediction_label=(
            "Potential fraud"
            if prediction == 1
            else "Normal claim"
        ),
        fraud_probability=round(
            fraud_probability,
            4,
        ),
        risk_level=get_risk_level(
            fraud_probability
        ),
        threshold=threshold,
    )


@app.post("/claims/{claim_id}/risk-assessment")
def assess_claim_risk_endpoint(
    claim_id: str,
    request: RiskAssessmentRequest | None = None,
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
    manual_features = (
        request.manual_features
        if request is not None
        else {}
    )

    try:
        result = run_claim_risk_assessment(
            claim_id=claim_id,
            claim=model_to_dict(claim),
            documents=validation_documents,
            manual_features=manual_features,
            expected_features=get_expected_features(),
            model=load_fraud_model(),
            model_path=MODEL_PATH,
        )
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=f"Risk assessment failed: {error}",
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Risk assessment failed: {error}",
        ) from error

    add_audit_log(
        db=db,
        claim_id=claim_id,
        event_type="fraud_prediction",
        event_data={
            "status": result["status"],
            "risk_level": result["risk_level"],
            "missing_feature_count": len(
                result["missing_features"]
            ),
        },
    )
    db.commit()

    return result


# ---------------------------------------------------------
# RAG endpoints
# ---------------------------------------------------------

@app.get("/rag/health")
def rag_health() -> dict[str, Any]:
    """
    Check whether the FAISS index, embedding model and Gemini
    configuration are ready.
    """

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


@app.post("/rag/ask")
def ask_policy_question(
    request: PolicyQuestionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Retrieve relevant policy clauses and generate a grounded
    answer using Gemini.
    """

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


@app.post("/rag/retrieve")
def retrieve_policy_sources(
    request: PolicyQuestionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Retrieve policy sources without calling Gemini.
    """

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


@app.get("/documents/types")
def get_document_types() -> dict[str, Any]:
    """
    Return supported insurance-document categories.
    """

    return {
        "document_types": sorted(
            ALLOWED_DOCUMENT_TYPES
        )
    }


@app.post("/claims/{claim_id}/documents")
async def upload_claim_document(
    claim_id: str,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Upload a PDF or image associated with a claim.
    """

    try:
        upload_result = await save_claim_document(
            claim_id=claim_id,
            document_type=document_type,
            upload=file,
        )

        get_or_create_claim(
            db=db,
            claim_id=upload_result["claim_id"],
        )
        create_document(
            db=db,
            document_data=upload_result,
        )

        return upload_result

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "The document could not be stored: "
                f"{error}"
            ),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Document upload failed: "
                f"{error}"
            ),
        ) from error

@app.post(
    "/claims/{claim_id}/documents/"
    "{document_id}/extract"
)
def extract_uploaded_document(
    claim_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Extract text from an uploaded PDF or image.
    """

    try:
        result = extract_document_text(
            claim_id=claim_id,
            document_id=document_id,
        )

        mark_document_extracted(
            db=db,
            claim_id=claim_id,
            document_id=document_id,
        )

        return result

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Document text extraction failed: "
                f"{error}"
            ),
        ) from error


@app.get(
    "/claims/{claim_id}/documents/"
    "{document_id}/extraction"
)
def get_document_extraction(
    claim_id: str,
    document_id: str,
) -> dict[str, Any]:
    """
    Return a previously saved extraction result.
    """

    try:
        return load_extraction_result(
            claim_id=claim_id,
            document_id=document_id,
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not load extraction result: "
                f"{error}"
            ),
        ) from error


@app.post(
    "/claims/{claim_id}/documents/"
    "{document_id}/fields"
)
def extract_document_fields(
    claim_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Extract structured insurance fields from saved document text.
    """

    try:
        result = extract_structured_fields(
            claim_id=claim_id,
            document_id=document_id,
        )

        save_field_results(
            db=db,
            claim_id=claim_id,
            document_id=document_id,
            fields=result["fields"],
        )

        return result

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Structured field extraction failed: "
                f"{error}"
            ),
        ) from error


@app.get(
    "/claims/{claim_id}/documents/"
    "{document_id}/fields"
)
def get_document_fields(
    claim_id: str,
    document_id: str,
) -> dict[str, Any]:
    """
    Return previously saved structured fields.
    """

    try:
        return load_field_result(
            claim_id=claim_id,
            document_id=document_id,
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
