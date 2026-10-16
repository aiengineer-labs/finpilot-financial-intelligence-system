from __future__ import annotations

import hashlib
import json
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    CalculationSnapshot,
    FinancialAccount,
    ScenarioPoint,
    ScenarioRun,
    StoredForecast,
    StoredForecastPoint,
    StoredRecurringPattern,
    Transaction,
)
from app.engines.financial import (
    EngineTransaction,
    Forecast,
    ForecastPoint,
    RecurringPattern,
    ScenarioShock,
    build_forecast,
    detect_anomalies,
    detect_recurrence,
    run_scenario,
)

ENGINE_VERSION = "financial-v1"


def _engine_transaction(row: Transaction) -> EngineTransaction:
    return EngineTransaction(
        id=str(row.id),
        transaction_date=row.transaction_date,
        amount_minor=row.amount_minor,
        merchant=row.merchant_normalized,
        category=row.category,
        kind=row.kind,
        is_excluded_from_cashflow=row.is_excluded_from_cashflow,
        balance_minor=row.balance_minor,
    )


def _snapshot_hash(account: FinancialAccount, as_of: date, rows: list[Transaction]) -> str:
    manifest = {
        "account_id": str(account.id),
        "as_of": as_of.isoformat(),
        "currency": account.currency,
        "transactions": [
            {
                "id": str(row.id),
                "date": row.transaction_date.isoformat(),
                "amount_minor": row.amount_minor,
                "balance_minor": row.balance_minor,
                "merchant": row.merchant_normalized,
                "category": row.category,
                "kind": row.kind.value,
                "excluded": row.is_excluded_from_cashflow,
            }
            for row in rows
        ],
    }
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


async def create_snapshot(
    session: AsyncSession, *, tenant_id: UUID, account_id: UUID, requested_as_of: date | None
) -> tuple[CalculationSnapshot, list[StoredRecurringPattern]]:
    account = await session.scalar(
        select(FinancialAccount).where(
            FinancialAccount.id == account_id, FinancialAccount.tenant_id == tenant_id
        )
    )
    if account is None:
        raise LookupError("account not found")
    query = select(Transaction).where(
        Transaction.tenant_id == tenant_id, Transaction.account_id == account_id
    )
    if requested_as_of is not None:
        query = query.where(Transaction.transaction_date <= requested_as_of)
    result = await session.scalars(query.order_by(Transaction.transaction_date, Transaction.id))
    rows = list(result)
    if not rows:
        raise ValueError("at least one imported transaction is required")
    as_of = requested_as_of or rows[-1].transaction_date
    latest = rows[-1]
    if latest.transaction_date != as_of or latest.balance_minor is None:
        raise ValueError(
            "the latest transaction on the snapshot date must include a known source balance"
        )
    input_sha256 = _snapshot_hash(account, as_of, rows)
    existing = await session.scalar(
        select(CalculationSnapshot).where(
            CalculationSnapshot.tenant_id == tenant_id,
            CalculationSnapshot.input_sha256 == input_sha256,
            CalculationSnapshot.engine_version == ENGINE_VERSION,
        )
    )
    if existing is not None:
        patterns = list(
            await session.scalars(
                select(StoredRecurringPattern)
                .where(
                    StoredRecurringPattern.tenant_id == tenant_id,
                    StoredRecurringPattern.snapshot_id == existing.id,
                )
                .order_by(StoredRecurringPattern.merchant, StoredRecurringPattern.id)
            )
        )
        return existing, patterns

    engine_rows = [_engine_transaction(row) for row in rows]
    recurrences = detect_recurrence(engine_rows)
    anomalies = detect_anomalies(engine_rows)
    snapshot = CalculationSnapshot(
        tenant_id=tenant_id,
        account_id=account_id,
        as_of=as_of,
        currency=account.currency,
        opening_balance_minor=latest.balance_minor,
        source_transaction_count=len(rows),
        source_transaction_ids=[str(row.id) for row in rows],
        input_sha256=input_sha256,
        engine_version=ENGINE_VERSION,
        anomaly_results=[
            {
                "transaction_id": anomaly.transaction_id,
                "observed_amount_minor": anomaly.observed_amount_minor,
                "baseline_median_minor": anomaly.baseline_median_minor,
                "robust_score_milli": anomaly.robust_score_milli,
                "severity": anomaly.severity,
                "explanation": anomaly.explanation,
            }
            for anomaly in anomalies
        ],
    )
    session.add(snapshot)
    await session.flush()
    stored_patterns = [
        StoredRecurringPattern(
            tenant_id=tenant_id,
            snapshot_id=snapshot.id,
            merchant=pattern.merchant,
            cadence=pattern.cadence,
            period_days=pattern.period_days,
            typical_amount_minor=pattern.typical_amount_minor,
            confidence_bps=pattern.confidence_bps,
            last_observed=pattern.last_observed,
            supporting_transaction_ids=list(pattern.supporting_transaction_ids),
            explanation=pattern.explanation,
        )
        for pattern in recurrences
    ]
    session.add_all(stored_patterns)
    await session.commit()
    await session.refresh(snapshot)
    return snapshot, stored_patterns


