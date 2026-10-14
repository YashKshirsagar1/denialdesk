import enum
from datetime import date, datetime, timezone
from typing import ClassVar, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
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


class OnboardingStatus(str, enum.Enum):
    pending_agreements = "pending_agreements"
    pending_details    = "pending_details"
    active             = "active"
    suspended          = "suspended"


class Practice(TimestampMixin, Base):
    __tablename__ = "practices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    specialty: Mapped[str] = mapped_column(String(100), nullable=False)
    contact: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Onboarding fields (Phase 2 step 8)
    onboarding_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=OnboardingStatus.pending_agreements.value
    )
    baa_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    baa_signed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    service_agreement_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    service_agreement_signed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    npi: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    specialties: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # JSON array
    payers_billed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array

    # Fee configuration — configurable per clinic contract
    fee_rate_standard: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.2200, server_default="0.2200")
    fee_rate_aged: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.3200, server_default="0.3200")
    aged_threshold_days: Mapped[int] = mapped_column(Integer, nullable=False, default=180, server_default="180")

    batches: Mapped[list["Batch"]] = relationship("Batch", back_populates="practice", foreign_keys="Batch.practice_id")
    payer_portal_accesses: Mapped[list["PayerPortalAccess"]] = relationship(
        "PayerPortalAccess", back_populates="practice"
    )
    statements: Mapped[list["Statement"]] = relationship("Statement", back_populates="practice")


class PayerPortalAccess(Base):
    """Records which payer portals our staff have delegated access to.

    NEVER store passwords here. Production secrets go in the secrets manager.
    This table records WHICH portals we have access to, not credentials.
    """
    __tablename__ = "payer_portal_access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    practice_id: Mapped[int] = mapped_column(ForeignKey("practices.id"), nullable=False, index=True)
    payer: Mapped[str] = mapped_column(String(100), nullable=False)
    portal_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    our_username: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)

    practice: Mapped["Practice"] = relationship("Practice", back_populates="payer_portal_accesses")


class Batch(TimestampMixin, Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    practice_id: Mapped[int] = mapped_column(ForeignKey("practices.id"), nullable=False)
    tenant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("practices.id"), nullable=True, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    source_files: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    practice: Mapped["Practice"] = relationship("Practice", back_populates="batches", foreign_keys=[practice_id])
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
    tenant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("practices.id"), nullable=True, index=True)
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
    document_requests: Mapped[list["DocumentRequest"]] = relationship("DocumentRequest", back_populates="case")

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
            tenant_id=self.tenant_id,
            actor=actor,
            action=action,
            inputs_hash=None,
            timestamp=_utcnow(),
        )


class Diagnosis(TimestampMixin, Base):
    __tablename__ = "diagnoses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, unique=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("practices.id"), nullable=True, index=True)
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
    tenant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("practices.id"), nullable=True, index=True)
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
    tenant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("practices.id"), nullable=True, index=True)
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


class VerificationMethod(str, enum.Enum):
    payment_835          = "payment_835"        # matched a line in an 835 ERA
    clinic_confirmation  = "clinic_confirmation" # clinic confirmed in portal


class Outcome(TimestampMixin, Base):
    __tablename__ = "outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, unique=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("practices.id"), nullable=True, index=True)
    result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # paid | denied
    amount_recovered: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    paid_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Verification fields — an outcome is billable only after verification
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    verification_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    billable_amount: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

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


class DocumentRequestStatus(str, enum.Enum):
    pending   = "pending"
    fulfilled = "fulfilled"
    cancelled = "cancelled"


class DocumentRequest(Base):
    __tablename__ = "document_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("practices.id"), nullable=True, index=True)
    requested_by: Mapped[str] = mapped_column(String(100), nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DocumentRequestStatus] = mapped_column(
        Enum(DocumentRequestStatus, name="documentrequeststatus"),
        default=DocumentRequestStatus.pending,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    fulfilled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # In prod this becomes a private S3 key; never log this value as it may contain PHI context
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    case: Mapped["Case"] = relationship("Case", back_populates="document_requests")


class StatementStatus(str, enum.Enum):
    draft = "draft"
    sent  = "sent"
    paid  = "paid"


class Statement(Base):
    """Monthly recovery statement per practice.

    line_items: JSON array of {case_id, patient_ref, amount_recovered, fee, rate, aged}.
    stripe_invoice_id: set when Stripe invoice is created — never store card/bank numbers here.
    pdf_path: local path in dev; replace with S3 key in prod.
    """
    __tablename__ = "statements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    practice_id: Mapped[int] = mapped_column(ForeignKey("practices.id"), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    total_recovered: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    fee_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=StatementStatus.draft.value)
    line_items: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # TODO: In production, set from Stripe invoice creation. Never store card/bank numbers.
    stripe_invoice_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    practice: Mapped["Practice"] = relationship("Practice", back_populates="statements")


class AccessLog(Base):
    """Records every HTTP access to PHI-bearing routes — reads included.

    actor_email is stored as SHA-256 hex — never plain text.
    resource is always an ID reference ("case:42", "queue") — never contains PHI.
    Separate from AuditEvent which tracks state-machine transitions.
    """
    __tablename__ = "access_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("practices.id"), nullable=True, index=True)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # Stored as SHA-256 hex — not reversible; derivable from auth context if needed.
    actor_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False)
    resource: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # read | create | update | delete
    http_method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"), nullable=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("practices.id"), nullable=True, index=True)
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
