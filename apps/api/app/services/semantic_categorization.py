"""Confidence-gated Mesh categorization for rows the deterministic rules could not place.

Mesh only proposes a category from a fixed list. Code decides whether to apply it, never touches
amounts, kinds or balances, and leaves human corrections alone.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.specialists import (
    CATEGORIZER_PROMPT_VERSION,
    MAX_CATEGORIZER_LABELS,
    MERCHANT_UPI_MARKER,
    PERSONAL_UPI_MARKER,
    CategorizerAgent,
    CategorizerOutput,
)
from app.core.settings import Settings
from app.database.models import (
    AgentRunStatus,
    CategorizationDecision,
    CategorizationRun,
    ClassificationMethod,
    Transaction,
    TransactionKind,
)
from app.engines.categorization import (
    EXPENSE_FALLBACK,
    INCOME_FALLBACK,
    MIN_SEMANTIC_CONFIDENCE_BPS,
    SEMANTIC_CONFIDENCE_CAP_BPS,
    SEMANTIC_EXPENSE_CATEGORIES,
    SEMANTIC_INCOME_CATEGORIES,
)
from app.guardrails.service import GuardrailViolation, get_model_guardrails
from app.integrations.mesh import MeshClient, MeshProviderError, reported_billing, token_usage
from app.security.input_policy import InputDecision, assess_untrusted_text
from app.services.governance import approved_artifact_lineage, ensure_governance_baseline
from app.services.transaction_import import find_account

MAX_LABEL_CHARS = 96
# A UPI handle such as "q123456789@ybl" or "name@okaxis"; an email address is left to Presidio.
_UPI_HANDLE = re.compile(r"[A-Za-z0-9._-]+@[A-Za-z]*(?![A-Za-z.])")
# Merchant QR and business handles: PhonePe "q<digits>", Paytm, BharatPe and "...qr" handles.
_MERCHANT_HANDLE = re.compile(r"^(?:q\d|paytm|bharatpe|mab\.|pos|[a-z0-9._-]*qr)", re.IGNORECASE)
# Transaction IDs mix letters and digits ("ICI3a2b1c..."); short codes such as P2M are kept.
_MIXED_REFERENCE = re.compile(r"\b(?=[A-Za-z]*\d)(?=\d*[A-Za-z])[A-Za-z0-9]{6,}\b")
_REFERENCE_DIGITS = re.compile(r"\d{6,}")
_SEPARATORS = re.compile(r"(?:\s*[/|]\s*)+")
_SEMANTIC_KINDS = (TransactionKind.EXPENSE, TransactionKind.INCOME)
_FIXED_REQUEST = "Categorize the supplied statement labels."


class CategorizerUnavailableError(RuntimeError):
    """Mesh is not configured, so ambiguous rows keep their rule-assigned fallback."""


@dataclass(frozen=True)
class CategorizationResult:
    run: CategorizationRun | None
    rows_pending: int
    labels_withheld: int
    rows_remaining: int


@dataclass
class _Label:
    label_id: str
    direction: str
    text: str
    transaction_ids: list[UUID]


def _upi_marker(match: re.Match[str]) -> str:
    handle = match.group(0)
    return MERCHANT_UPI_MARKER if _MERCHANT_HANDLE.match(handle) else PERSONAL_UPI_MARKER


def _label_text(row: Transaction) -> str:
    """The payee words of a statement line, without handles, references or account numbers.

    Removing the per-row identifiers keeps private data out of the request and lets repeat
    payments to the same payee share one label.
    """

    merchant = row.merchant_raw.strip()
    description = row.description.strip()
    text = merchant
    if description and description.casefold() not in merchant.casefold():
        text = f"{merchant} - {description}" if merchant else description
    text = _UPI_HANDLE.sub(_upi_marker, text)
    text = _MIXED_REFERENCE.sub(" ", text)
    text = _REFERENCE_DIGITS.sub(" ", text)
    text = _SEPARATORS.sub(" / ", text)
    return " ".join(text.split()).strip(" /-")[:MAX_LABEL_CHARS]


def _pending_rows_query(tenant_id: UUID, account_id: UUID) -> Any:
    """Rows routed to Mesh that the current categorizer prompt has not answered yet.

    An answer from an older prompt version does not count, so a prompt with new categories
    gets to look again at rows its predecessor left unclear.
    """

    answered = exists().where(
        CategorizationDecision.transaction_id == Transaction.id,
        CategorizationDecision.run_id == CategorizationRun.id,
        CategorizationRun.prompt_version == CATEGORIZER_PROMPT_VERSION,
    )
    return select(Transaction).where(
        Transaction.tenant_id == tenant_id,
        Transaction.account_id == account_id,
        Transaction.classification_method == ClassificationMethod.MESH_REQUIRED,
        Transaction.kind.in_(_SEMANTIC_KINDS),
        ~answered,
    )


async def _pending_rows(
    session: AsyncSession, tenant_id: UUID, account_id: UUID
) -> list[Transaction]:
    query = _pending_rows_query(tenant_id, account_id).order_by(
        Transaction.transaction_date, Transaction.id
    )
    return list(await session.scalars(query))


def _group_labels(rows: list[Transaction]) -> tuple[list[_Label], int]:
    """Bound, screen and de-duplicate labels, most frequent first; count withheld rows."""

    grouped: dict[tuple[str, str], list[Transaction]] = defaultdict(list)
    withheld = 0
    for row in rows:
        text = _label_text(row)
        if not text or assess_untrusted_text(text).decision is InputDecision.BLOCK:
            withheld += 1
            continue
        direction = "credit" if row.kind is TransactionKind.INCOME else "debit"
        grouped[(direction, text.casefold())].append(row)
    ranked = sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
    labels = [
        _Label(
            label_id=f"L{index}",
            direction=direction,
            text=_label_text(members[0]),
            transaction_ids=[member.id for member in members],
        )
        for index, ((direction, _), members) in enumerate(ranked, start=1)
    ]
    return labels, withheld


def _sendable_rows(labels: list[_Label]) -> int:
    return sum(len(label.transaction_ids) for label in labels)


def _judge(label: _Label, category: str, confidence_bps: int) -> str:
    """Code, not the model, decides whether a proposed category is applied."""

    if label.direction == "credit":
        allowed, other = SEMANTIC_INCOME_CATEGORIES, SEMANTIC_EXPENSE_CATEGORIES
    else:
        allowed, other = SEMANTIC_EXPENSE_CATEGORIES, SEMANTIC_INCOME_CATEGORIES
    if category not in allowed:
        return "wrong_direction" if category in other else "unknown_category"
    if category in (EXPENSE_FALLBACK, INCOME_FALLBACK):
        return "still_unclear"
    if confidence_bps < MIN_SEMANTIC_CONFIDENCE_BPS:
        return "low_confidence"
    return "applied"


async def categorize_ambiguous_rows(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    account_id: UUID,
    settings: Settings,
    mesh: MeshClient | None = None,
) -> CategorizationResult:
    account = await find_account(session, tenant_id, account_id)
    if account is None:
        raise LookupError("account not found")
    rows = await _pending_rows(session, tenant_id, account_id)
    sendable, withheld = _group_labels(rows)
    if not sendable:
        return CategorizationResult(None, len(rows), withheld, 0)
    labels = sendable[:MAX_CATEGORIZER_LABELS]

    guardrails = get_model_guardrails()
    if mesh is None:
        try:
            mesh = MeshClient(settings, output_guard=guardrails)
        except RuntimeError as exc:
            raise CategorizerUnavailableError(
                "Mesh is not configured, so unclear rows keep their rule-based category"
            ) from exc
    prepared = await guardrails.prepare_input(
        _FIXED_REQUEST,
        {
            "labels": [
                {"label_id": label.label_id, "direction": label.direction, "text": label.text}
                for label in labels
            ]
        },
    )
    await ensure_governance_baseline(
        session, tenant_id=tenant_id, owner_user_id=user_id, settings=settings
    )
    run = CategorizationRun(
        tenant_id=tenant_id,
        account_id=account_id,
        requested_by_user_id=user_id,
        status=AgentRunStatus.RUNNING,
        prompt_version=CATEGORIZER_PROMPT_VERSION,
        model_id=settings.mesh_model,
        rows_pending=len(rows),
        labels_sent=len(labels),
        labels_withheld=withheld,
        rows_updated=0,
        latency_ms=0,
        input_tokens=0,
        output_tokens=0,
        details={"guardrails": [event["details"] for event in prepared.events]},
        artifact_lineage=await approved_artifact_lineage(session, tenant_id),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    try:
        result = await CategorizerAgent(mesh).run(
            cast(list[dict[str, str]], prepared.context["labels"])
        )
    except Exception as exc:
        details: dict[str, Any] = {**run.details, "error_type": type(exc).__name__}
        failure = "semantic categorization failed safely"
        if isinstance(exc, MeshProviderError):
            details["provider_status"] = exc.status_code
            failure = f"{failure}: {exc.reason}"
        elif isinstance(exc, GuardrailViolation):
            details["guardrail_rule"] = exc.rule or "unknown"
            failure = f"{failure}: the output guardrail blocked model text ({exc.rule})"
        run.status = AgentRunStatus.FAILED
        run.details = details
        await session.commit()
        raise RuntimeError(failure) from exc

    output = cast(CategorizerOutput, result.payload)
    by_id = {label.label_id: label for label in labels}
    answers: dict[str, tuple[str, int]] = {}
    unknown_ids = 0
    for answer in output.labels:
        if answer.label_id not in by_id:
            unknown_ids += 1
        else:
            answers.setdefault(answer.label_id, (answer.category, answer.confidence_bps))

    # Re-read the rows: a human correction made during the Mesh call must win.
    still_pending = {
        row.id: row
        for row in await session.scalars(
            select(Transaction)
            .where(
                Transaction.tenant_id == tenant_id,
                Transaction.id.in_([tid for label in labels for tid in label.transaction_ids]),
                Transaction.classification_method == ClassificationMethod.MESH_REQUIRED,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }
    outcomes: dict[str, int] = defaultdict(int)
    for label in labels:
        category, confidence = answers.get(label.label_id, ("", 0))
        reason = _judge(label, category, confidence) if category else "not_answered"
        for transaction_id in label.transaction_ids:
            row = still_pending.get(transaction_id)
            if row is None:
                continue
            outcomes[reason] += 1
            session.add(
                CategorizationDecision(
                    tenant_id=tenant_id,
                    run_id=run.id,
                    transaction_id=row.id,
                    label_id=label.label_id,
                    previous_category=row.category,
                    proposed_category=category or row.category,
                    confidence_bps=confidence,
                    applied=reason == "applied",
                    reason=reason,
                )
            )
            if reason == "applied":
                row.category = category
                row.classification_method = ClassificationMethod.MESH
                row.classification_confidence_bps = min(confidence, SEMANTIC_CONFIDENCE_CAP_BPS)

    input_tokens, output_tokens = token_usage(result.mesh)
    run.status = AgentRunStatus.COMPLETED
    run.rows_updated = outcomes.get("applied", 0)
    run.latency_ms = result.mesh.latency_ms
    run.input_tokens = input_tokens
    run.output_tokens = output_tokens
    details = {
        **run.details,
        **reported_billing(result.mesh),
        "reported_model": result.mesh.completion.model,
        "outcomes": dict(sorted(outcomes.items())),
        "unknown_label_ids": unknown_ids,
        "min_confidence_bps": MIN_SEMANTIC_CONFIDENCE_BPS,
    }
    if result.mesh.guardrails is not None:
        details["output_guardrails"] = result.mesh.guardrails
    run.details = details
    await session.commit()
    await session.refresh(run)
    remaining, _ = _group_labels(await _pending_rows(session, tenant_id, account_id))
    return CategorizationResult(run, len(rows), withheld, _sendable_rows(remaining))
