from pathlib import Path
from typing import Any

import pandas as pd

from src.risk.feature_mapping import (
    build_feature_mapping_report,
)


def risk_level(probability: float) -> str:
    if probability < 0.30:
        return "LOW"

    if probability < 0.70:
        return "MEDIUM"

    return "HIGH"


def model_version(model_path: Path) -> str:
    if not model_path.exists():
        return "unknown"

    return (
        f"{model_path.name}:"
        f"{int(model_path.stat().st_mtime)}"
    )


def important_risk_factors(
    model: Any,
    ordered_features: dict[str, Any],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Best-effort local explanation for linear sklearn pipelines.

    This is not SHAP. It exposes the largest absolute transformed
    logistic-regression contributions when the model supports it.
    """

    try:
        preprocessing = model.named_steps["preprocessing"]
        estimator = model.named_steps["model"]
        dataframe = pd.DataFrame([ordered_features])
        transformed = preprocessing.transform(dataframe)

        feature_names = preprocessing.get_feature_names_out()
        coefficients = estimator.coef_[0]
        row = transformed.toarray()[0] if hasattr(
            transformed,
            "toarray",
        ) else transformed[0]
        contributions = row * coefficients

        ranked = sorted(
            zip(
                feature_names,
                contributions,
            ),
            key=lambda item: abs(float(item[1])),
            reverse=True,
        )

        return [
            {
                "feature": str(feature_name),
                "contribution": round(
                    float(contribution),
                    4,
                ),
            }
            for feature_name, contribution in ranked[:limit]
        ]

    except Exception:
        return []


def run_claim_risk_assessment(
    claim_id: str,
    claim: dict[str, Any],
    documents: list[dict[str, Any]],
    manual_features: dict[str, Any] | None,
    expected_features: list[str],
    model: Any,
    model_path: Path,
    threshold: float = 0.50,
) -> dict[str, Any]:
    mapping_report = build_feature_mapping_report(
        expected_features=expected_features,
        claim=claim,
        documents=documents,
        manual_features=manual_features,
    )

    if mapping_report["missing_features"]:
        return {
            "claim_id": claim_id,
            "status": "manual_features_required",
            "fraud_probability": None,
            "prediction": None,
            "prediction_label": (
                "Risk assessment not run because required "
                "model features are missing."
            ),
            "risk_level": "NOT_ASSESSED",
            "threshold": threshold,
            "model_version": model_version(model_path),
            "features_used": mapping_report["features_used"],
            "available_features": mapping_report["available_features"],
            "missing_features": mapping_report["missing_features"],
            "defaulted_features": mapping_report["defaulted_features"],
            "manually_required_features": (
                mapping_report["manually_required_features"]
            ),
            "warnings": mapping_report["warnings"],
            "important_risk_factors": [],
        }

    ordered_features = {
        feature: mapping_report["features_used"][feature]
        for feature in expected_features
    }
    claim_dataframe = pd.DataFrame([ordered_features])
    probabilities = model.predict_proba(
        claim_dataframe
    )[0]
    classes = list(model.classes_)

    if 1 not in classes:
        raise ValueError(
            "Fraud class 1 was not found in model classes."
        )

    fraud_probability = float(
        probabilities[classes.index(1)]
    )
    prediction = int(
        fraud_probability >= threshold
    )

    return {
        "claim_id": claim_id,
        "status": "assessed",
        "fraud_probability": round(
            fraud_probability,
            4,
        ),
        "prediction": prediction,
        "prediction_label": (
            "Higher fraud-risk signal"
            if prediction == 1
            else "Lower fraud-risk signal"
        ),
        "risk_level": risk_level(
            fraud_probability
        ),
        "threshold": threshold,
        "model_version": model_version(model_path),
        "features_used": ordered_features,
        "available_features": mapping_report["available_features"],
        "missing_features": [],
        "defaulted_features": mapping_report["defaulted_features"],
        "manually_required_features": [],
        "warnings": mapping_report["warnings"],
        "important_risk_factors": important_risk_factors(
            model=model,
            ordered_features=ordered_features,
        ),
    }
