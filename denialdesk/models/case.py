import enum
from datetime import datetime, timezone
from typing import ClassVar, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class CaseState(str, enum.Enum):
    ingested = "ingested"
    diagnosed = "diagnosed"
    declined = "declined"
    approved = "approved"
    drafted = "drafted"
    awaiting_human_review = "awaiting_human_review"
    submitted = "submitted"
    pending_payer = "pending_payer"
    paid = "paid"
    re_denied = "re_denied"
    escalated = "escalated"
    closed = "closed"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
        nullable=False,
    )


class Practice(TimestampMixin, Base):
    __tablename__ = "practices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    specialty: Mapped[str] = mapped_column(String(100), nullable=False)
    contact: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    batches: Mapped[list["Batch"]] = relationship("Batch", back_populates="practice")


class Batch(TimestampMixin, Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    practice_id: Mapped[int] = mapped_column(ForeignKey("practices.id"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    source_files: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    practice: Mapped["Practice"] = relationship("Practice", back_populates="batches")
    cases: Mapped[list["Case"]] = relationship("Case", back_populates="batch")


class Case(TimestampMixin, Base):
    __tablename__ = "cases"

    VALID_TRANSITIONS: ClassVar[dict[CaseState, list[CaseState]]] = {
        CaseState.ingested:              [CaseState.diagnosed],
        CaseState.diagnosed:             [CaseState.declined, CaseState.approved],
        CaseState.declined:              [CaseState.closed],
        CaseState.approved:              [CaseState.drafted],
        CaseState.drafted:               [CaseState.awaiting_human_review],
        CaseState.awaiting_human_review: [CaseState.submitted, CaseState.drafted],
        CaseState.submitted:             [CaseState.pending_payer],
        CaseState.pending_payer:         [CaseState.paid, CaseState.re_denied],
        CaseState.paid:                  [CaseState.closed],
        CaseState.re_denied:             [CaseState.escalated, CaseState.closed],
        CaseState.escalated:             [CaseState.pending_payer, CaseState.closed],
        CaseState.closed:                [],
    }

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False)
    payer: Mapped[str] = mapped_column(String(255), nullable=False)
    patient_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dos: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cpt_hcpcs: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    icd10: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    billed_amt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    allowed_amt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    carc: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    rarc: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    denial_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    filing_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[CaseState] = mapped_column(
        Enum(CaseState, name="casestate"), default=CaseState.ingested, nullable=False
    )

    batch: Mapped["Batch"] = relationship("Batch", back_populates="cases")
    diagnosis: Mapped[Optional["Diagnosis"]] = relationship("Diagnosis", back_populates="case", uselist=False)
    drafts: Mapped[list["Draft"]] = relationship("Draft", back_populates="case")
    submissions: Mapped[list["Submission"]] = relationship("Submission", back_populates="case")
    outcome: Mapped[Optional["Outcome"]] = relationship("Outcome", back_populates="case", uselist=False)
    audit_events: Mapped[list["AuditEvent"]] = relationship("AuditEvent", back_populates="case")

    @property
    def is_terminal(self) -> bool:
        return self.state in (CaseState.closed, CaseState.paid, CaseState.declined)

    def transition(self, new_state: CaseState, actor: str = "system", action_note: str = "") -> "AuditEvent":
        allowed = self.VALID_TRANSITIONS.get(self.state, [])
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {self.state.value} -> {new_state.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        old_state = self.state
        self.state = new_state
        self.updated_at = _utcnow()
        action = f"state_transition:{old_state.value}->{new_state.value}"
        if action_note:
            action = f"{action} | {action_note}"
        return AuditEvent(
            case_id=self.id,
            actor=actor,
            action=action,
            inputs_hash=None,
            timestamp=_utcnow(),
        )


class Diagnosis(TimestampMixin, Base):
    __tablename__ = "diagnoses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, unique=True)
    root_cause: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    winnability_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    case: Mapped["Case"] = relationship("Case", back_populates="diagnosis")


class Draft(TimestampMixin, Base):
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # appeal | corrected_claim | call_packet
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attachments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    case: Mapped["Case"] = relationship("Case", back_populates="drafts")
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="draft")


class Review(TimestampMixin, Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id"), nullable=False)
    reviewer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # approved | rejected | edited
    edits_diff: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    draft: Mapped["Draft"] = relationship("Draft", back_populates="reviews")


class Submission(TimestampMixin, Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)  # portal | fax | mail | phone
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reference_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    case: Mapped["Case"] = relationship("Case", back_populates="submissions")


class Outcome(TimestampMixin, Base):
    __tablename__ = "outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, unique=True)
    result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # paid | denied
    amount_recovered: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    paid_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    case: Mapped["Case"] = relationship("Case", back_populates="outcome")


class PayerPlaybook(TimestampMixin, Base):
    __tablename__ = "payer_playbooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payer: Mapped[str] = mapped_column(String(255), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(20), nullable=False)
    specialty: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    winning_strategy: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    required_docs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array stored as text
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"), nullable=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    inputs_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    case: Mapped[Optional["Case"]] = relationship("Case", back_populates="audit_events")
