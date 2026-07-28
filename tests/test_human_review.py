from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.claims.repository import (
    correct_field_result,
    create_claim,
    create_document,
    create_review_decision,
    list_review_decisions,
    model_to_dict,
    save_field_results,
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


def create_claim_document_and_field(
    db_session: Session,
) -> None:
    create_claim(
        db=db_session,
        claim_data={
            "claim_id": "CLM-REV-001",
            "status": "open",
        },
    )
    create_document(
        db=db_session,
        document_data={
            "document_id": "c" * 32,
            "claim_id": "CLM-REV-001",
            "document_type": "claim_form",
            "original_filename": "claim.pdf",
            "stored_filename": "cccc_claim_form.pdf",
            "content_type": "application/pdf",
            "size_bytes": 512,
            "storage_path": "data/uploads/CLM-REV-001/claim.pdf",
        },
    )
    save_field_results(
        db=db_session,
        claim_id="CLM-REV-001",
        document_id="c" * 32,
        fields={
            "insured_name": {
                "status": "found",
                "value": "Asha Rao",
                "raw_value": "Asha Rao",
                "confidence": 0.9,
                "source_page": 1,
                "evidence": "Insured Name: Asha Rao",
            }
        },
    )


def test_create_and_list_review_decisions(
    db_session: Session,
) -> None:
    create_claim_document_and_field(db_session)

    review = create_review_decision(
        db=db_session,
        claim_id="CLM-REV-001",
        reviewer_name="Reviewer One",
        decision="normal_review",
        comment="Looks ready for normal review.",
    )
    reviews = list_review_decisions(
        db=db_session,
        claim_id="CLM-REV-001",
    )
    review_data = model_to_dict(review)

    assert review.id is not None
    assert len(reviews) == 1
    assert review_data["decision"] == "normal_review"
    assert review_data["comments"] == (
        "Looks ready for normal review."
    )


def test_correct_field_result_creates_audit_log(
    db_session: Session,
) -> None:
    create_claim_document_and_field(db_session)

    corrected = correct_field_result(
        db=db_session,
        claim_id="CLM-REV-001",
        document_id="c" * 32,
        field_name="insured_name",
        reviewer_name="Reviewer One",
        corrected_value="Asha R.",
    )
    audit_events = list(
        db_session.scalars(
            select(AuditLog).where(
                AuditLog.claim_id == "CLM-REV-001"
            )
        )
    )

    assert corrected.value == "Asha Rao"
    assert corrected.reviewer_corrected_value == "Asha R."
    assert corrected.reviewed_at is not None
    assert "human_correction" in {
        event.event_type
        for event in audit_events
    }


def test_correct_missing_field_raises_value_error(
    db_session: Session,
) -> None:
    create_claim_document_and_field(db_session)

    with pytest.raises(ValueError):
        correct_field_result(
            db=db_session,
            claim_id="CLM-REV-001",
            document_id="c" * 32,
            field_name="missing_field",
            reviewer_name="Reviewer One",
            corrected_value="Corrected",
        )
