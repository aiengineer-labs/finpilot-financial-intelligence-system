from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.database.models import ClassificationMethod, TransactionKind, UploadStatus


class UploadResponse(BaseModel):
    id: UUID
    filename: str
    status: UploadStatus
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    duplicate_rows: int
    row_errors: list[dict[str, str | int]]
    source_format: str
    detected_content_type: str
    parser_name: str
    parser_version: str
    extraction_method: str
    page_count: int | None
    warnings: list[str]
    processing_duration_ms: int
    statement_kind: str
    replayed: bool = False


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    upload_id: UUID
    transaction_date: date
    amount_minor: int
    currency: str
    merchant_raw: str
    merchant_normalized: str
    description: str
    external_transaction_id: str | None
    balance_minor: int | None
    kind: TransactionKind
    category: str
    classification_method: ClassificationMethod
    classification_confidence_bps: int
    is_excluded_from_cashflow: bool
    source_evidence: dict[str, int | str]
    created_at: datetime


class TransactionPage(BaseModel):
    items: list[TransactionResponse]
    total: int
    limit: int
    offset: int


class CategoryCorrectionRequest(BaseModel):
    category: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    reason: str = Field(min_length=3, max_length=500)
