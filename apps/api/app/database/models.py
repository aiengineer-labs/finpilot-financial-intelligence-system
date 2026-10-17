from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TenantRole(StrEnum):
    OWNER = "owner"
    MEMBER = "member"
    REVIEWER = "reviewer"


class UploadStatus(StrEnum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class AccountType(StrEnum):
    UNKNOWN = "unknown"
    DEPOSIT = "deposit"
    CREDIT_CARD = "credit_card"


class TransactionKind(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    REFUND = "refund"


class ClassificationMethod(StrEnum):
    RULE = "rule"
    MESH_REQUIRED = "mesh_required"
    HUMAN = "human"


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class VerificationStatus(StrEnum):
    ACCEPT = "accept"
    REVISE = "revise"
    REJECT = "reject"
    INSUFFICIENT_DATA = "insufficient_data"


class GovernanceArtifactStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HumanReviewStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"


class HumanDecisionOutcome(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_INFORMATION = "request_information"
    REQUEST_REVISION = "request_revision"


class EvaluationGateStatus(StrEnum):
    PASS = "pass"  # noqa: S105 - evaluation status, not a credential
    FAIL = "fail"
    NOT_RUN = "not_run"


class DigestJobStatus(StrEnum):
    CLAIMED = "claimed"
    DELIVERED = "delivered"
    FAILED = "failed"


class NotificationStatus(StrEnum):
    DELIVERED = "delivered"
    FAILED = "failed"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    memberships: Mapped[list["Membership"]] = relationship(back_populates="tenant")
    accounts: Mapped[list["FinancialAccount"]] = relationship(back_populates="tenant")
    uploads: Mapped[list["TransactionUpload"]] = relationship(back_populates="tenant")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="tenant")


class Membership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "tenant_id"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    role: Mapped[TenantRole] = mapped_column(Enum(TenantRole), default=TenantRole.MEMBER)
    user: Mapped[User] = relationship(back_populates="memberships")
    tenant: Mapped[Tenant] = relationship(back_populates="memberships")


class FinancialAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_accounts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_reference"),
        Index("ix_financial_accounts_tenant_id_id", "tenant_id", "id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    external_reference: Mapped[str] = mapped_column(String(128))
    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType), default=AccountType.UNKNOWN
    )
    tenant: Mapped[Tenant] = relationship(back_populates="accounts")
    uploads: Mapped[list["TransactionUpload"]] = relationship(back_populates="account")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")


class TransactionUpload(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transaction_uploads"
    __table_args__ = (
        UniqueConstraint("tenant_id", "account_id", "content_sha256"),
        Index("ix_transaction_uploads_tenant_created", "tenant_id", "created_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_accounts.id", ondelete="CASCADE")
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[UploadStatus] = mapped_column(Enum(UploadStatus))
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    accepted_rows: Mapped[int] = mapped_column(Integer, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0)
    column_mapping: Mapped[dict[str, str | None]] = mapped_column(JSON)
    row_errors: Mapped[list[dict[str, str | int]]] = mapped_column(JSON, default=list)
    source_format: Mapped[str] = mapped_column(String(12), default="csv")
    claimed_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    detected_content_type: Mapped[str] = mapped_column(String(120), default="text/csv")
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    parser_name: Mapped[str] = mapped_column(String(80), default="python-csv")
    parser_version: Mapped[str] = mapped_column(String(40), default="1")
    extraction_method: Mapped[str] = mapped_column(String(40), default="structured_text")
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    processing_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    statement_kind: Mapped[str] = mapped_column(String(20), default="unknown")
    tenant: Mapped[Tenant] = relationship(back_populates="uploads")
    account: Mapped[FinancialAccount] = relationship(back_populates="uploads")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="upload")


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "account_id", "fingerprint"),
        Index("ix_transactions_tenant_date", "tenant_id", "transaction_date"),
        Index("ix_transactions_tenant_category", "tenant_id", "category"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_accounts.id", ondelete="CASCADE")
    )
    upload_id: Mapped[UUID] = mapped_column(
        ForeignKey("transaction_uploads.id", ondelete="RESTRICT")
    )
    transaction_date: Mapped[date] = mapped_column(Date)
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    merchant_raw: Mapped[str] = mapped_column(String(255))
    merchant_normalized: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    external_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    balance_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    kind: Mapped[TransactionKind] = mapped_column(Enum(TransactionKind))
    category: Mapped[str] = mapped_column(String(80))
    classification_method: Mapped[ClassificationMethod] = mapped_column(Enum(ClassificationMethod))
    classification_confidence_bps: Mapped[int] = mapped_column(Integer)
    fingerprint: Mapped[str] = mapped_column(String(64))
    is_excluded_from_cashflow: Mapped[bool] = mapped_column(Boolean, default=False)
    source_evidence: Mapped[dict[str, int | str]] = mapped_column(JSON, default=dict)
    tenant: Mapped[Tenant] = relationship(back_populates="transactions")
    account: Mapped[FinancialAccount] = relationship(back_populates="transactions")
    upload: Mapped[TransactionUpload] = relationship(back_populates="transactions")
    corrections: Mapped[list["ClassificationCorrection"]] = relationship(
        back_populates="transaction"
    )


class ClassificationCorrection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "classification_corrections"
    __table_args__ = (Index("ix_classification_corrections_tenant", "tenant_id", "created_at"),)

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    transaction_id: Mapped[UUID] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"))
    corrected_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    previous_category: Mapped[str] = mapped_column(String(80))
    new_category: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(String(500))
    transaction: Mapped[Transaction] = relationship(back_populates="corrections")


class CalculationSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable, tenant-scoped input manifest for deterministic analytics."""

    __tablename__ = "calculation_snapshots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "input_sha256", "engine_version"),
        Index("ix_calculation_snapshots_tenant_created", "tenant_id", "created_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_accounts.id", ondelete="CASCADE")
    )
    as_of: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3))
    opening_balance_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    analysis_mode: Mapped[str] = mapped_column(String(20), default="cashflow")
    source_transaction_count: Mapped[int] = mapped_column(Integer)
    source_transaction_ids: Mapped[list[str]] = mapped_column(JSON)
    input_sha256: Mapped[str] = mapped_column(String(64))
    engine_version: Mapped[str] = mapped_column(String(40))
    anomaly_results: Mapped[list[dict[str, str | int]]] = mapped_column(JSON, default=list)
    # Deterministic spending summary, frozen with the snapshot for audit.
    spending_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class StoredRecurringPattern(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recurring_patterns"
    __table_args__ = (Index("ix_recurring_patterns_tenant_snapshot", "tenant_id", "snapshot_id"),)

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("calculation_snapshots.id", ondelete="CASCADE")
    )
    merchant: Mapped[str] = mapped_column(String(255))
    cadence: Mapped[str] = mapped_column(String(20))
    period_days: Mapped[int] = mapped_column(Integer)
    typical_amount_minor: Mapped[int] = mapped_column(BigInteger)
    confidence_bps: Mapped[int] = mapped_column(Integer)
    last_observed: Mapped[date] = mapped_column(Date)
    supporting_transaction_ids: Mapped[list[str]] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)


class StoredForecast(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "forecasts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "snapshot_id", "horizon_days", "engine_version"),
        Index("ix_forecasts_tenant_created", "tenant_id", "created_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("calculation_snapshots.id", ondelete="RESTRICT")
    )
    horizon_days: Mapped[int] = mapped_column(Integer)
    opening_balance_minor: Mapped[int] = mapped_column(BigInteger)
    minimum_balance_minor: Mapped[int] = mapped_column(BigInteger)
    assumptions: Mapped[list[str]] = mapped_column(JSON)
    engine_version: Mapped[str] = mapped_column(String(40))


class StoredForecastPoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "forecast_points"
    __table_args__ = (
        UniqueConstraint("forecast_id", "day"),
        Index("ix_forecast_points_forecast_day", "forecast_id", "day"),
    )

    forecast_id: Mapped[UUID] = mapped_column(ForeignKey("forecasts.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)
    balance_minor: Mapped[int] = mapped_column(BigInteger)
    recurring_flow_minor: Mapped[int] = mapped_column(BigInteger)
    estimated_variable_spend_minor: Mapped[int] = mapped_column(BigInteger)


class ScenarioRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scenario_runs"
    __table_args__ = (Index("ix_scenario_runs_tenant_created", "tenant_id", "created_at"),)

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    forecast_id: Mapped[UUID] = mapped_column(ForeignKey("forecasts.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(120))
    shocks: Mapped[list[dict[str, str | int]]] = mapped_column(JSON)
    minimum_balance_minor: Mapped[int] = mapped_column(BigInteger)
    first_shortfall_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ending_delta_minor: Mapped[int] = mapped_column(BigInteger)
    engine_version: Mapped[str] = mapped_column(String(40))


class ScenarioPoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scenario_points"
    __table_args__ = (
        UniqueConstraint("scenario_run_id", "day"),
        Index("ix_scenario_points_run_day", "scenario_run_id", "day"),
    )

    scenario_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("scenario_runs.id", ondelete="CASCADE")
    )
    day: Mapped[date] = mapped_column(Date)
    balance_minor: Mapped[int] = mapped_column(BigInteger)
    recurring_flow_minor: Mapped[int] = mapped_column(BigInteger)
    estimated_variable_spend_minor: Mapped[int] = mapped_column(BigInteger)


class AgentExecution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_executions"
    __table_args__ = (Index("ix_agent_executions_tenant_created", "tenant_id", "created_at"),)

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("calculation_snapshots.id", ondelete="RESTRICT")
    )
    # Null for spending advice grounded only in a snapshot (card or balance-free statements).
    forecast_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("forecasts.id", ondelete="RESTRICT"), nullable=True
    )
    scenario_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("scenario_runs.id", ondelete="RESTRICT"), nullable=True
    )
    question: Mapped[str] = mapped_column(String(1000))
    intent: Mapped[str] = mapped_column(String(40))
    status: Mapped[AgentRunStatus] = mapped_column(Enum(AgentRunStatus))
    verification_status: Mapped[VerificationStatus] = mapped_column(Enum(VerificationStatus))
    final_response: Mapped[str] = mapped_column(Text, default="")
    graph_version: Mapped[str] = mapped_column(String(40))
    prompt_version: Mapped[str] = mapped_column(String(40))
    model_id: Mapped[str] = mapped_column(String(120))
    revision_attempts: Mapped[int] = mapped_column(Integer, default=0)
    total_latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    artifact_lineage: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)


class AgentEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_events"
    __table_args__ = (
        UniqueConstraint("execution_id", "sequence"),
        Index("ix_agent_events_execution_sequence", "execution_id", "sequence"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_executions.id", ondelete="CASCADE")
    )
    sequence: Mapped[int] = mapped_column(Integer)
    node: Mapped[str] = mapped_column(String(50))
    event_type: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(String(500))
    details: Mapped[dict[str, str | int | bool | list[str]]] = mapped_column(JSON)
    model_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Recommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recommendations"
    __table_args__ = (Index("ix_recommendations_tenant_execution", "tenant_id", "execution_id"),)

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_executions.id", ondelete="CASCADE")
    )
    rank: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(180))
    explanation: Mapped[str] = mapped_column(Text)
    amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3))
    evidence_ids: Mapped[list[str]] = mapped_column(JSON)
    assumptions: Mapped[list[str]] = mapped_column(JSON)
    confidence_bps: Mapped[int] = mapped_column(Integer)
    verification_status: Mapped[VerificationStatus] = mapped_column(Enum(VerificationStatus))
    artifact_lineage: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)


class FinancialVerification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_verifications"
    __table_args__ = (Index("ix_verifications_tenant_execution", "tenant_id", "execution_id"),)

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_executions.id", ondelete="CASCADE")
    )
    recommendation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[VerificationStatus] = mapped_column(Enum(VerificationStatus))
    reasons: Mapped[list[str]] = mapped_column(JSON)
    checked_values: Mapped[dict[str, str | int | list[str]]] = mapped_column(JSON)
    verifier_version: Mapped[str] = mapped_column(String(40))


class GovernanceArtifact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "governance_artifacts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "artifact_type", "name", "version"),
        Index("ix_governance_artifacts_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    artifact_type: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(80))
    content_sha256: Mapped[str] = mapped_column(String(64))
    configuration: Mapped[dict[str, str | int | bool | list[str]]] = mapped_column(JSON)
    status: Mapped[GovernanceArtifactStatus] = mapped_column(Enum(GovernanceArtifactStatus))
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approval_source: Mapped[str] = mapped_column(String(80), default="pending")
    approval_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rollback_artifact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("governance_artifacts.id", ondelete="RESTRICT"), nullable=True
    )


class RiskRegisterEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risk_register_entries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "risk_id", "version"),
        Index("ix_risk_register_tenant_level", "tenant_id", "residual_risk"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    risk_id: Mapped[str] = mapped_column(String(40))
    version: Mapped[str] = mapped_column(String(40))
    category: Mapped[str] = mapped_column(String(80))
    likelihood: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel))
    impact: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel))
    affected_assets: Mapped[list[str]] = mapped_column(JSON)
    cause: Mapped[str] = mapped_column(Text)
    mitigation: Mapped[str] = mapped_column(Text)
    test_evidence: Mapped[list[str]] = mapped_column(JSON)
    owner_role: Mapped[str] = mapped_column(String(80))
    residual_risk: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel))
    acceptance_status: Mapped[str] = mapped_column(String(40))
    exception_record: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_on: Mapped[date] = mapped_column(Date)


class EvaluationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dataset_id", "dataset_version", "code_version"),
        Index("ix_evaluation_runs_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    dataset_id: Mapped[str] = mapped_column(String(120))
    dataset_version: Mapped[str] = mapped_column(String(80))
    sampling_method: Mapped[str] = mapped_column(String(160))
    metrics: Mapped[dict[str, int | float | str]] = mapped_column(JSON)
    thresholds: Mapped[dict[str, int | float | str]] = mapped_column(JSON)
    status: Mapped[EvaluationGateStatus] = mapped_column(Enum(EvaluationGateStatus))
    code_version: Mapped[str] = mapped_column(String(80))
    model_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    failures: Mapped[list[str]] = mapped_column(JSON)
    reviewer_disposition: Mapped[str] = mapped_column(String(80))
    duration_ms: Mapped[int] = mapped_column(Integer)


class HumanReviewCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "human_review_cases"
    __table_args__ = (Index("ix_human_review_tenant_status", "tenant_id", "status"),)

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    execution_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_executions.id", ondelete="RESTRICT"), nullable=True
    )
    recommendation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="RESTRICT"), nullable=True
    )
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(60))
    reason: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel))
    status: Mapped[HumanReviewStatus] = mapped_column(Enum(HumanReviewStatus))
    evidence_ids: Mapped[list[str]] = mapped_column(JSON)
    artifact_lineage: Mapped[dict[str, str]] = mapped_column(JSON)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class HumanDecision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "human_decisions"
    __table_args__ = (Index("ix_human_decisions_case_created", "review_case_id", "created_at"),)

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    review_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("human_review_cases.id", ondelete="RESTRICT")
    )
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    outcome: Mapped[HumanDecisionOutcome] = mapped_column(Enum(HumanDecisionOutcome))
    reason: Mapped[str] = mapped_column(Text)
    source_evidence: Mapped[list[str]] = mapped_column(JSON)
    artifact_lineage: Mapped[dict[str, str]] = mapped_column(JSON)


class DigestPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "digest_preferences"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id"),
        Index("ix_digest_preferences_due", "enabled", "next_due_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    weekday: Mapped[int] = mapped_column(Integer)
    local_time: Mapped[str] = mapped_column(String(5))
    timezone: Mapped[str] = mapped_column(String(64))
    next_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class DigestJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "digest_jobs"
    __table_args__ = (
        UniqueConstraint("job_key"),
        Index("ix_digest_jobs_tenant_created", "tenant_id", "created_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    preference_id: Mapped[UUID] = mapped_column(
        ForeignKey("digest_preferences.id", ondelete="CASCADE")
    )
    job_key: Mapped[str] = mapped_column(String(180))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[DigestJobStatus] = mapped_column(Enum(DigestJobStatus))
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("calculation_snapshots.id", ondelete="RESTRICT"), nullable=True
    )
    forecast_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("forecasts.id", ondelete="RESTRICT"), nullable=True
    )
    insight_kind: Mapped[str] = mapped_column(String(60))
    insight_amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    subject: Mapped[str] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)


class InAppNotification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "in_app_notifications"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dedupe_key"),
        Index("ix_notifications_user_created", "tenant_id", "user_id", "created_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    digest_job_id: Mapped[UUID] = mapped_column(ForeignKey("digest_jobs.id", ondelete="CASCADE"))
    dedupe_key: Mapped[str] = mapped_column(String(180))
    channel: Mapped[str] = mapped_column(String(30), default="in_app")
    status: Mapped[NotificationStatus] = mapped_column(Enum(NotificationStatus))
    subject: Mapped[str] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
