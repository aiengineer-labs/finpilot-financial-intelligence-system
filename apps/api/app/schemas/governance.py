from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.database.models import (
    EvaluationGateStatus,
    GovernanceArtifactStatus,
    HumanDecisionOutcome,
    HumanReviewStatus,
    RiskLevel,
)


class GovernanceArtifactCreate(BaseModel):
    artifact_type: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=120)
    version: str = Field(min_length=1, max_length=80)
    configuration: dict[str, str | int | bool | list[str]]
    rollback_artifact_id: UUID | None = None


class GovernanceArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    artifact_type: str
    name: str
    version: str
    content_sha256: str
    configuration: dict[str, str | int | bool | list[str]]
    status: GovernanceArtifactStatus
    owner_user_id: UUID
    approved_by_user_id: UUID | None
    approval_source: str
    approval_reason: str | None
    approved_at: datetime | None
    rollback_artifact_id: UUID | None
    created_at: datetime


class ArtifactApprovalRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=500)


class RiskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    risk_id: str
    version: str
    category: str
    likelihood: RiskLevel
    impact: RiskLevel
    affected_assets: list[str]
    cause: str
    mitigation: str
    test_evidence: list[str]
    owner_role: str
    residual_risk: RiskLevel
    acceptance_status: str
    exception_record: str | None
    expires_on: date | None
    review_on: date


class EvaluationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: str
    dataset_version: str
    sampling_method: str
    metrics: dict[str, int | float | str]
    thresholds: dict[str, int | float | str]
    status: EvaluationGateStatus
    code_version: str
    model_id: str | None
    failures: list[str]
    reviewer_disposition: str
    duration_ms: int
    created_at: datetime


class HumanReviewCreate(BaseModel):
    execution_id: UUID | None = None
    recommendation_id: UUID | None = None
    reason: str = Field(min_length=10, max_length=1000)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class HumanReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    execution_id: UUID | None
    recommendation_id: UUID | None
    requested_by_user_id: UUID | None
    source: str
    reason: str
    risk_level: RiskLevel
    status: HumanReviewStatus
    evidence_ids: list[str]
    artifact_lineage: dict[str, str]
    resolved_at: datetime | None
    created_at: datetime


class HumanDecisionCreate(BaseModel):
    outcome: HumanDecisionOutcome
    reason: str = Field(min_length=10, max_length=1000)


class HumanDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    review_case_id: UUID
    reviewer_user_id: UUID
    outcome: HumanDecisionOutcome
    reason: str
    source_evidence: list[str]
    artifact_lineage: dict[str, str]
    created_at: datetime


class GovernanceSummaryResponse(BaseModel):
    artifacts: int
    risks: int
    pending_reviews: int
    evaluation_failures: int
    rejected_recommendations: int
    release_ready: bool
    release_blockers: list[str]
    drift_alerts: list[str]
    baseline_version: str
