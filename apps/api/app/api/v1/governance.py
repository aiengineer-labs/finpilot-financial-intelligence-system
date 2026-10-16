from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import TenantContext, tenant_context
from app.core.settings import Settings, get_settings
from app.database.models import (
    AgentExecution,
    EvaluationRun,
    GovernanceArtifact,
    GovernanceArtifactStatus,
    HumanReviewCase,
    Recommendation,
    RiskLevel,
    RiskRegisterEntry,
    TenantRole,
    VerificationStatus,
)
from app.database.session import get_session
from app.schemas.governance import (
    ArtifactApprovalRequest,
    EvaluationRunResponse,
    GovernanceArtifactCreate,
    GovernanceArtifactResponse,
    GovernanceSummaryResponse,
    HumanDecisionCreate,
    HumanDecisionResponse,
    HumanReviewCreate,
    HumanReviewResponse,
    RiskResponse,
)
from app.services.governance import (
    GOVERNANCE_BASELINE_VERSION,
    approved_artifact_lineage,
    artifact_content_sha256,
    create_review_case,
    decide_review_case,
    ensure_governance_baseline,
    governance_counts,
    release_gate_state,
)

router = APIRouter(prefix="/governance", tags=["governance"])


async def _ensure(session: AsyncSession, context: TenantContext, settings: Settings) -> None:
    await ensure_governance_baseline(
        session,
        tenant_id=context.tenant_id,
        owner_user_id=context.user.id,
        settings=settings,
    )
    await session.commit()


@router.get("/summary", response_model=GovernanceSummaryResponse)
async def summary(
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GovernanceSummaryResponse:
    await _ensure(session, context, settings)
    counts = await governance_counts(session, context.tenant_id)
    rejected = await session.scalar(
        select(func.count())
        .select_from(Recommendation)
        .where(
            Recommendation.tenant_id == context.tenant_id,
            Recommendation.verification_status != VerificationStatus.ACCEPT,
        )
    )
    release_ready, blockers = await release_gate_state(session, context.tenant_id)
    return GovernanceSummaryResponse(
        **counts,
        rejected_recommendations=int(rejected or 0),
        release_ready=release_ready,
        release_blockers=blockers,
        drift_alerts=[],
        baseline_version=GOVERNANCE_BASELINE_VERSION,
    )


@router.get("/artifacts", response_model=list[GovernanceArtifactResponse])
async def list_artifacts(
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[GovernanceArtifact]:
    await _ensure(session, context, settings)
    return list(
        await session.scalars(
            select(GovernanceArtifact)
            .where(GovernanceArtifact.tenant_id == context.tenant_id)
            .order_by(GovernanceArtifact.artifact_type, GovernanceArtifact.created_at.desc())
        )
    )


@router.post(
    "/artifacts", response_model=GovernanceArtifactResponse, status_code=status.HTTP_201_CREATED
)
async def propose_artifact(
    body: GovernanceArtifactCreate,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GovernanceArtifact:
    await _ensure(session, context, settings)
    if context.role is not TenantRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner role required")
    artifact = GovernanceArtifact(
        tenant_id=context.tenant_id,
        artifact_type=body.artifact_type,
        name=body.name,
        version=body.version,
        content_sha256=artifact_content_sha256(body.configuration),
        configuration=body.configuration,
        status=GovernanceArtifactStatus.DRAFT,
        owner_user_id=context.user.id,
        approved_by_user_id=None,
        approval_source="human_review",
        approval_reason=None,
        approved_at=None,
        rollback_artifact_id=body.rollback_artifact_id,
    )
    session.add(artifact)
    await session.commit()
    await session.refresh(artifact)
    return artifact


@router.post("/artifacts/{artifact_id}/approve", response_model=GovernanceArtifactResponse)
async def approve_artifact(
    artifact_id: UUID,
    body: ArtifactApprovalRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GovernanceArtifact:
    await _ensure(session, context, settings)
    if context.role not in {TenantRole.OWNER, TenantRole.REVIEWER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="reviewer role required")
    artifact = await session.scalar(
        select(GovernanceArtifact).where(
            GovernanceArtifact.id == artifact_id,
            GovernanceArtifact.tenant_id == context.tenant_id,
        )
    )
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")
    if artifact.status is not GovernanceArtifactStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="artifact is not a draft")
    if artifact.owner_user_id == context.user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="artifact owner cannot approve their own change",
        )
    ready, blockers = await release_gate_state(session, context.tenant_id)
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "release evaluation gates are not satisfied", "blockers": blockers},
        )
    artifact.status = GovernanceArtifactStatus.APPROVED
    artifact.approved_by_user_id = context.user.id
    artifact.approval_reason = body.reason
    artifact.approval_source = "independent_human_review"
    artifact.approved_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(artifact)
    return artifact


