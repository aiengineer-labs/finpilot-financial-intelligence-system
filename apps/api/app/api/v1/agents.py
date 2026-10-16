from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import TenantContext, tenant_context
from app.database.session import get_session
from app.schemas.agents import (
    AgentEventResponse,
    AgentRunCreate,
    AgentRunResponse,
    RecommendationResponse,
)
from app.services.agent_runs import execute_advice, get_execution

router = APIRouter(prefix="/agent-runs", tags=["agents"])


def _response(execution, events, recommendations) -> AgentRunResponse:  # type: ignore[no-untyped-def]
    return AgentRunResponse(
        id=execution.id,
        snapshot_id=execution.snapshot_id,
        forecast_id=execution.forecast_id,
        scenario_run_id=execution.scenario_run_id,
        question=execution.question,
        intent=execution.intent,
        status=execution.status,
        verification_status=execution.verification_status,
        final_response=execution.final_response,
        graph_version=execution.graph_version,
        prompt_version=execution.prompt_version,
        model_id=execution.model_id,
        revision_attempts=execution.revision_attempts,
        total_latency_ms=execution.total_latency_ms,
        total_input_tokens=execution.total_input_tokens,
        total_output_tokens=execution.total_output_tokens,
        events=[AgentEventResponse.model_validate(item) for item in events],
        recommendations=[RecommendationResponse.model_validate(item) for item in recommendations],
        created_at=execution.created_at,
    )


@router.post("", response_model=AgentRunResponse, status_code=201)
async def post_agent_run(
    body: AgentRunCreate,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentRunResponse:
    try:
        execution = await execute_advice(
            session,
            tenant_id=context.tenant_id,
            user_id=context.user.id,
            forecast_id=body.forecast_id,
            scenario_id=body.scenario_id,
            question=body.question,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    loaded = await get_execution(
        session, tenant_id=context.tenant_id, execution_id=execution.id
    )
    if loaded is None:
        raise HTTPException(status_code=500, detail="agent execution was not persisted")
    return _response(*loaded)


@router.get("/{execution_id}", response_model=AgentRunResponse)
async def read_agent_run(
    execution_id: UUID,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentRunResponse:
    loaded = await get_execution(
        session, tenant_id=context.tenant_id, execution_id=execution_id
    )
    if loaded is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent run not found")
    return _response(*loaded)
