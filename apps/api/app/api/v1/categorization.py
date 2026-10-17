from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.specialists import CATEGORIZER_PROMPT_VERSION
from app.auth.dependencies import TenantContext, tenant_context
from app.core.settings import Settings, get_settings
from app.database.session import get_session
from app.schemas.categorization import CategorizationRunResponse
from app.services.semantic_categorization import (
    CategorizerUnavailableError,
    categorize_ambiguous_rows,
)

router = APIRouter(tags=["categorization"])


@router.post(
    "/accounts/{account_id}/categorization-runs", response_model=CategorizationRunResponse
)
async def post_categorization_run(
    account_id: UUID,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CategorizationRunResponse:
    """Ask Mesh to label rows the rules could not place; code decides what is applied."""
    try:
        result = await categorize_ambiguous_rows(
            session,
            tenant_id=context.tenant_id,
            user_id=context.user.id,
            account_id=account_id,
            settings=settings,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CategorizerUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    run = result.run
    return CategorizationRunResponse(
        id=run.id if run else None,
        account_id=account_id,
        status="completed" if run else "not_needed",
        prompt_version=run.prompt_version if run else CATEGORIZER_PROMPT_VERSION,
        model_id=run.model_id if run else None,
        rows_pending=result.rows_pending,
        labels_sent=run.labels_sent if run else 0,
        labels_withheld=result.labels_withheld,
        rows_updated=run.rows_updated if run else 0,
        rows_remaining=result.rows_remaining,
        latency_ms=run.latency_ms if run else 0,
        input_tokens=run.input_tokens if run else 0,
        output_tokens=run.output_tokens if run else 0,
        details=run.details if run else {},
        created_at=run.created_at if run else None,
    )
