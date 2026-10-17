from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.specialists import AdvisorOutput
from app.core.settings import get_settings
from app.database.models import (
    AgentEvent,
    AgentExecution,
    AgentRunStatus,
    CalculationSnapshot,
    FinancialVerification,
    Recommendation,
    RiskLevel,
    ScenarioRun,
    StoredForecast,
    StoredForecastPoint,
    VerificationStatus,
)
from app.graphs.advice import AdviceWorkflow
from app.graphs.manifest import GRAPH_VERSION, PROMPT_VERSION, VERIFIER_VERSION
from app.guardrails.service import GuardrailViolation, get_model_guardrails
from app.integrations.mesh import MeshClient
from app.security.input_policy import InputDecision, assess_untrusted_text
from app.services.governance import (
    approved_artifact_lineage,
    create_review_case,
    ensure_governance_baseline,
)


async def _context(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    forecast_id: UUID,
    scenario_id: UUID | None,
) -> tuple[StoredForecast, CalculationSnapshot, ScenarioRun | None, dict[str, Any]]:
    forecast = await session.scalar(
        select(StoredForecast).where(
            StoredForecast.id == forecast_id, StoredForecast.tenant_id == tenant_id
        )
    )
    if forecast is None:
        raise LookupError("forecast not found")
    snapshot = await session.scalar(
        select(CalculationSnapshot).where(
            CalculationSnapshot.id == forecast.snapshot_id,
            CalculationSnapshot.tenant_id == tenant_id,
        )
    )
    if snapshot is None:
        raise LookupError("snapshot not found")
    points = list(
        await session.scalars(
            select(StoredForecastPoint)
            .where(StoredForecastPoint.forecast_id == forecast.id)
            .order_by(StoredForecastPoint.day)
        )
    )
    scenario: ScenarioRun | None = None
    if scenario_id is not None:
        scenario = await session.scalar(
            select(ScenarioRun).where(
                ScenarioRun.id == scenario_id,
                ScenarioRun.tenant_id == tenant_id,
                ScenarioRun.forecast_id == forecast.id,
            )
        )
        if scenario is None:
            raise LookupError("scenario not found")

    evidence_ids = [str(snapshot.id), str(forecast.id)]
    allowed_amounts = {
        snapshot.opening_balance_minor,
        forecast.opening_balance_minor,
        forecast.minimum_balance_minor,
        points[-1].balance_minor if points else forecast.opening_balance_minor,
    }
    for anomaly in snapshot.anomaly_results:
        transaction_id = anomaly.get("transaction_id")
        if isinstance(transaction_id, str):
            evidence_ids.append(transaction_id)
        for key in ("observed_amount_minor", "baseline_median_minor"):
            value = anomaly.get(key)
            if isinstance(value, int):
                allowed_amounts.add(value)
    scenario_summary: dict[str, Any] | None = None
    if scenario is not None:
        evidence_ids.append(str(scenario.id))
        allowed_amounts.update(
            {
                scenario.minimum_balance_minor,
                scenario.ending_delta_minor,
                abs(scenario.ending_delta_minor),
            }
        )
        for shock in scenario.shocks:
            value = shock.get("amount_minor")
            if isinstance(value, int):
                allowed_amounts.update({value, abs(value)})
        scenario_summary = {
            "id": str(scenario.id),
            "name": scenario.name,
            "minimum_balance_minor": scenario.minimum_balance_minor,
            "first_shortfall_date": (
                scenario.first_shortfall_date.isoformat() if scenario.first_shortfall_date else None
            ),
            "ending_delta_minor": scenario.ending_delta_minor,
            "shocks": scenario.shocks,
        }
    context: dict[str, Any] = {
        "currency": snapshot.currency,
        "snapshot": {
            "id": str(snapshot.id),
            "as_of": snapshot.as_of.isoformat(),
            "opening_balance_minor": snapshot.opening_balance_minor,
            "source_transaction_count": snapshot.source_transaction_count,
            "anomalies": snapshot.anomaly_results,
            "engine_version": snapshot.engine_version,
        },
        "forecast": {
            "id": str(forecast.id),
            "horizon_days": forecast.horizon_days,
            "minimum_balance_minor": forecast.minimum_balance_minor,
            "ending_balance_minor": (
                points[-1].balance_minor if points else forecast.opening_balance_minor
            ),
            "assumptions": forecast.assumptions,
            "engine_version": forecast.engine_version,
        },
        "scenario": scenario_summary,
        "scenario_id": str(scenario.id) if scenario else None,
        "evidence_ids": evidence_ids,
        "allowed_amount_minor": sorted(allowed_amounts),
    }
    return forecast, snapshot, scenario, context


