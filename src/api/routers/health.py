from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from src.api.dependencies import (
    MODEL_PATH,
    PROJECT_ROOT,
    get_expected_features,
)


router = APIRouter(tags=["health"])


@router.get("/")
def root() -> dict[str, str]:
    return {
        "message": "ClaimGuard AI API is running",
        "documentation": "/docs",
    }


@router.get("/health")
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


@router.get("/model/features")
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
