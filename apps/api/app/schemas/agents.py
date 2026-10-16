from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.database.models import AgentRunStatus, VerificationStatus


class AgentRunCreate(BaseModel):
    forecast_id: UUID
    scenario_id: UUID | None = None
    question: str = Field(min_length=3, max_length=1000)


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


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    snapshot_id: UUID
    forecast_id: UUID
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
    events: list[AgentEventResponse]
    recommendations: list[RecommendationResponse]
    created_at: datetime