@router.get("/risks", response_model=list[RiskResponse])
async def list_risks(
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[RiskRegisterEntry]:
    await _ensure(session, context, settings)
    return list(
        await session.scalars(
            select(RiskRegisterEntry)
            .where(RiskRegisterEntry.tenant_id == context.tenant_id)
            .order_by(RiskRegisterEntry.risk_id)
        )
    )


@router.get("/evaluations", response_model=list[EvaluationRunResponse])
async def list_evaluations(
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[EvaluationRun]:
    await _ensure(session, context, settings)
    return list(
        await session.scalars(
            select(EvaluationRun)
            .where(EvaluationRun.tenant_id == context.tenant_id)
            .order_by(EvaluationRun.created_at.desc())
        )
    )


@router.get("/reviews", response_model=list[HumanReviewResponse])
async def list_reviews(
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[HumanReviewCase]:
    return list(
        await session.scalars(
            select(HumanReviewCase)
            .where(HumanReviewCase.tenant_id == context.tenant_id)
            .order_by(HumanReviewCase.created_at.desc())
        )
    )


@router.post("/reviews", response_model=HumanReviewResponse, status_code=status.HTTP_201_CREATED)
async def request_review(
    body: HumanReviewCreate,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HumanReviewCase:
    await _ensure(session, context, settings)
    execution_id = body.execution_id
    recommendation: Recommendation | None = None
    if body.recommendation_id is not None:
        recommendation = await session.scalar(
            select(Recommendation).where(
                Recommendation.id == body.recommendation_id,
                Recommendation.tenant_id == context.tenant_id,
            )
        )
        if recommendation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="recommendation not found",
            )
        if execution_id is not None and recommendation.execution_id != execution_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="recommendation does not belong to the supplied execution",
            )
        execution_id = recommendation.execution_id

    if execution_id is not None:
        execution = await session.scalar(
            select(AgentExecution).where(
                AgentExecution.id == execution_id,
                AgentExecution.tenant_id == context.tenant_id,
            )
        )
        if execution is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="execution not found")
        lineage = (
            recommendation.artifact_lineage
            if recommendation is not None
            else execution.artifact_lineage
        )
    else:
        lineage = await approved_artifact_lineage(session, context.tenant_id)
    review = await create_review_case(
        session,
        tenant_id=context.tenant_id,
        requested_by_user_id=context.user.id,
        source="user_contest",
        reason=body.reason,
        risk_level=body.risk_level,
        evidence_ids=body.evidence_ids,
        artifact_lineage=lineage,
        execution_id=execution_id,
        recommendation_id=body.recommendation_id,
    )
    await session.commit()
    await session.refresh(review)
    return review


@router.post(
    "/demo-review", response_model=HumanReviewResponse, status_code=status.HTTP_201_CREATED
)
async def create_demo_review(
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HumanReviewCase:
    if context.role not in {TenantRole.OWNER, TenantRole.REVIEWER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="reviewer role required")
    await _ensure(session, context, settings)
    review = await create_review_case(
        session,
        tenant_id=context.tenant_id,
        requested_by_user_id=None,
        source="synthetic_demo",
        reason=(
            "Synthetic recommendation claimed a guaranteed return and was automatically withheld."
        ),
        risk_level=RiskLevel.HIGH,
        evidence_ids=["synthetic:verifier-rejection"],
        artifact_lineage=await approved_artifact_lineage(session, context.tenant_id),
    )
    await session.commit()
    await session.refresh(review)
    return review


@router.post("/reviews/{case_id}/decisions", response_model=HumanDecisionResponse)
async def decide_review(
    case_id: UUID,
    body: HumanDecisionCreate,
    context: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HumanDecisionResponse:
    try:
        decision = await decide_review_case(
            session,
            tenant_id=context.tenant_id,
            case_id=case_id,
            reviewer_user_id=context.user.id,
            reviewer_role=context.role,
            outcome=body.outcome,
            reason=body.reason,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(decision)
    return HumanDecisionResponse.model_validate(decision)
