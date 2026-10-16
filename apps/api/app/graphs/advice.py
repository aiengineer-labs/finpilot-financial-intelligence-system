from __future__ import annotations

from typing import Any, Literal, TypedDict, cast

from langgraph.graph import END, START, StateGraph

from app.agents.specialists import (
    AdvisorOutput,
    AnalysisOutput,
    BehaviorAnalystAgent,
    CriticAgent,
    CriticOutput,
    FinancialAdvisorAgent,
)
from app.database.models import VerificationStatus
from app.integrations.mesh import MeshClient, MeshResult

GRAPH_VERSION = "advice-graph-v1"
PROMPT_VERSION = "advice-prompts-v1"
VERIFIER_VERSION = "financial-verifier-v1"


class AdviceState(TypedDict):
    question: str
    context: dict[str, Any]
    intent: str
    analysis: dict[str, Any]
    draft: dict[str, Any]
    critique: dict[str, Any]
    verification_status: str
    verification_reasons: list[str]
    revision_attempts: int
    events: list[dict[str, Any]]
    final_response: str


def _usage(result: MeshResult) -> tuple[int, int]:
    usage = result.completion.usage or {}
    return usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


def _mesh_event(node: str, summary: str, result: MeshResult) -> dict[str, Any]:
    input_tokens, output_tokens = _usage(result)
    details: dict[str, Any] = {"gateway": "Mesh API", "model": result.completion.model}
    if result.guardrails is not None:
        details["guardrails"] = result.guardrails
    return {
        "node": node,
        "event_type": "mesh_completion",
        "summary": summary,
        "details": details,
        "model_id": result.completion.model,
        "latency_ms": result.latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def verify_advice(
    draft: AdvisorOutput, context: dict[str, Any], revision_attempts: int
) -> tuple[VerificationStatus, list[str]]:
    allowed_evidence = set(cast(list[str], context.get("evidence_ids", [])))
    allowed_amounts = set(cast(list[int], context.get("allowed_amount_minor", [])))
    currency = context.get("currency")
    reasons: list[str] = []
    for index, recommendation in enumerate(draft.recommendations, start=1):
        prefix = f"recommendation {index}"
        evidence = set(recommendation.evidence_ids)
        if not evidence or not evidence.issubset(allowed_evidence):
            reasons.append(f"{prefix} cites unavailable evidence")
        if (
            recommendation.amount_minor is not None
            and recommendation.amount_minor not in allowed_amounts
        ):
            reasons.append(f"{prefix} contains an unverified amount")
        if recommendation.currency != currency:
            reasons.append(f"{prefix} uses the wrong currency")
        lowered = f"{recommendation.title} {recommendation.explanation}".casefold()
        if any(term in lowered for term in ("guaranteed", "certain return", "risk-free")):
            reasons.append(f"{prefix} uses prohibited certainty")
    if not draft.recommendations:
        return VerificationStatus.INSUFFICIENT_DATA, ["no recommendation was produced"]
    if not reasons:
        return VerificationStatus.ACCEPT, []
    if revision_attempts < 1:
        return VerificationStatus.REVISE, reasons
    return VerificationStatus.REJECT, reasons


def _render_accepted(draft: AdvisorOutput, context: dict[str, Any]) -> str:
    currency = str(context["currency"])
    lines = ["Verified options:"]
    for index, item in enumerate(draft.recommendations, start=1):
        amount = f" ({item.amount_minor} {currency} minor units)" if item.amount_minor else ""
        lines.append(f"{index}. {item.title}{amount}: {item.explanation}")
    lines.append(
        "These are estimated options based on the cited snapshot, not guaranteed outcomes."
    )
    return "\n".join(lines)


class AdviceWorkflow:
    def __init__(self, mesh: MeshClient) -> None:
        self._analyst = BehaviorAnalystAgent(mesh)
        self._advisor = FinancialAdvisorAgent(mesh)
        self._critic = CriticAgent(mesh)
        builder = StateGraph(AdviceState)
        builder.add_node("supervisor", self._supervisor)
        builder.add_node("behavior_analyst", self._behavior_analyst)
        builder.add_node("financial_advisor", self._financial_advisor)
        builder.add_node("verification", self._verification)
        builder.add_node("critic", self._critic_node)
        builder.add_node("revision", self._revision)
        builder.add_edge(START, "supervisor")
        builder.add_edge("supervisor", "behavior_analyst")
        builder.add_edge("behavior_analyst", "financial_advisor")
        builder.add_edge("financial_advisor", "verification")
        builder.add_conditional_edges(
            "verification",
            self._route_verification,
            {"accept": END, "revise": "critic", "reject": END},
        )
        builder.add_edge("critic", "revision")
        builder.add_edge("revision", "verification")
        self.graph = builder.compile()

    async def run(
        self,
        *,
        question: str,
        context: dict[str, Any],
        guardrail_events: list[dict[str, Any]] | None = None,
    ) -> AdviceState:
        initial: AdviceState = {
            "question": question,
            "context": context,
            "intent": "",
            "analysis": {},
            "draft": {},
            "critique": {},
            "verification_status": VerificationStatus.INSUFFICIENT_DATA.value,
            "verification_reasons": [],
            "revision_attempts": 0,
            "events": list(guardrail_events or []),
            "final_response": "",
        }
        return cast(AdviceState, await self.graph.ainvoke(initial))

    async def _supervisor(self, state: AdviceState) -> dict[str, Any]:
        intent = "scenario_advice" if state["context"].get("scenario_id") else "forecast_advice"
        event = {
            "node": "supervisor",
            "event_type": "route",
            "summary": f"Routed request to {intent}",
            "details": {"intent": intent, "tool": "route_intent"},
        }
        return {"intent": intent, "events": [*state["events"], event]}

    async def _behavior_analyst(self, state: AdviceState) -> dict[str, Any]:
        result = await self._analyst.run(state["question"], state["context"])
        analysis = cast(AnalysisOutput, result.payload)
        event = _mesh_event("behavior_analyst", "Explained deterministic patterns", result.mesh)
        return {"analysis": analysis.model_dump(), "events": [*state["events"], event]}

    async def _financial_advisor(self, state: AdviceState) -> dict[str, Any]:
        result = await self._advisor.run(
            state["question"], state["context"], AnalysisOutput.model_validate(state["analysis"])
        )
        draft = cast(AdvisorOutput, result.payload)
        event = _mesh_event("financial_advisor", "Drafted evidence-bound options", result.mesh)
        return {"draft": draft.model_dump(), "events": [*state["events"], event]}

    async def _verification(self, state: AdviceState) -> dict[str, Any]:
        draft = AdvisorOutput.model_validate(state["draft"])
        status, reasons = verify_advice(draft, state["context"], state["revision_attempts"])
        event = {
            "node": "verification",
            "event_type": "deterministic_gate",
            "summary": f"Financial verification: {status.value}",
            "details": {"status": status.value, "reasons": reasons},
        }
        final = (
            _render_accepted(draft, state["context"]) if status is VerificationStatus.ACCEPT else ""
        )
        if status in {VerificationStatus.REJECT, VerificationStatus.INSUFFICIENT_DATA}:
            final = "Advice was withheld because deterministic financial verification did not pass."
        return {
            "verification_status": status.value,
            "verification_reasons": reasons,
            "events": [*state["events"], event],
            "final_response": final,
        }

    def _route_verification(self, state: AdviceState) -> Literal["accept", "revise", "reject"]:
        if state["verification_status"] == VerificationStatus.ACCEPT.value:
            return "accept"
        if state["verification_status"] == VerificationStatus.REVISE.value:
            return "revise"
        return "reject"

    async def _critic_node(self, state: AdviceState) -> dict[str, Any]:
        result = await self._critic.run(
            state["question"],
            state["context"],
            AdvisorOutput.model_validate(state["draft"]),
            state["verification_reasons"],
        )
        critique = cast(CriticOutput, result.payload)
        event = _mesh_event("critic", "Challenged rejected claims", result.mesh)
        return {"critique": critique.model_dump(), "events": [*state["events"], event]}

    async def _revision(self, state: AdviceState) -> dict[str, Any]:
        result = await self._advisor.run(
            state["question"],
            state["context"],
            AnalysisOutput.model_validate(state["analysis"]),
            CriticOutput.model_validate(state["critique"]),
        )
        draft = cast(AdvisorOutput, result.payload)
        event = _mesh_event("revision", "Revised advice after verifier feedback", result.mesh)
        return {
            "draft": draft.model_dump(),
            "revision_attempts": state["revision_attempts"] + 1,
            "events": [*state["events"], event],
        }
