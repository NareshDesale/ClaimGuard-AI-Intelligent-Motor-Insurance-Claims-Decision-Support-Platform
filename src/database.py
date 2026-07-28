from datetime import UTC, datetime
from typing import Generator

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from src.config import (
    DEFAULT_DATABASE_PATH,
    get_settings,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def get_database_url() -> str:
    return get_settings().database_url


DATABASE_URL = get_database_url()

connect_args = (
    {"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )
    claim_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    policy_number: Mapped[str | None] = mapped_column(String(100))
    customer_name: Mapped[str | None] = mapped_column(String(200))
    vehicle_number: Mapped[str | None] = mapped_column(String(50))
    accident_date: Mapped[str | None] = mapped_column(String(30))
    reported_date: Mapped[str | None] = mapped_column(String(30))
    claimed_amount: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(
        String(50),
        default="open",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
    )
    review_decisions: Mapped[list["ReviewDecision"]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )
    document_id: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
    )
    claim_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("claims.claim_id"),
        index=True,
        nullable=False,
    )
    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    stored_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    content_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    extraction_status: Mapped[str] = mapped_column(
        String(50),
        default="not_started",
        nullable=False,
    )
    fields_status: Mapped[str] = mapped_column(
        String(50),
        default="not_started",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    claim: Mapped[Claim] = relationship(
        back_populates="documents",
    )
    field_results: Mapped[list["FieldResult"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class FieldResult(Base):
    __tablename__ = "field_results"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )
    document_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("documents.document_id"),
        index=True,
        nullable=False,
    )
    field_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    value: Mapped[str | None] = mapped_column(String(500))
    raw_value: Mapped[str | None] = mapped_column(String(500))
    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    source_page: Mapped[int | None] = mapped_column(Integer)
    evidence: Mapped[str | None] = mapped_column(Text)
    reviewer_corrected_value: Mapped[str | None] = mapped_column(
        String(500)
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    document: Mapped[Document] = relationship(
        back_populates="field_results",
    )


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )
    claim_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("claims.claim_id"),
        index=True,
        nullable=False,
    )
    reviewer_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    comments: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    claim: Mapped[Claim] = relationship(
        back_populates="review_decisions",
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )
    claim_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("claims.claim_id"),
        index=True,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    event_data: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    claim: Mapped[Claim] = relationship(
        back_populates="audit_logs",
    )


def init_database() -> None:
    if DATABASE_URL.startswith("sqlite"):
        DEFAULT_DATABASE_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    database = SessionLocal()

    try:
        yield database
    finally:
        database.close()
