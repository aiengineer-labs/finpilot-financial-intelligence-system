from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    CalculationSnapshot,
    DigestJob,
    DigestJobStatus,
    DigestPreference,
    InAppNotification,
    NotificationStatus,
    StoredForecast,
)


def next_weekly_due(*, weekday: int, local_time: str, timezone: str, after: datetime) -> datetime:
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("unknown IANA timezone") from exc
    hour, minute = (int(part) for part in local_time.split(":"))
    localized = after.astimezone(zone)
    days_ahead = (weekday - localized.weekday()) % 7
    candidate = localized.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(
        days=days_ahead
    )
    if candidate <= localized:
        candidate += timedelta(days=7)
    return candidate.astimezone(UTC)


async def upsert_preference(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    enabled: bool,
    weekday: int,
    local_time: str,
    timezone: str,
    now: datetime | None = None,
) -> DigestPreference:
    current = now or datetime.now(UTC)
    next_due = next_weekly_due(
        weekday=weekday, local_time=local_time, timezone=timezone, after=current
    )
    preference = await session.scalar(
        select(DigestPreference).where(
            DigestPreference.tenant_id == tenant_id, DigestPreference.user_id == user_id
        )
    )
    if preference is None:
        preference = DigestPreference(
            tenant_id=tenant_id,
            user_id=user_id,
            enabled=enabled,
            weekday=weekday,
            local_time=local_time,
            timezone=timezone,
            next_due_at=next_due,
        )
        session.add(preference)
    else:
        preference.enabled = enabled
        preference.weekday = weekday
        preference.local_time = local_time
        preference.timezone = timezone
        preference.next_due_at = next_due
    await session.commit()
    await session.refresh(preference)
    return preference


@dataclass(frozen=True)
class DigestInsight:
    kind: str
    amount_minor: int | None
    currency: str
    subject: str
    body: str
    snapshot_id: UUID | None
    forecast_id: UUID | None


async def _insight(session: AsyncSession, tenant_id: UUID) -> DigestInsight:
    forecast = await session.scalar(
        select(StoredForecast)
        .where(StoredForecast.tenant_id == tenant_id)
        .order_by(StoredForecast.created_at.desc())
        .limit(1)
    )
    if forecast is None:
        return DigestInsight(
            kind="setup_required",
            amount_minor=None,
            currency="INR",
            subject="Your FinPilot weekly check-in",
            body=(
                "Import a statement and create a forecast to receive a data-backed weekly insight."
            ),
            snapshot_id=None,
            forecast_id=None,
        )
    snapshot = await session.scalar(
        select(CalculationSnapshot).where(CalculationSnapshot.id == forecast.snapshot_id)
    )
    currency = snapshot.currency if snapshot is not None else "INR"
    amount = forecast.minimum_balance_minor
    formatted = f"{currency} {abs(amount) / 100:,.2f}"
    if amount < 0:
        body = (
            f"Your {forecast.horizon_days}-day deterministic forecast reaches a minimum "
            f"balance of -{formatted}. Review upcoming commitments before spending."
        )
        kind = "forecast_shortfall"
    else:
        body = (
            f"Your {forecast.horizon_days}-day deterministic forecast stays at or above "
            f"{formatted}. This is an estimate based only on recorded history and assumptions."
        )
        kind = "forecast_minimum"
    return DigestInsight(
        kind=kind,
        amount_minor=amount,
        currency=currency,
        subject="Your verified FinPilot weekly insight",
        body=body,
        snapshot_id=forecast.snapshot_id,
        forecast_id=forecast.id,
    )


async def dispatch_due_digests(
    session: AsyncSession, *, now: datetime | None = None, limit: int = 25
) -> list[DigestJob]:
    current = now or datetime.now(UTC)
    preferences = list(
        await session.scalars(
            select(DigestPreference)
            .where(DigestPreference.enabled.is_(True), DigestPreference.next_due_at <= current)
            .order_by(DigestPreference.next_due_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    jobs: list[DigestJob] = []
    for preference in preferences:
        scheduled_for = preference.next_due_at
        insight = await _insight(session, preference.tenant_id)
        job_key = f"weekly:{preference.id}:{scheduled_for.astimezone(UTC).isoformat()}"
        job = DigestJob(
            tenant_id=preference.tenant_id,
            user_id=preference.user_id,
            preference_id=preference.id,
            job_key=job_key,
            scheduled_for=scheduled_for,
            status=DigestJobStatus.CLAIMED,
            claimed_at=current,
            attempts=1,
            snapshot_id=insight.snapshot_id,
            forecast_id=insight.forecast_id,
            insight_kind=insight.kind,
            insight_amount_minor=insight.amount_minor,
            currency=insight.currency,
            subject=insight.subject,
            body=insight.body,
        )
        session.add(job)
        await session.flush()
        session.add(
            InAppNotification(
                tenant_id=preference.tenant_id,
                user_id=preference.user_id,
                digest_job_id=job.id,
                dedupe_key=job_key,
                channel="in_app",
                status=NotificationStatus.DELIVERED,
                subject=insight.subject,
                body=insight.body,
                delivered_at=current,
            )
        )
        job.status = DigestJobStatus.DELIVERED
        job.completed_at = current
        preference.last_dispatched_at = current
        preference.next_due_at = next_weekly_due(
            weekday=preference.weekday,
            local_time=preference.local_time,
            timezone=preference.timezone,
            after=current,
        )
        jobs.append(job)
    await session.commit()
    for job in jobs:
        await session.refresh(job)
    return jobs
