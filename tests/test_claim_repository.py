from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.claims.repository import (
    create_claim,
    create_document,
    get_claim,
    get_or_create_claim,
    list_claim_documents,
    list_claims,
    model_to_dict,
    update_claim,
)
from src.database import (
    AuditLog,
    Base,
)


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    session = session_factory()

    try:
        yield session
    finally:
        session.close()


def test_create_list_get_and_update_claim(
    db_session: Session,
) -> None:
    claim = create_claim(
        db=db_session,
        claim_data={
            "claim_id": "CLM-DB-001",
            "policy_number": "POL-123",
            "customer_name": "Asha Rao",
            "vehicle_number": "MH12AB1234",
            "status": "open",
        },
    )

    assert claim.id is not None
    assert get_claim(db_session, "CLM-DB-001") is not None
    assert len(list_claims(db_session)) == 1

    updated_claim = update_claim(
        db=db_session,
        claim=claim,
        updates={
            "status": "pending_review",
            "claimed_amount": 12500.0,
        },
    )

    assert updated_claim.status == "pending_review"
    assert updated_claim.claimed_amount == 12500.0

    serialized = model_to_dict(updated_claim)
    assert serialized["claim_id"] == "CLM-DB-001"
    assert isinstance(serialized["created_at"], str)


def test_get_or_create_claim_is_idempotent(
    db_session: Session,
) -> None:
    first_claim = get_or_create_claim(
        db=db_session,
        claim_id="CLM-DB-002",
    )
    second_claim = get_or_create_claim(
        db=db_session,
        claim_id="CLM-DB-002",
    )

    assert first_claim.id == second_claim.id
    assert len(list_claims(db_session)) == 1


def test_create_document_and_audit_log(
    db_session: Session,
) -> None:
    get_or_create_claim(
        db=db_session,
        claim_id="CLM-DB-003",
    )

    document = create_document(
        db=db_session,
        document_data={
            "document_id": "b" * 32,
            "claim_id": "CLM-DB-003",
            "document_type": "claim_form",
            "original_filename": "claim.pdf",
            "stored_filename": "bbbb_claim_form.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1024,
            "storage_path": "data/uploads/CLM-DB-003/bbbb.pdf",
        },
    )

    documents = list_claim_documents(
        db=db_session,
        claim_id="CLM-DB-003",
    )
    audit_logs = list(
        db_session.scalars(
            select(AuditLog).where(
                AuditLog.claim_id == "CLM-DB-003"
            )
        )
    )

    assert document.document_id == "b" * 32
    assert len(documents) == 1
    assert {
        audit_log.event_type
        for audit_log in audit_logs
    } == {
        "claim_created",
        "document_uploaded",
    }
