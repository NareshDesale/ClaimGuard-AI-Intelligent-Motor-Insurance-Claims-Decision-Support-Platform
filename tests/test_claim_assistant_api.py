from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "fraud_model.joblib"

if not MODEL_PATH.exists():
    pytest.skip(
        "fraud_model.joblib is required for app assistant API tests",
        allow_module_level=True,
    )

import app as app_module
from src.database import Base


@pytest.fixture()
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    def override_get_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app_module.app.dependency_overrides[
        app_module.get_db
    ] = override_get_db

    try:
        with TestClient(app_module.app) as test_client:
            yield test_client
    finally:
        app_module.app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_claim_assistant_endpoint_returns_deterministic_brief(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/claims",
        json={
            "claim_id": "CLM-AI-API",
            "policy_number": "POL-AI-API",
            "customer_name": "Demo Customer",
            "vehicle_number": "MH12AB1234",
            "claimed_amount": 35000.0,
            "status": "open",
        },
    )
    assert create_response.status_code == 200

    response = client.post(
        "/claims/CLM-AI-API/assistant",
        json={
            "question": "What should the reviewer check next?",
            "use_llm": False,
            "include_policy_context": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["claim_id"] == "CLM-AI-API"
    assert data["mode"] == "deterministic"
    assert "reviewer briefing" in data["answer"]
    assert data["context_summary"]["document_count"] == 0

    audit_response = client.get("/claims/CLM-AI-API/audit-log")
    assert audit_response.status_code == 200
    event_types = {
        event["event_type"]
        for event in audit_response.json()["audit_logs"]
    }
    assert "claim_assistant_query" in event_types


def test_claim_assistant_endpoint_validates_question(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/claims",
        json={
            "claim_id": "CLM-AI-422",
            "status": "open",
        },
    )
    assert create_response.status_code == 200

    response = client.post(
        "/claims/CLM-AI-422/assistant",
        json={
            "question": "Hi",
        },
    )

    assert response.status_code == 422
