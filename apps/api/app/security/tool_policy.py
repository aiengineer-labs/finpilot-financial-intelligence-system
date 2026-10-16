from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AgentRole(StrEnum):
    SUPERVISOR = "supervisor"
    CATEGORIZER = "categorizer"
    ANALYST = "analyst"
    ADVISOR = "advisor"
    CRITIC = "critic"


_ALLOWLIST: dict[AgentRole, frozenset[str]] = {
    AgentRole.SUPERVISOR: frozenset({"route_intent"}),
    AgentRole.CATEGORIZER: frozenset({"read_transaction_context", "suggest_category"}),
    AgentRole.ANALYST: frozenset({"read_snapshot", "read_anomalies"}),
    AgentRole.ADVISOR: frozenset({"read_snapshot", "read_forecast", "read_scenario"}),
    AgentRole.CRITIC: frozenset({"read_evidence", "request_revision"}),
}


@dataclass(frozen=True)
class ToolAuthorization:
    allowed: bool
    reason: str


def authorize_tool(role: AgentRole, tool: str, arguments: dict[str, Any]) -> ToolAuthorization:
    if tool not in _ALLOWLIST[role]:
        return ToolAuthorization(False, "tool is not allowed for this agent role")
    forbidden = {"tenant_id", "user_id", "mesh_base_url", "policy", "permissions"}
    if forbidden.intersection(arguments):
        return ToolAuthorization(False, "security context cannot be supplied by model output")
    return ToolAuthorization(True, "allowed by static role policy")
