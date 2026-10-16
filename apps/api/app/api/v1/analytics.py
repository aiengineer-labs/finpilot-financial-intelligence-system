from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import TenantContext, tenant_context
from app.database.session import get_session
from app.engines.financial import ScenarioShock
from app.schemas.analytics import (
    ForecastCreate,
    ForecastResponse,
    PointResponse,
    RecurringPatternResponse,
    ScenarioCreate,
    ScenarioResponse,
    SnapshotCreate,
    SnapshotResponse,
)
from app.services.analytics import (
    create_forecast,
    create_scenario,
    create_snapshot,
    get_forecast,
    get_scenario,
    get_snapshot,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _snapshot_response(snapshot, patterns) -> SnapshotResponse:  # type: ignore[no-untyped-def]
    return SnapshotResponse(
        id=snapshot.id,
        account_id=snapshot.account_id,
        as_of=snapshot.as_of,
        currency=snapshot.currency,
        opening_balance_minor=snapshot.opening_balance_minor,
        source_transaction_count=snapshot.source_transaction_count,
        source_transaction_ids=snapshot.source_transaction_ids,
        input_sha256=snapshot.input_sha256,
        engine_version=snapshot.engine_version,
        anomaly_results=snapshot.anomaly_results,
        recurring_patterns=[RecurringPatternResponse.model_validate(item) for item in patterns],
        created_at=snapshot.created_at,
    )


def _forecast_response(forecast, points) -> ForecastResponse:  # type: ignore[no-untyped-def]
    return ForecastResponse(
        id=forecast.id,
        snapshot_id=forecast.snapshot_id,
        horizon_days=forecast.horizon_days,
        opening_balance_minor=forecast.opening_balance_minor,
        minimum_balance_minor=forecast.minimum_balance_minor,
        assumptions=forecast.assumptions,
        engine_version=forecast.engine_version,
        points=[PointResponse.model_validate(item) for item in points],
        created_at=forecast.created_at,
    )


def _scenario_response(run, points) -> ScenarioResponse:  # type: ignore[no-untyped-def]
    return ScenarioResponse(
        id=run.id,
        forecast_id=run.forecast_id,
        name=run.name,
        shocks=run.shocks,
        minimum_balance_minor=run.minimum_balance_minor,
        first_shortfall_date=run.first_shortfall_date,
        ending_delta_minor=run.ending_delta_minor,
        engine_version=run.engine_version,
        points=[PointResponse.model_validate(item) for item in points],
        created_at=run.created_at,
    )


@router.post("/snapshots", response_model=SnapshotResponse, status_code=201)
async def post_snapshot(
    body: SnapshotCreate,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SnapshotResponse:
    try:
        snapshot, patterns = await create_snapshot(
            session,
            tenant_id=context.tenant_id,
            account_id=body.account_id,
            requested_as_of=body.as_of,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _snapshot_response(snapshot, patterns)


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotResponse)
async def read_snapshot(
    snapshot_id: UUID,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SnapshotResponse:
    loaded = await get_snapshot(session, tenant_id=context.tenant_id, snapshot_id=snapshot_id)
    if loaded is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="snapshot not found")
    return _snapshot_response(*loaded)


@router.post("/forecasts", response_model=ForecastResponse, status_code=201)
async def post_forecast(
    body: ForecastCreate,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ForecastResponse:
    try:
        loaded = await create_forecast(
            session,
            tenant_id=context.tenant_id,
            snapshot_id=body.snapshot_id,
            horizon_days=body.horizon_days,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _forecast_response(*loaded)


@router.get("/forecasts/{forecast_id}", response_model=ForecastResponse)
async def read_forecast(
    forecast_id: UUID,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ForecastResponse:
    loaded = await get_forecast(session, tenant_id=context.tenant_id, forecast_id=forecast_id)
    if loaded is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="forecast not found")
    return _forecast_response(*loaded)


@router.post("/scenarios", response_model=ScenarioResponse, status_code=201)
async def post_scenario(
    body: ScenarioCreate,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ScenarioResponse:
    try:
        loaded = await create_scenario(
            session,
            tenant_id=context.tenant_id,
            forecast_id=body.forecast_id,
            name=body.name,
            shocks=[ScenarioShock(item.day, item.amount_minor, item.label) for item in body.shocks],
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _scenario_response(*loaded)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def read_scenario(
    scenario_id: UUID,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ScenarioResponse:
    loaded = await get_scenario(session, tenant_id=context.tenant_id, scenario_id=scenario_id)
    if loaded is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scenario not found")
    return _scenario_response(*loaded)
