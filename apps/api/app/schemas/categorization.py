from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


class CategorizationRunResponse(BaseModel):
    """Outcome of one Mesh categorization pass; `not_needed` means no model call was made."""

    id: UUID | None
    account_id: UUID
    status: Literal["not_needed", "completed"]
    prompt_version: str
    model_id: str | None
    rows_pending: int
    labels_sent: int
    labels_withheld: int
    rows_updated: int
    rows_remaining: int
    latency_ms: int
    input_tokens: int
    output_tokens: int
    details: dict[str, Any]
    created_at: datetime | None
