from pathlib import Path

import pytest
from fastapi import HTTPException

from src.api import dependencies


def test_expected_features_can_load_from_tracked_dataset() -> None:
    dependencies.get_expected_features.cache_clear()

    features = dependencies.get_expected_features()

    assert "Age" in features
    assert "FraudFound_P" not in features
    assert "PolicyNumber" not in features


def test_fraud_model_dependency_returns_503_when_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dependencies.load_fraud_model.cache_clear()
    monkeypatch.setattr(
        dependencies,
        "MODEL_PATH",
        tmp_path / "missing_model.joblib",
    )

    with pytest.raises(HTTPException) as error:
        dependencies.get_fraud_model_or_503()

    assert error.value.status_code == 503
    assert "Fraud model not found" in str(error.value.detail)

    dependencies.load_fraud_model.cache_clear()
