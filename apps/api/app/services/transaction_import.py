from pathlib import Path
from time import perf_counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    FinancialAccount,
    Transaction,
    TransactionUpload,
    UploadStatus,
)
from app.services.csv_ingestion import CSVColumnMapping, content_sha256
from app.services.statement_ingestion import ParsedStatement, parse_statement


async def find_account(
    session: AsyncSession, tenant_id: UUID, account_id: UUID
) -> FinancialAccount | None:
    return await session.scalar(
        select(FinancialAccount).where(
            FinancialAccount.id == account_id, FinancialAccount.tenant_id == tenant_id
        )
    )


async def import_transactions(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    account_id: UUID,
    filename: str,
    claimed_content_type: str | None,
    content: bytes,
    mapping: CSVColumnMapping,
) -> tuple[TransactionUpload, bool]:
    checksum = content_sha256(content)
    started_at = perf_counter()
    statement: ParsedStatement = parse_statement(
        content,
        filename=filename,
        claimed_content_type=claimed_content_type,
        mapping=mapping,
    )
    existing_upload = await session.scalar(
        select(TransactionUpload).where(
            TransactionUpload.tenant_id == tenant_id,
            TransactionUpload.account_id == account_id,
            TransactionUpload.content_sha256 == checksum,
        )
    )
    if existing_upload is not None:
        return existing_upload, True

    parsed = statement.transactions
    fingerprints = [row.fingerprint for row in parsed.rows]
    existing_fingerprints: set[str] = set()
    if fingerprints:
        existing_fingerprints = set(
            await session.scalars(
                select(Transaction.fingerprint).where(
                    Transaction.tenant_id == tenant_id,
                    Transaction.account_id == account_id,
                    Transaction.fingerprint.in_(fingerprints),
                )
            )
        )
    accepted_rows = len(parsed.rows) - len(existing_fingerprints)
    duplicate_rows = parsed.duplicate_rows + len(existing_fingerprints)
    status = UploadStatus.COMPLETED_WITH_ERRORS if parsed.errors else UploadStatus.COMPLETED
    upload = TransactionUpload(
        tenant_id=tenant_id,
        account_id=account_id,
        filename=Path(filename).name[:255] or "transactions.csv",
        content_sha256=checksum,
        status=status,
        total_rows=parsed.total_rows,
        accepted_rows=accepted_rows,
        rejected_rows=len(parsed.errors),
        duplicate_rows=duplicate_rows,
        column_mapping=mapping.model_dump(),
        row_errors=[error.__dict__ for error in parsed.errors],
        source_format=statement.format.value,
        claimed_content_type=claimed_content_type,
        detected_content_type=statement.detected_content_type,
        byte_size=len(content),
        parser_name=statement.parser_name,
        parser_version=statement.parser_version,
        extraction_method=statement.extraction_method,
        page_count=statement.page_count,
        warnings=statement.warnings,
        processing_duration_ms=max(0, round((perf_counter() - started_at) * 1000)),
    )
    session.add(upload)
    await session.flush()
    session.add_all(
        [
            Transaction(
                tenant_id=tenant_id,
                account_id=account_id,
                upload_id=upload.id,
                transaction_date=row.transaction_date.date(),
                amount_minor=row.amount_minor,
                currency=row.currency,
                merchant_raw=row.merchant_raw,
                merchant_normalized=row.merchant_normalized,
                description=row.description,
                external_transaction_id=row.external_transaction_id,
                balance_minor=row.balance_minor,
                kind=row.kind,
                category=row.category,
                classification_method=row.classification_method,
                classification_confidence_bps=row.classification_confidence_bps,
                fingerprint=row.fingerprint,
                is_excluded_from_cashflow=row.is_excluded_from_cashflow,
                source_evidence=statement.source_evidence[row.fingerprint],
            )
            for row in parsed.rows
            if row.fingerprint not in existing_fingerprints
        ]
    )
    await session.commit()
    await session.refresh(upload)
    return upload, False