async def get_snapshot(
    session: AsyncSession, *, tenant_id: UUID, snapshot_id: UUID
) -> tuple[CalculationSnapshot, list[StoredRecurringPattern]] | None:
    snapshot = await session.scalar(
        select(CalculationSnapshot).where(
            CalculationSnapshot.id == snapshot_id, CalculationSnapshot.tenant_id == tenant_id
        )
    )
    if snapshot is None:
        return None
    patterns = list(
        await session.scalars(
            select(StoredRecurringPattern)
            .where(
                StoredRecurringPattern.snapshot_id == snapshot_id,
                StoredRecurringPattern.tenant_id == tenant_id,
            )
            .order_by(StoredRecurringPattern.merchant, StoredRecurringPattern.id)
        )
    )
    return snapshot, patterns


async def create_forecast(
    session: AsyncSession, *, tenant_id: UUID, snapshot_id: UUID, horizon_days: int
) -> tuple[StoredForecast, list[StoredForecastPoint]]:
    loaded = await get_snapshot(session, tenant_id=tenant_id, snapshot_id=snapshot_id)
    if loaded is None:
        raise LookupError("snapshot not found")
    snapshot, stored_patterns = loaded
    existing = await session.scalar(
        select(StoredForecast).where(
            StoredForecast.tenant_id == tenant_id,
            StoredForecast.snapshot_id == snapshot_id,
            StoredForecast.horizon_days == horizon_days,
            StoredForecast.engine_version == ENGINE_VERSION,
        )
    )
    if existing is not None:
        points = list(
            await session.scalars(
                select(StoredForecastPoint)
                .where(StoredForecastPoint.forecast_id == existing.id)
                .order_by(StoredForecastPoint.day)
            )
        )
        return existing, points

    transaction_ids = [UUID(value) for value in snapshot.source_transaction_ids]
    rows = list(
        await session.scalars(
            select(Transaction)
            .where(
                Transaction.tenant_id == tenant_id,
                Transaction.id.in_(transaction_ids),
            )
            .order_by(Transaction.transaction_date, Transaction.id)
        )
    )
    if len(rows) != snapshot.source_transaction_count:
        raise ValueError("snapshot source manifest is incomplete")
    patterns = [
        RecurringPattern(
            merchant=item.merchant,
            cadence=item.cadence,
            period_days=item.period_days,
            typical_amount_minor=item.typical_amount_minor,
            confidence_bps=item.confidence_bps,
            last_observed=item.last_observed,
            supporting_transaction_ids=tuple(item.supporting_transaction_ids),
            explanation=item.explanation,
        )
        for item in stored_patterns
    ]
    computed = build_forecast(
        as_of=snapshot.as_of,
        horizon_days=horizon_days,
        opening_balance_minor=snapshot.opening_balance_minor,
        transactions=[_engine_transaction(row) for row in rows],
        patterns=patterns,
    )
    forecast = StoredForecast(
        tenant_id=tenant_id,
        snapshot_id=snapshot.id,
        horizon_days=horizon_days,
        opening_balance_minor=computed.opening_balance_minor,
        minimum_balance_minor=computed.minimum_balance_minor,
        assumptions=list(computed.assumptions),
        engine_version=ENGINE_VERSION,
    )
    session.add(forecast)
    await session.flush()
    points = [
        StoredForecastPoint(
            forecast_id=forecast.id,
            day=point.day,
            balance_minor=point.balance_minor,
            recurring_flow_minor=point.recurring_flow_minor,
            estimated_variable_spend_minor=point.estimated_variable_spend_minor,
        )
        for point in computed.points
    ]
    session.add_all(points)
    await session.commit()
    await session.refresh(forecast)
    return forecast, points


