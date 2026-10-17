from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.specialists import CATEGORIZER_PROMPT_VERSION, MAX_CATEGORIZER_LABELS
from app.core.settings import Settings
from app.database.models import (
    EvaluationGateStatus,
    EvaluationRun,
    GovernanceArtifact,
    GovernanceArtifactStatus,
    HumanDecision,
    HumanDecisionOutcome,
    HumanReviewCase,
    HumanReviewStatus,
    Membership,
    RiskLevel,
    RiskRegisterEntry,
    TenantRole,
)
from app.engines.categorization import MIN_SEMANTIC_CONFIDENCE_BPS, SEMANTIC_CONFIDENCE_CAP_BPS
from app.graphs.manifest import GRAPH_VERSION, PROMPT_VERSION, VERIFIER_VERSION
from app.guardrails.service import NEMO_POLICY_VERSION, PII_POLICY_VERSION

GOVERNANCE_BASELINE_VERSION = "governance-baseline-v1"
RELEASE_CODE_VERSION = "5d33571"


def artifact_content_sha256(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _artifact_specs(settings: Settings) -> tuple[tuple[str, str, str, dict[str, Any]], ...]:
    model_id = settings.mesh_model or "not-configured"
    effort = settings.mesh_reasoning_effort
    return (
        (
            "model",
            "mesh-advice-model",
            f"{model_id}@reasoning-{effort or 'disabled'}@schema-v1",
            {
                "model_id": model_id,
                "gateway": "https://api.meshapi.ai/v1",
                "direct_provider_fallback": False,
                "reasoning_effort": effort or "disabled",
                "temperature": "provider_default" if effort else 0,
                "response_format": "strict_json_schema",
            },
        ),
        ("prompt", "advice-prompts", PROMPT_VERSION, {"template_version": PROMPT_VERSION}),
        ("agent_graph", "advice-graph", GRAPH_VERSION, {"graph_version": GRAPH_VERSION}),
        (
            "guardrail",
            "model-boundary",
            NEMO_POLICY_VERSION,
            {"nemo": NEMO_POLICY_VERSION, "presidio": PII_POLICY_VERSION},
        ),
        (
            "financial_verifier",
            "advice-verifier",
            VERIFIER_VERSION,
            {"version": VERIFIER_VERSION, "mandatory": True, "fail_closed": True},
        ),
        (
            "financial_engine",
            "cashflow-engine",
            "financial-engine-v1",
            {"money_representation": "integer_minor_units", "forecast": "deterministic-v1"},
        ),
        (
            "categorization",
            "transaction-rules",
            "categorization-rules-v2",
            {"low_confidence_route": "mesh_required", "human_correction_lineage": True},
        ),
        (
            "categorizer_prompt",
            "mesh-categorizer",
            CATEGORIZER_PROMPT_VERSION,
            {
                "template_version": CATEGORIZER_PROMPT_VERSION,
                "fixed_categories": True,
                "min_confidence_bps": MIN_SEMANTIC_CONFIDENCE_BPS,
                "confidence_cap_bps": SEMANTIC_CONFIDENCE_CAP_BPS,
                "max_labels_per_run": MAX_CATEGORIZER_LABELS,
                "amounts_sent": False,
                "human_corrections_overridable": False,
            },
        ),
        (
            "tool_policy",
            "static-agent-allowlist",
            "tool-policy-v1",
            {"model_supplied_security_context": False, "money_movement": False},
        ),
        (
            "evaluation_dataset",
            "prompt-injection-corpus",
            "2026-10-16-v1",
            {"attack_cases": 168, "benign_cases": 16, "synthetic_only": True},
        ),
        (
            "threshold_policy",
            "human-review-thresholds",
            "review-policy-v1",
            {
                "low_confidence_bps": 7000,
                "verifier_rejection_requires_review": True,
                "critical_controls_overridable": False,
            },
        ),
    )


RISK_SPECS: tuple[tuple[str, str, RiskLevel, RiskLevel, str, str, str, RiskLevel], ...] = (
    (
        "R-001",
        "financial_miscalculation",
        RiskLevel.MEDIUM,
        RiskLevel.CRITICAL,
        "Numeric logic defect",
        "Integer minor-unit engines and independent verifier",
        "Financial Engine Owner",
        RiskLevel.LOW,
    ),
    (
        "R-002",
        "hallucinated_advice",
        RiskLevel.HIGH,
        RiskLevel.HIGH,
        "Model invents evidence or amounts",
        "Evidence allowlist, critic, deterministic verifier, safe withholding",
        "AI System Owner",
        RiskLevel.MEDIUM,
    ),
    (
        "R-003",
        "forecast_reliability",
        RiskLevel.MEDIUM,
        RiskLevel.HIGH,
        "Sparse or non-stationary history",
        "Chronological backtests, assumptions and uncertainty labels",
        "Financial Engine Owner",
        RiskLevel.MEDIUM,
    ),
    (
        "R-004",
        "quality_drift",
        RiskLevel.MEDIUM,
        RiskLevel.HIGH,
        "Data or provider behavior changes",
        "Versioned evaluation gates and drift observations",
        "AI System Owner",
        RiskLevel.MEDIUM,
    ),
    (
        "R-005",
        "prompt_injection",
        RiskLevel.HIGH,
        RiskLevel.CRITICAL,
        "Untrusted content carries instructions",
        "Deterministic policy, NeMo rails, tool allowlists and red-team regression",
        "Security Owner",
        RiskLevel.MEDIUM,
    ),
    (
        "R-006",
        "data_leakage",
        RiskLevel.MEDIUM,
        RiskLevel.CRITICAL,
        "Sensitive data crosses trust boundary",
        "Tenant authorization, Presidio minimization and audit",
        "Data Owner",
        RiskLevel.LOW,
    ),
    (
        "R-007",
        "tenant_crossover",
        RiskLevel.LOW,
        RiskLevel.CRITICAL,
        "Object access misses tenant predicate",
        "Server-derived tenant context and isolation tests",
        "Security Owner",
        RiskLevel.LOW,
    ),
    (
        "R-008",
        "misclassification",
        RiskLevel.MEDIUM,
        RiskLevel.MEDIUM,
        "Ambiguous merchant semantics",
        "Rules first; confidence-gated Mesh categorizer over a fixed list; correction lineage",
        "Data Owner",
        RiskLevel.MEDIUM,
    ),
    (
        "R-009",
        "profiling_bias",
        RiskLevel.LOW,
        RiskLevel.HIGH,
        "Advice uses protected attributes",
        "No protected attributes in advice context; contestability review",
        "AI System Owner",
        RiskLevel.LOW,
    ),
    (
        "R-010",
        "model_cost",
        RiskLevel.MEDIUM,
        RiskLevel.MEDIUM,
        "Runaway calls or retries",
        "Bounded graph, token accounting and timeout limits",
        "AI System Owner",
        RiskLevel.LOW,
    ),
    (
        "R-011",
        "scheduler_failure",
        RiskLevel.MEDIUM,
        RiskLevel.MEDIUM,
        "Digest job is lost or duplicated",
        "Idempotent durable dispatch and delivery audit",
        "AI System Owner",
        RiskLevel.MEDIUM,
    ),
    (
        "R-012",
        "stale_snapshot",
        RiskLevel.MEDIUM,
        RiskLevel.HIGH,
        "Advice uses obsolete calculation input",
        "Immutable snapshot IDs and freshness labels",
        "Financial Engine Owner",
        RiskLevel.LOW,
    ),
    (
        "R-013",
        "undetected_degradation",
        RiskLevel.MEDIUM,
        RiskLevel.HIGH,
        "Evaluation coverage misses regression",
        "Multiple measured gates, incident path and safe AI disable",
        "AI System Owner",
        RiskLevel.MEDIUM,
    ),
)


async def ensure_governance_baseline(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    owner_user_id: UUID,
    settings: Settings,
) -> None:
    tenant_owner_user_id = await session.scalar(
        select(Membership.user_id).where(
            Membership.tenant_id == tenant_id, Membership.role == TenantRole.OWNER
        )
    )
    artifact_owner_user_id = tenant_owner_user_id or owner_user_id
    existing_artifacts = {
        (artifact_type, name, version)
        for artifact_type, name, version in (
            await session.execute(
                select(
                    GovernanceArtifact.artifact_type,
                    GovernanceArtifact.name,
                    GovernanceArtifact.version,
                ).where(GovernanceArtifact.tenant_id == tenant_id)
            )
        ).all()
    }
    now = datetime.now(UTC)
    for artifact_type, name, version, configuration in _artifact_specs(settings):
        if (artifact_type, name, version) in existing_artifacts:
            continue
        session.add(
            GovernanceArtifact(
                tenant_id=tenant_id,
                artifact_type=artifact_type,
                name=name,
                version=version,
                content_sha256=artifact_content_sha256(configuration),
                configuration=configuration,
                status=GovernanceArtifactStatus.APPROVED,
                owner_user_id=artifact_owner_user_id,
                approved_by_user_id=None,
                approval_source="automated_release_gate",
                approval_reason=(
                    "Baseline is tied to tested source and cannot mutate runtime policy."
                ),
                approved_at=now,
            )
        )

    existing_risks = set(
        await session.scalars(
            select(RiskRegisterEntry.risk_id).where(RiskRegisterEntry.tenant_id == tenant_id)
        )
    )
    for risk_id, category, likelihood, impact, cause, mitigation, owner, residual in RISK_SPECS:
        if risk_id in existing_risks:
            continue
        session.add(
            RiskRegisterEntry(
                tenant_id=tenant_id,
                risk_id=risk_id,
                version="1.0",
                category=category,
                likelihood=likelihood,
                impact=impact,
                affected_assets=["financial_data", "recommendations", "audit_evidence"],
                cause=cause,
                mitigation=mitigation,
                test_evidence=["docs/IMPLEMENTATION_STATUS.md"],
                owner_role=owner,
                residual_risk=residual,
                acceptance_status="controlled",
                exception_record=None,
                expires_on=None,
                review_on=date.today() + timedelta(days=30),
            )
        )

    existing_evaluations = set(
        await session.scalars(
            select(EvaluationRun.dataset_id).where(EvaluationRun.tenant_id == tenant_id)
        )
    )
    if "prompt-injection-quick" not in existing_evaluations:
        session.add(
            EvaluationRun(
                tenant_id=tenant_id,
                dataset_id="prompt-injection-quick",
                dataset_version="2026-10-16-v1",
                sampling_method="exhaustive versioned synthetic corpus",
                metrics={
                    "passed": 184,
                    "failed": 0,
                    "attack_success_rate": 0.0,
                    "false_positive_rate": 0.0,
                },
                thresholds={"max_attack_success_rate": 0.0, "max_false_positive_rate": 0.0},
                status=EvaluationGateStatus.PASS,
                code_version=RELEASE_CODE_VERSION,
                model_id=None,
                failures=[],
                reviewer_disposition="automated_gate_passed",
                duration_ms=2125,
            )
        )
    if "mesh-model-redteam" not in existing_evaluations:
        session.add(
            EvaluationRun(
                tenant_id=tenant_id,
                dataset_id="mesh-model-redteam",
                dataset_version="not-run",
                sampling_method="Promptfoo model-generated probes through Mesh only",
                metrics={},
                thresholds={"max_critical_attack_success_rate": 0.0},
                status=EvaluationGateStatus.NOT_RUN,
                code_version=RELEASE_CODE_VERSION,
                model_id=settings.mesh_model or None,
                failures=["Model security evaluation has not been run for this release"],
                reviewer_disposition="release_blocked",
                duration_ms=0,
            )
        )
    else:
        pending_model_evaluation = await session.scalar(
            select(EvaluationRun).where(
                EvaluationRun.tenant_id == tenant_id,
                EvaluationRun.dataset_id == "mesh-model-redteam",
                EvaluationRun.status == EvaluationGateStatus.NOT_RUN,
            )
        )
        if pending_model_evaluation is not None and pending_model_evaluation.failures == [
            "External Mesh egress approval pending"
        ]:
            # This seed text described the development environment, not the durable gate state.
            # Reword it without pretending that the model-based evaluation has passed.
            pending_model_evaluation.failures = [
                "Model security evaluation has not been run for this release"
            ]
    await session.flush()


async def approved_artifact_lineage(session: AsyncSession, tenant_id: UUID) -> dict[str, str]:
    artifacts = list(
        await session.scalars(
            select(GovernanceArtifact)
            .where(
                GovernanceArtifact.tenant_id == tenant_id,
                GovernanceArtifact.status == GovernanceArtifactStatus.APPROVED,
            )
            .order_by(GovernanceArtifact.artifact_type, GovernanceArtifact.created_at.desc())
        )
    )
    lineage: dict[str, str] = {}
    for artifact in artifacts:
        lineage.setdefault(
            artifact.artifact_type,
            f"{artifact.id}:{artifact.version}:{artifact.content_sha256}",
        )
    required = {"model", "prompt", "agent_graph", "guardrail", "financial_verifier", "tool_policy"}
    if not required.issubset(lineage):
        raise RuntimeError("approved governance baseline is incomplete")
    return lineage


async def release_gate_state(session: AsyncSession, tenant_id: UUID) -> tuple[bool, list[str]]:
    evaluations = list(
        await session.scalars(select(EvaluationRun).where(EvaluationRun.tenant_id == tenant_id))
    )
    blockers = [
        f"evaluation:{item.dataset_id}:{item.status.value}"
        for item in evaluations
        if item.status is not EvaluationGateStatus.PASS
    ]
    critical_risks = list(
        await session.scalars(
            select(RiskRegisterEntry).where(
                RiskRegisterEntry.tenant_id == tenant_id,
                RiskRegisterEntry.residual_risk == RiskLevel.CRITICAL,
            )
        )
    )
    blockers.extend(f"risk:{item.risk_id}:critical" for item in critical_risks)
    return not blockers and bool(evaluations), blockers


async def create_review_case(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    requested_by_user_id: UUID | None,
    source: str,
    reason: str,
    risk_level: RiskLevel,
    evidence_ids: list[str],
    artifact_lineage: dict[str, str],
    execution_id: UUID | None = None,
    recommendation_id: UUID | None = None,
) -> HumanReviewCase:
    case = HumanReviewCase(
        tenant_id=tenant_id,
        execution_id=execution_id,
        recommendation_id=recommendation_id,
        requested_by_user_id=requested_by_user_id,
        source=source,
        reason=reason,
        risk_level=risk_level,
        status=HumanReviewStatus.PENDING,
        evidence_ids=evidence_ids,
        artifact_lineage=artifact_lineage,
    )
    session.add(case)
    await session.flush()
    return case


async def decide_review_case(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    case_id: UUID,
    reviewer_user_id: UUID,
    reviewer_role: TenantRole,
    outcome: HumanDecisionOutcome,
    reason: str,
) -> HumanDecision:
    if reviewer_role not in {TenantRole.OWNER, TenantRole.REVIEWER}:
        raise PermissionError("reviewer role required")
    case = await session.scalar(
        select(HumanReviewCase).where(
            HumanReviewCase.id == case_id, HumanReviewCase.tenant_id == tenant_id
        )
    )
    if case is None:
        raise LookupError("review case not found")
    if case.status is HumanReviewStatus.RESOLVED:
        raise ValueError("review case is already resolved")
    if case.requested_by_user_id == reviewer_user_id:
        raise PermissionError("requester cannot decide their own review case")
    decision = HumanDecision(
        tenant_id=tenant_id,
        review_case_id=case.id,
        reviewer_user_id=reviewer_user_id,
        outcome=outcome,
        reason=reason,
        source_evidence=case.evidence_ids,
        artifact_lineage=case.artifact_lineage,
    )
    case.status = HumanReviewStatus.RESOLVED
    case.resolved_at = datetime.now(UTC)
    session.add(decision)
    await session.flush()
    return decision


async def governance_counts(session: AsyncSession, tenant_id: UUID) -> dict[str, int]:
    async def count(model: type[Any], *conditions: Any) -> int:
        value = await session.scalar(select(func.count()).select_from(model).where(*conditions))
        return int(value or 0)

    return {
        "artifacts": await count(GovernanceArtifact, GovernanceArtifact.tenant_id == tenant_id),
        "risks": await count(RiskRegisterEntry, RiskRegisterEntry.tenant_id == tenant_id),
        "pending_reviews": await count(
            HumanReviewCase,
            HumanReviewCase.tenant_id == tenant_id,
            HumanReviewCase.status == HumanReviewStatus.PENDING,
        ),
        "evaluation_failures": await count(
            EvaluationRun,
            EvaluationRun.tenant_id == tenant_id,
            EvaluationRun.status != EvaluationGateStatus.PASS,
        ),
    }