async def execute_advice(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    forecast_id: UUID,
    scenario_id: UUID | None,
    question: str,
    mesh: MeshClient | None = None,
) -> AgentExecution:
    assessment = assess_untrusted_text(question)
    if assessment.decision is InputDecision.BLOCK:
        raise ValueError("question was blocked by the prompt-injection policy")
    forecast, snapshot, scenario, context = await _context(
        session, tenant_id=tenant_id, forecast_id=forecast_id, scenario_id=scenario_id
    )
    settings = get_settings()
    await ensure_governance_baseline(
        session, tenant_id=tenant_id, owner_user_id=user_id, settings=settings
    )
    artifact_lineage = await approved_artifact_lineage(session, tenant_id)
    guardrails = get_model_guardrails()
    try:
        prepared = await guardrails.prepare_input(question, context)
    except GuardrailViolation as exc:
        raise ValueError("question was blocked by programmable guardrails") from exc
    execution = AgentExecution(
        tenant_id=tenant_id,
        requested_by_user_id=user_id,
        snapshot_id=snapshot.id,
        forecast_id=forecast.id,
        scenario_run_id=scenario.id if scenario else None,
        question=question,
        intent="pending",
        status=AgentRunStatus.RUNNING,
        verification_status=VerificationStatus.INSUFFICIENT_DATA,
        final_response="",
        graph_version=GRAPH_VERSION,
        prompt_version=PROMPT_VERSION,
        model_id=settings.mesh_model,
        revision_attempts=0,
        total_latency_ms=0,
        total_input_tokens=0,
        total_output_tokens=0,
        artifact_lineage=artifact_lineage,
    )
    session.add(execution)
    await session.commit()
    await session.refresh(execution)
    try:
        state = await AdviceWorkflow(mesh or MeshClient(settings, output_guard=guardrails)).run(
            question=prepared.question,
            context=prepared.context,
            guardrail_events=prepared.events,
        )
    except Exception as exc:
        execution.status = AgentRunStatus.FAILED
        execution.final_response = "The agent run failed safely before producing advice."
        session.add(
            AgentEvent(
                tenant_id=tenant_id,
                execution_id=execution.id,
                sequence=1,
                node="runtime",
                event_type="failure",
                summary="Agent execution failed closed",
                details={"error_type": type(exc).__name__},
            )
        )
        await session.commit()
        raise RuntimeError("agent execution failed safely") from exc

    status = VerificationStatus(state["verification_status"])
    execution.intent = state["intent"]
    execution.verification_status = status
    execution.status = (
        AgentRunStatus.COMPLETED if status is VerificationStatus.ACCEPT else AgentRunStatus.REJECTED
    )
    execution.final_response = state["final_response"]
    execution.revision_attempts = state["revision_attempts"]
    for sequence, raw in enumerate(state["events"], start=1):
        event = raw
        latency = cast(int | None, event.get("latency_ms"))
        input_tokens = cast(int | None, event.get("input_tokens"))
        output_tokens = cast(int | None, event.get("output_tokens"))
        execution.total_latency_ms += latency or 0
        execution.total_input_tokens += input_tokens or 0
        execution.total_output_tokens += output_tokens or 0
        session.add(
            AgentEvent(
                tenant_id=tenant_id,
                execution_id=execution.id,
                sequence=sequence,
                node=str(event["node"]),
                event_type=str(event["event_type"]),
                summary=str(event["summary"]),
                details=cast(dict[str, Any], event.get("details", {})),
                model_id=cast(str | None, event.get("model_id")),
                latency_ms=latency,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        )
    draft = AdvisorOutput.model_validate(state["draft"])
    for rank, item in enumerate(draft.recommendations, start=1):
        recommendation = Recommendation(
            tenant_id=tenant_id,
            execution_id=execution.id,
            rank=rank,
            title=item.title,
            explanation=item.explanation,
            amount_minor=item.amount_minor,
            currency=item.currency,
            evidence_ids=item.evidence_ids,
            assumptions=item.assumptions,
            confidence_bps=item.confidence_bps,
            verification_status=status,
            artifact_lineage=artifact_lineage,
        )
        session.add(recommendation)
        await session.flush()
        session.add(
            FinancialVerification(
                tenant_id=tenant_id,
                execution_id=execution.id,
                recommendation_id=recommendation.id,
                status=status,
                reasons=state["verification_reasons"],
                checked_values={
                    "currency": snapshot.currency,
                    "amount_minor": item.amount_minor or 0,
                    "evidence_ids": item.evidence_ids,
                },
                verifier_version=VERIFIER_VERSION,
            )
        )
    if status is not VerificationStatus.ACCEPT:
        await create_review_case(
            session,
            tenant_id=tenant_id,
            requested_by_user_id=user_id,
            source="automatic_verifier_escalation",
            reason="Deterministic financial verification did not accept the final recommendation.",
            risk_level=RiskLevel.HIGH,
            evidence_ids=[str(snapshot.id), str(forecast.id)],
            artifact_lineage=artifact_lineage,
            execution_id=execution.id,
        )
    await session.commit()
    await session.refresh(execution)
    return execution


async def get_execution(
    session: AsyncSession, *, tenant_id: UUID, execution_id: UUID
) -> tuple[AgentExecution, list[AgentEvent], list[Recommendation]] | None:
    execution = await session.scalar(
        select(AgentExecution).where(
            AgentExecution.id == execution_id, AgentExecution.tenant_id == tenant_id
        )
    )
    if execution is None:
        return None
    events = list(
        await session.scalars(
            select(AgentEvent)
            .where(AgentEvent.execution_id == execution.id, AgentEvent.tenant_id == tenant_id)
            .order_by(AgentEvent.sequence)
        )
    )
    recommendations = list(
        await session.scalars(
            select(Recommendation)
            .where(
                Recommendation.execution_id == execution.id,
                Recommendation.tenant_id == tenant_id,
            )
            .order_by(Recommendation.rank)
        )
    )
    return execution, events, recommendations
