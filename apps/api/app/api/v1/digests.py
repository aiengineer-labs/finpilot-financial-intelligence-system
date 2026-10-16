import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import TenantContext, tenant_context
from app.core.settings import Settings, get_settings
from app.database.models import DigestJob, DigestPreference, InAppNotification
from app.database.session import get_session
from app.schemas.digests import (
    DigestJobResponse,
    DigestPreferenceResponse,
    DigestPreferenceUpdate,
    DispatchResponse,
    NotificationResponse,
)
from app.services.digests import dispatch_due_digests, upsert_preference

router = APIRouter(prefix="/digests", tags=["digests"])


@router.get("/preference", response_model=DigestPreferenceResponse | None)
async def get_preference(
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DigestPreference | None:
    return await session.scalar(
        select(DigestPreference).where(
            DigestPreference.tenant_id == context.tenant_id,
            DigestPreference.user_id == context.user.id,
        )
    )


@router.put("/preference", response_model=DigestPreferenceResponse)
async def put_preference(
    body: DigestPreferenceUpdate,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DigestPreference:
    try:
        return await upsert_preference(
            session,
            tenant_id=context.tenant_id,
            user_id=context.user.id,
            enabled=body.enabled,
            weekday=body.weekday,
            local_time=body.local_time,
            timezone=body.timezone,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("/jobs", response_model=list[DigestJobResponse])
async def list_jobs(
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[DigestJob]:
    return list(
        await session.scalars(
            select(DigestJob)
            .where(
                DigestJob.tenant_id == context.tenant_id,
                DigestJob.user_id == context.user.id,
            )
            .order_by(DigestJob.created_at.desc())
            .limit(50)
        )
    )


@router.get("/notifications", response_model=list[NotificationResponse])
async def list_notifications(
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[InAppNotification]:
    return list(
        await session.scalars(
            select(InAppNotification)
            .where(
                InAppNotification.tenant_id == context.tenant_id,
                InAppNotification.user_id == context.user.id,
            )
            .order_by(InAppNotification.created_at.desc())
            .limit(50)
        )
    )


@router.get("/dispatch", response_model=DispatchResponse)
async def dispatch(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> DispatchResponse:
    expected = settings.cron_secret.get_secret_value() if settings.cron_secret else ""
    supplied = authorization.removeprefix("Bearer ") if authorization else ""
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid cron token")
    jobs = await dispatch_due_digests(session, limit=settings.digest_dispatch_limit)
    return DispatchResponse(
        claimed=len(jobs),
        delivered=sum(job.status.value == "delivered" for job in jobs),
        failed=sum(job.status.value == "failed" for job in jobs),
        job_ids=[job.id for job in jobs],
    )
