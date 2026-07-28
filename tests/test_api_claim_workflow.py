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
        "fraud_model.joblib is required for app workflow tests",
        allow_module_level=True,
    )

import app as app_module
from src.claims.repository import (
    create_document,
    save_field_results,
)
from src.database import (
    Base,
)


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


def test_claim_crud_endpoints_use_temporary_database(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/claims",
        json={
            "claim_id": "CLM-API-001",
            "policy_number": "POL-API-1",
            "customer_name": "Demo Customer",
            "vehicle_number": "MH12AB1234",
            "status": "open",
        },
    )

    assert create_response.status_code == 200
    assert create_response.json()["claim_id"] == "CLM-API-001"

    duplicate_response = client.post(
        "/claims",
        json={
            "claim_id": "CLM-API-001",
        },
    )
    assert duplicate_response.status_code == 409

    list_response = client.get("/claims")
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1

    get_response = client.get("/claims/CLM-API-001")
    assert get_response.status_code == 200
    assert get_response.json()["policy_number"] == "POL-API-1"

    patch_response = client.patch(
        "/claims/CLM-API-001",
        json={
            "status": "pending_review",
            "claimed_amount": 42500.0,
        },
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "pending_review"
    assert patch_response.json()["claimed_amount"] == 42500.0


def test_review_and_audit_log_endpoints(
    client: TestClient,
) -> None:
    response = client.post(
        "/claims",
        json={
            "claim_id": "CLM-API-REV",
            "status": "open",
        },
    )
    assert response.status_code == 200

    review_response = client.post(
        "/claims/CLM-API-REV/review",
        json={
            "reviewer_name": "Reviewer One",
            "decision": "normal_review",
            "comment": "Ready for normal review.",
        },
    )

    assert review_response.status_code == 200
    assert review_response.json()["decision"] == "normal_review"
    assert review_response.json()["comment"] == (
        "Ready for normal review."
    )

    reviews_response = client.get(
        "/claims/CLM-API-REV/reviews"
    )
    assert reviews_response.status_code == 200
    assert reviews_response.json()["count"] == 1

    audit_response = client.get(
        "/claims/CLM-API-REV/audit-log"
    )
    assert audit_response.status_code == 200
    event_types = {
        event["event_type"]
        for event in audit_response.json()["audit_logs"]
    }

    assert "claim_created" in event_types
    assert "review_decision" in event_types


def test_field_correction_endpoint_creates_review_payload(
    client: TestClient,
) -> None:
    response = client.post(
        "/claims",
        json={
            "claim_id": "CLM-API-FLD",
            "status": "open",
        },
    )
    assert response.status_code == 200

    session_override = app_module.app.dependency_overrides[
        app_module.get_db
    ]
    session_iterator = session_override()
    db = next(session_iterator)
    try:
        create_document(
            db=db,
            document_data={
                "document_id": "d" * 32,
                "claim_id": "CLM-API-FLD",
                "document_type": "claim_form",
                "original_filename": "claim.pdf",
                "stored_filename": "dddd_claim_form.pdf",
                "content_type": "application/pdf",
                "size_bytes": 512,
                "storage_path": (
                    "data/uploads/CLM-API-FLD/"
                    "dddd_claim_form.pdf"
                ),
            },
        )
        save_field_results(
            db=db,
            claim_id="CLM-API-FLD",
            document_id="d" * 32,
            fields={
                "insured_name": {
                    "status": "found",
                    "value": "Demo Customer",
                    "raw_value": "Demo Customer",
                    "confidence": 0.91,
                    "source_page": 1,
                    "evidence": "Insured Name: Demo Customer",
                }
            },
        )
    finally:
        db.close()
        try:
            next(session_iterator)
        except StopIteration:
            pass

    correction_response = client.patch(
        f"/claims/CLM-API-FLD/documents/{'d' * 32}/fields/"
        "insured_name",
        json={
            "reviewer_name": "Reviewer One",
            "corrected_value": "Demo C.",
        },
    )

    assert correction_response.status_code == 200
    data = correction_response.json()
    assert data["original_value"] == "Demo Customer"
    assert data["corrected_value"] == "Demo C."
    assert data["status"] == "corrected"
