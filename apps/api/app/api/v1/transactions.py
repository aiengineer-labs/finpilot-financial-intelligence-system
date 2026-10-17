import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import TenantContext, tenant_context
from app.database.models import (
    ClassificationCorrection,
    ClassificationMethod,
    Transaction,
    TransactionUpload,
)
from app.database.session import get_session
from app.schemas.transactions import (
    CategoryCorrectionRequest,
    TransactionPage,
    TransactionResponse,
    UploadResponse,
)
from app.services.csv_ingestion import MAX_UPLOAD_BYTES, CSVColumnMapping
from app.services.statement_ingestion import StatementValidationError
from app.services.transaction_import import (
    AccountTypeMismatchError,
    find_account,
    import_transactions,
)

router = APIRouter(tags=["transactions"])


def _upload_response(upload, replayed: bool) -> UploadResponse:  # type: ignore[no-untyped-def]
    return UploadResponse(
        id=upload.id,
        filename=upload.filename,
        status=upload.status,
        total_rows=upload.total_rows,
        accepted_rows=upload.accepted_rows,
        rejected_rows=upload.rejected_rows,
        duplicate_rows=upload.duplicate_rows,
        row_errors=upload.row_errors,
        source_format=upload.source_format,
        detected_content_type=upload.detected_content_type,
        parser_name=upload.parser_name,
        parser_version=upload.parser_version,
        extraction_method=upload.extraction_method,
        page_count=upload.page_count,
        warnings=upload.warnings,
        processing_duration_ms=upload.processing_duration_ms,
        statement_kind=upload.statement_kind,
        replayed=replayed,
    )


@router.post("/accounts/{account_id}/transaction-uploads", response_model=UploadResponse)
async def upload_transactions(
    account_id: UUID,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    mapping_json: Annotated[str, Form(alias="mapping")],
    file: Annotated[UploadFile, File()],
) -> UploadResponse:
    account = await find_account(session, context.tenant_id, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="A .csv or .pdf bank statement is required",
        )
    try:
        mapping = CSVColumnMapping.model_validate(json.loads(mapping_json))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        upload, replayed = await import_transactions(
            session,
            tenant_id=context.tenant_id,
            account=account,
            filename=file.filename,
            claimed_content_type=file.content_type,
            content=content,
            mapping=mapping,
        )
    except AccountTypeMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": exc.code,
                "message": str(exc),
                "statement_kind": exc.statement_kind.value,
            },
        ) from exc
    except StatementValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _upload_response(upload, replayed)


@router.get("/transaction-uploads/{upload_id}", response_model=UploadResponse)
async def get_transaction_upload(
    upload_id: UUID,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UploadResponse:
    upload = await session.scalar(
        select(TransactionUpload).where(
            TransactionUpload.id == upload_id,
            TransactionUpload.tenant_id == context.tenant_id,
        )
    )
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="upload not found")
    return _upload_response(upload, replayed=False)


@router.get("/transactions", response_model=TransactionPage)
async def list_transactions(
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    account_id: UUID | None = None,
) -> TransactionPage:
    scope = Transaction.tenant_id == context.tenant_id
    if account_id is not None:
        scope = and_(scope, Transaction.account_id == account_id)
    total = await session.scalar(select(func.count()).select_from(Transaction).where(scope))
    rows = await session.scalars(
        select(Transaction)
        .where(scope)
        .order_by(Transaction.transaction_date.desc(), Transaction.id)
        .limit(limit)
        .offset(offset)
    )
    return TransactionPage(
        items=[TransactionResponse.model_validate(row) for row in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.patch("/transactions/{transaction_id}/category", response_model=TransactionResponse)
async def correct_category(
    transaction_id: UUID,
    body: CategoryCorrectionRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Transaction:
    transaction = await session.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id, Transaction.tenant_id == context.tenant_id
        )
    )
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="transaction not found")
    session.add(
        ClassificationCorrection(
            tenant_id=context.tenant_id,
            transaction_id=transaction.id,
            corrected_by_user_id=context.user.id,
            previous_category=transaction.category,
            new_category=body.category,
            reason=body.reason,
        )
    )
    transaction.category = body.category
    transaction.classification_method = ClassificationMethod.HUMAN
    transaction.classification_confidence_bps = 10_000
    await session.commit()
    await session.refresh(transaction)
    return transaction
