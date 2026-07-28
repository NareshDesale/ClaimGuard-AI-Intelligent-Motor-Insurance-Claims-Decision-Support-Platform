from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.claim_context import build_validation_documents
from src.api.dependencies import (
    MODEL_PATH,
    get_expected_features,
    get_fraud_model_or_503,
    load_fraud_model,
)
from src.api.schemas import (
    ClaimRequest,
    PredictionResponse,
    RiskAssessmentRequest,
)
from src.claims.repository import (
    add_audit_log,
    get_claim,
    list_claim_documents,
    model_to_dict,
)
from src.database import get_db
from src.risk.service import run_claim_risk_assessment


router = APIRouter(tags=["fraud"])


def get_risk_level(probability: float) -> str:
    """Convert fraud probability into a readable risk level."""

    if probability < 0.30:
        return "LOW"

    if probability < 0.70:
        return "MEDIUM"

    return "HIGH"


@router.post(
    "/predict",
    response_model=PredictionResponse,
)
def predict_fraud(
    request: ClaimRequest,
) -> PredictionResponse:
    """Estimate the fraud probability of a vehicle-insurance claim."""

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

    ordered_claim = {
        feature: claim_data[feature]
        for feature in expected_features
    }

    claim_dataframe = pd.DataFrame(
        [ordered_claim],
    )

    try:
        probabilities = fraud_model.predict_proba(
            claim_dataframe,
        )[0]
        classes = list(fraud_model.classes_)

        if 1 not in classes:
            raise ValueError(
                "Fraud class 1 was not found in model classes.",
            )

        fraud_class_index = classes.index(1)
        fraud_probability = float(
            probabilities[fraud_class_index],
        )

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Prediction failed: {error}",
        ) from error

    threshold = 0.50
    prediction = int(
        fraud_probability >= threshold,
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
            fraud_probability,
        ),
        threshold=threshold,
    )


@router.post("/claims/{claim_id}/risk-assessment")
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
                result["missing_features"],
            ),
        },
    )
    db.commit()

    return result
