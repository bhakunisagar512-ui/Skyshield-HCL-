from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.core.taxonomy import IncidentStatus, MeasureStatus, SummaryStatus
from app.database import Base

EMBEDDING_DIM = get_settings().embedding_dim


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), index=True)
    designation: Mapped[str | None] = mapped_column(String(80))
    base_station: Mapped[str | None] = mapped_column(String(3))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Incident(TimestampMixin, Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    airport_code: Mapped[str] = mapped_column(String(3), index=True)
    flight_phase: Mapped[str] = mapped_column(String(20))
    aircraft_registration: Mapped[str | None] = mapped_column(String(10))
    aircraft_type: Mapped[str | None] = mapped_column(String(20))
    operator_code: Mapped[str | None] = mapped_column(String(3))
    flight_number: Mapped[str | None] = mapped_column(String(10))

    severity: Mapped[str | None] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), default=IncidentStatus.SUBMITTED, index=True)
    analysis: Mapped[str | None] = mapped_column(Text)
    closing_note: Mapped[str | None] = mapped_column(Text)

    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    officer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    reporter: Mapped[User] = relationship(foreign_keys=[reporter_id])
    officer: Mapped[User | None] = relationship(foreign_keys=[officer_id])
    measures: Mapped[list["Measure"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan", order_by="Measure.id"
    )
    summaries: Mapped[list["AISummary"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan", order_by="AISummary.id"
    )
    history: Mapped[list["StatusHistory"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan", order_by="StatusHistory.id"
    )

    @property
    def latest_summary(self) -> "AISummary | None":
        return self.summaries[-1] if self.summaries else None


class StatusHistory(Base):
    __tablename__ = "incident_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    incident: Mapped[Incident] = relationship(back_populates="history")
    changed_by: Mapped[User | None] = relationship()


class AISummary(TimestampMixin, Base):
    __tablename__ = "ai_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default=SummaryStatus.GENERATING)
    summary: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[str | None] = mapped_column(Text)  # comma separated chunk refs
    model: Mapped[str | None] = mapped_column(String(80))
    error: Mapped[str | None] = mapped_column(Text)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    incident: Mapped[Incident] = relationship(back_populates="summaries")


class Measure(TimestampMixin, Base):
    __tablename__ = "measures"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(10))
    source: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(15), default=MeasureStatus.PENDING, index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    policy_reference: Mapped[str | None] = mapped_column(String(120))
    marked_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    incident: Mapped[Incident] = relationship(back_populates="measures")


class PolicyDocument(TimestampMixin, Base):
    __tablename__ = "policy_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(40), index=True)
    source: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)

    chunks: Mapped[list["PolicyChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="PolicyChunk.chunk_index"
    )


class PolicyChunk(Base):
    __tablename__ = "policy_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("policy_documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    section_ref: Mapped[str] = mapped_column(String(120))
    content: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(EMBEDDING_DIM))

    document: Mapped[PolicyDocument] = relationship(back_populates="chunks")
