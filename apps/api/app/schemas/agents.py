from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.database.models import AgentRunStatus, VerificationStatus


class AgentRunCreate(BaseModel):
    """Advice is grounded in a cash forecast or, for balance-free statements, a snapshot."""

    forecast_id: UUID | None = None
    snapshot_id: UUID | None = None
    scenario_id: UUID | None = None
    question: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def one_grounding(self) -> "AgentRunCreate":
        if (self.forecast_id is None) == (self.snapshot_id is None):
            raise ValueError("provide exactly one of forecast_id or snapshot_id")
        if self.scenario_id is not None and self.forecast_id is None:
            raise ValueError("scenario_id requires forecast_id")
        return self


class AgentEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sequence: int
    node: str
    event_type: str
    summary: str
    details: dict[str, object]
    model_id: str | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    created_at: datetime


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    rank: int
    title: str
    explanation: str
    amount_minor: int | None
    currency: str
    evidence_ids: list[str]
    assumptions: list[str]
    confidence_bps: int
    verification_status: VerificationStatus
    artifact_lineage: dict[str, str]


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    snapshot_id: UUID
    forecast_id: UUID | None
    scenario_run_id: UUID | None
    question: str
    intent: str
    status: AgentRunStatus
    verification_status: VerificationStatus
    final_response: str
    graph_version: str
    prompt_version: str
    model_id: str
    revision_attempts: int
    total_latency_ms: int
    total_input_tokens: int
    total_output_tokens: int
    artifact_lineage: dict[str, str]
    events: list[AgentEventResponse]
    recommendations: list[RecommendationResponse]
    created_at: datetime
