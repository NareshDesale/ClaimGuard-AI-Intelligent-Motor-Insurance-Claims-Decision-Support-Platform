from __future__ import annotations

from functools import lru_cache
import logging
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from fastapi import HTTPException

from src.config import get_settings
from src.rag.service import PolicyRAGService


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS = get_settings()
MODEL_PATH = SETTINGS.fraud_model_path
TRAINING_DATA_PATH = SETTINGS.training_data_path
TARGET_COLUMN = "FraudFound_P"


@lru_cache(maxsize=1)
def load_fraud_model() -> Any:
    """
    Load the trained fraud model lazily.

    The model binary is intentionally not committed to GitHub, so a
    fresh clone must still be able to start and report a clear degraded
    health state until the model is trained locally.
    """

    if not MODEL_PATH.exists():
        raise RuntimeError(
            f"Fraud model not found at {MODEL_PATH}. "
            "Run 'python -m src.train_model' to train it."
        )

    return joblib.load(MODEL_PATH)


def get_fraud_model_or_503() -> Any:
    try:
        return load_fraud_model()
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error


@lru_cache(maxsize=1)
def get_expected_features() -> list[str]:
    """Return fraud-model feature names without requiring the binary."""

    if MODEL_PATH.exists():
        try:
            loaded_model = load_fraud_model()
            feature_names = getattr(
                loaded_model,
                "feature_names_in_",
                None,
            )
            if feature_names is not None:
                return list(feature_names)
        except Exception:
            logger.warning(
                "Unable to read feature names from fraud model.",
                exc_info=True,
            )

    if TRAINING_DATA_PATH.exists():
        dataframe = pd.read_csv(
            TRAINING_DATA_PATH,
            nrows=0,
        )
        return [
            column
            for column in dataframe.columns
            if column not in {TARGET_COLUMN, "PolicyNumber"}
        ]

    raise RuntimeError(
        "Fraud feature schema is unavailable. Provide either "
        "models/fraud_model.joblib or data/raw/fraud_oracle.csv."
    )


@lru_cache(maxsize=1)
def get_policy_rag_service() -> PolicyRAGService:
    """
    Load the embedding model and FAISS index once.

    Caching prevents the Sentence Transformer and vector index from
    being reloaded for every request.
    """

    return PolicyRAGService()
