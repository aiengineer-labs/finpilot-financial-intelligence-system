"""Single-source manifest for the executable FinPilot decision graph and its UI."""

from typing import Final, Literal, TypedDict

GRAPH_VERSION: Final = "advice-graph-v2"
PROMPT_VERSION: Final = "advice-prompts-v4"
VERIFIER_VERSION: Final = "financial-verifier-v1"

NodeKind = Literal["input", "guardrail", "deterministic", "store", "mesh", "verifier", "output"]


class GraphNode(TypedDict):
    id: str
    label: str
    detail: str
    runtime: str
    kind: NodeKind
    x: int
    y: int


class GraphEdge(TypedDict, total=False):
    source: str
    target: str
    label: str
    branch: Literal["normal", "revise", "reject", "audit", "mesh"]


SYSTEM_GRAPH_NODES: Final[tuple[GraphNode, ...]] = (
    {
        "id": "upload",
        "label": "Bank statement",
        "detail": "User-selected CSV or PDF; no preloaded ledger values.",
        "runtime": "Untrusted input",
        "kind": "input",
        "x": 90,
        "y": 105,
    },
    {
        "id": "input_policy",
        "label": "Input shield",
        "detail": "Content detection, resource limits, schema and active-content controls.",
        "runtime": "Deterministic policy",
        "kind": "guardrail",
        "x": 285,
        "y": 105,
    },
    {
        "id": "ingestion",
        "label": "Ingestion engine",
        "detail": "Parses exact minor units, dates, transfers, refunds and duplicates.",
        "runtime": "FastAPI · Python",
        "kind": "deterministic",
        "x": 480,
        "y": 105,
    },
    {
        "id": "ledger",
        "label": "Ledger truth",
        "detail": "Tenant-isolated transactions and immutable import lineage.",
        "runtime": "PostgreSQL",
        "kind": "store",
        "x": 675,
        "y": 105,
    },
    {
        "id": "financial_engines",
        "label": "Financial engines",
        "detail": "Recurrence, robust anomalies, forecast and scenario branches.",
        "runtime": "Integer math",
        "kind": "deterministic",
        "x": 870,
        "y": 105,
    },
    {
        "id": "supervisor",
        "label": "Supervisor",
        "detail": "Routes spending, forecast, or scenario advice under a bounded budget.",
        "runtime": "LangGraph",
        "kind": "deterministic",
        "x": 1065,
        "y": 105,
    },
    {
        "id": "behavior_analyst",
        "label": "Behavior analyst",
        "detail": "Explains supplied engine evidence without doing financial arithmetic.",
        "runtime": "Mesh API",
        "kind": "mesh",
        "x": 870,
        "y": 300,
    },
    {
        "id": "financial_advisor",
        "label": "Financial advisor",
        "detail": "Drafts ranked actions tied to allowed evidence and verified amounts.",
        "runtime": "Mesh API",
        "kind": "mesh",
        "x": 1065,
        "y": 300,
    },
    {
        "id": "verification",
        "label": "Financial verifier",
        "detail": "Checks money, currency, evidence, permissions and prohibited certainty.",
        "runtime": "Fail-closed code",
        "kind": "verifier",
        "x": 1065,
        "y": 495,
    },
    {
        "id": "critic",
        "label": "Adversarial critic",
        "detail": "Challenges rejected claims before one bounded revision attempt.",
        "runtime": "Mesh API",
        "kind": "mesh",
        "x": 675,
        "y": 495,
    },
    {
        "id": "revision",
        "label": "Revision",
        "detail": "Rewrites the draft from verifier reasons and critic findings.",
        "runtime": "Mesh API",
        "kind": "mesh",
        "x": 870,
        "y": 495,
    },
    {
        "id": "verified_output",
        "label": "Verified decision",
        "detail": "Releases accepted advice or a transparent withheld response.",
        "runtime": "Terminal state",
        "kind": "output",
        "x": 1065,
        "y": 650,
    },
    {
        "id": "audit",
        "label": "Audit ledger",
        "detail": "Persists transitions, versions, evidence, tokens, latency and verdicts.",
        "runtime": "PostgreSQL",
        "kind": "store",
        "x": 285,
        "y": 650,
    },
    {
        "id": "mesh_gateway",
        "label": "Mesh gateway",
        "detail": "The only LLM egress: allowlisted model, timeouts and structured output.",
        "runtime": "Mesh API only",
        "kind": "guardrail",
        "x": 675,
        "y": 650,
    },
)

SYSTEM_GRAPH_EDGES: Final[tuple[GraphEdge, ...]] = (
    {"source": "upload", "target": "input_policy", "label": "file", "branch": "normal"},
    {
        "source": "input_policy",
        "target": "ingestion",
        "label": "validated rows",
        "branch": "normal",
    },
    {"source": "ingestion", "target": "ledger", "label": "normalized", "branch": "normal"},
    {
        "source": "ledger",
        "target": "financial_engines",
        "label": "versioned truth",
        "branch": "normal",
    },
    {
        "source": "financial_engines",
        "target": "supervisor",
        "label": "evidence",
        "branch": "normal",
    },
    {"source": "supervisor", "target": "behavior_analyst", "label": "route", "branch": "normal"},
    {
        "source": "behavior_analyst",
        "target": "financial_advisor",
        "label": "analysis",
        "branch": "normal",
    },
    {"source": "financial_advisor", "target": "verification", "label": "draft", "branch": "normal"},
    {
        "source": "verification",
        "target": "verified_output",
        "label": "accept / withhold",
        "branch": "normal",
    },
    {"source": "verification", "target": "critic", "label": "revise", "branch": "revise"},
    {"source": "critic", "target": "revision", "label": "critique", "branch": "revise"},
    {"source": "revision", "target": "verification", "label": "one retry", "branch": "revise"},
    {"source": "mesh_gateway", "target": "behavior_analyst", "label": "model", "branch": "mesh"},
    {"source": "mesh_gateway", "target": "financial_advisor", "label": "model", "branch": "mesh"},
    {"source": "mesh_gateway", "target": "critic", "label": "model", "branch": "mesh"},
    {
        "source": "verified_output",
        "target": "audit",
        "label": "decision lineage",
        "branch": "audit",
    },
)

ADVICE_NODE_IDS: Final = (
    "supervisor",
    "behavior_analyst",
    "financial_advisor",
    "verification",
    "critic",
    "revision",
)
