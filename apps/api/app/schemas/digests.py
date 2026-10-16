from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.database.models import DigestJobStatus, NotificationStatus


class DigestPreferenceUpdate(BaseModel):
    enabled: bool = True
    weekday: int = Field(default=0, ge=0, le=6)
    local_time: str = "09:00"
    timezone: str = Field(default="Asia/Kolkata", min_length=1, max_length=64)

    @field_validator("local_time")
    @classmethod
    def valid_time(cls, value: str) -> str:
        try:
            hour_text, minute_text = value.split(":", maxsplit=1)
            hour, minute = int(hour_text), int(minute_text)
        except (TypeError, ValueError) as exc:
            raise ValueError("local_time must use HH:MM") from exc
        if not 0 <= hour <= 23 or not 0 <= minute <= 59 or len(value) != 5:
            raise ValueError("local_time must use HH:MM")
        return value


class DigestPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    enabled: bool
    weekday: int
    local_time: str
    timezone: str
    next_due_at: datetime
    last_dispatched_at: datetime | None


class DigestJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_key: str
    scheduled_for: datetime
    status: DigestJobStatus
    snapshot_id: UUID | None
    forecast_id: UUID | None
    insight_kind: str
    insight_amount_minor: int | None
    currency: str
    subject: str
    body: str
    attempts: int
    created_at: datetime


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    digest_job_id: UUID
    status: NotificationStatus
    subject: str
    body: str
    delivered_at: datetime | None
    read_at: datetime | None
    created_at: datetime


class DispatchResponse(BaseModel):
    claimed: int
    delivered: int
    failed: int
    job_ids: list[UUID]
