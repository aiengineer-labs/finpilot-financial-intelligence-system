from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SnapshotCreate(BaseModel):
    account_id: UUID
    as_of: date | None = None


class RecurringPatternResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    merchant: str
    cadence: str
    period_days: int
    typical_amount_minor: int
    confidence_bps: int
    last_observed: date
    supporting_transaction_ids: list[str]
    explanation: str


class SnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    as_of: date
    currency: str
    opening_balance_minor: int | None
    analysis_mode: Literal["cashflow", "spending"]
    source_transaction_count: int
    source_transaction_ids: list[str]
    input_sha256: str
    engine_version: str
    anomaly_results: list[dict[str, str | int]]
    recurring_patterns: list[RecurringPatternResponse]
    created_at: datetime


class ForecastCreate(BaseModel):
    snapshot_id: UUID
    horizon_days: Literal[30, 60, 90] = 30


class PointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    balance_minor: int
    recurring_flow_minor: int
    estimated_variable_spend_minor: int


class ForecastResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    snapshot_id: UUID
    horizon_days: int
    opening_balance_minor: int
    minimum_balance_minor: int
    assumptions: list[str]
    engine_version: str
    points: list[PointResponse]
    created_at: datetime


class ScenarioShockRequest(BaseModel):
    day: date
    amount_minor: int
    label: str = Field(min_length=1, max_length=120)


class ScenarioCreate(BaseModel):
    forecast_id: UUID
    name: str = Field(min_length=1, max_length=120)
    shocks: list[ScenarioShockRequest] = Field(min_length=1, max_length=24)


class ScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    forecast_id: UUID
    name: str
    shocks: list[dict[str, str | int]]
    minimum_balance_minor: int
    first_shortfall_date: date | None
    ending_delta_minor: int
    engine_version: str
    points: list[PointResponse]
    created_at: datetime