async def get_forecast(
    session: AsyncSession, *, tenant_id: UUID, forecast_id: UUID
) -> tuple[StoredForecast, list[StoredForecastPoint]] | None:
    forecast = await session.scalar(
        select(StoredForecast).where(
            StoredForecast.id == forecast_id, StoredForecast.tenant_id == tenant_id
        )
    )
    if forecast is None:
        return None
    points = list(
        await session.scalars(
            select(StoredForecastPoint)
            .where(StoredForecastPoint.forecast_id == forecast.id)
            .order_by(StoredForecastPoint.day)
        )
    )
    return forecast, points


async def create_scenario(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    forecast_id: UUID,
    name: str,
    shocks: list[ScenarioShock],
) -> tuple[ScenarioRun, list[ScenarioPoint]]:
    loaded = await get_forecast(session, tenant_id=tenant_id, forecast_id=forecast_id)
    if loaded is None:
        raise LookupError("forecast not found")
    forecast, stored_points = loaded
    snapshot = await session.scalar(
        select(CalculationSnapshot).where(
            CalculationSnapshot.id == forecast.snapshot_id,
            CalculationSnapshot.tenant_id == tenant_id,
        )
    )
    if snapshot is None:
        raise ValueError("forecast snapshot is unavailable")
    baseline = Forecast(
        as_of=snapshot.as_of,
        horizon_days=forecast.horizon_days,
        opening_balance_minor=forecast.opening_balance_minor,
        points=tuple(
            ForecastPoint(
                item.day,
                item.balance_minor,
                item.recurring_flow_minor,
                item.estimated_variable_spend_minor,
            )
            for item in stored_points
        ),
        assumptions=tuple(forecast.assumptions),
    )
    computed = run_scenario(baseline, shocks)
    run = ScenarioRun(
        tenant_id=tenant_id,
        forecast_id=forecast.id,
        name=name,
        shocks=[
            {"day": item.day.isoformat(), "amount_minor": item.amount_minor, "label": item.label}
            for item in shocks
        ],
        minimum_balance_minor=computed.minimum_balance_minor,
        first_shortfall_date=computed.first_shortfall_date,
        ending_delta_minor=computed.ending_delta_minor,
        engine_version=ENGINE_VERSION,
    )
    session.add(run)
    await session.flush()
    points = [
        ScenarioPoint(
            scenario_run_id=run.id,
            day=point.day,
            balance_minor=point.balance_minor,
            recurring_flow_minor=point.recurring_flow_minor,
            estimated_variable_spend_minor=point.estimated_variable_spend_minor,
        )
        for point in computed.points
    ]
    session.add_all(points)
    await session.commit()
    await session.refresh(run)
    return run, points


async def get_scenario(
    session: AsyncSession, *, tenant_id: UUID, scenario_id: UUID
) -> tuple[ScenarioRun, list[ScenarioPoint]] | None:
    run = await session.scalar(
        select(ScenarioRun).where(ScenarioRun.id == scenario_id, ScenarioRun.tenant_id == tenant_id)
    )
    if run is None:
        return None
    points = list(
        await session.scalars(
            select(ScenarioPoint)
            .where(ScenarioPoint.scenario_run_id == run.id)
            .order_by(ScenarioPoint.day)
        )
    )
    return run, points
