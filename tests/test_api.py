import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_CLAIM_PATH = PROJECT_ROOT / "test_claim.json"
MODEL_PATH = PROJECT_ROOT / "models" / "fraud_model.joblib"

if not MODEL_PATH.exists():
    pytest.skip(
        "fraud_model.joblib is required for app API tests",
        allow_module_level=True,
    )

from app import app

client = TestClient(app)


def test_root_endpoint() -> None:
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "ClaimGuard AI API is running"
    assert data["documentation"] == "/docs"


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert data["fraud_model_loaded"] is True
    assert data["expected_feature_count"] > 0


def test_model_features_endpoint() -> None:
    response = client.get("/model/features")

    assert response.status_code == 200

    data = response.json()

    assert data["feature_count"] > 0
    assert len(data["features"]) == data["feature_count"]
    assert "Age" in data["features"]


def test_predict_rejects_missing_features() -> None:
    response = client.post(
        "/predict",
        json={
            "claim": {
                "Age": 30
            }
        },
    )

    assert response.status_code == 422

    detail = response.json()["detail"]

    assert detail["message"] == (
        "Required claim features are missing."
    )
    assert len(detail["missing_features"]) > 0


def test_predict_with_valid_claim() -> None:
    assert TEST_CLAIM_PATH.exists(), (
        "test_claim.json does not exist. Run "
        "python src/create_test_request.py first."
    )

    with TEST_CLAIM_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        request_body = json.load(file)

    response = client.post(
        "/predict",
        json=request_body,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["prediction"] in [0, 1]
    assert data["prediction_label"] in [
        "Normal claim",
        "Potential fraud",
    ]
    assert 0.0 <= data["fraud_probability"] <= 1.0
    assert data["risk_level"] in [
        "LOW",
        "MEDIUM",
        "HIGH",
    ]
    assert data["threshold"] == 0.5
