"""Inspectable, authenticated description of the deployed neuro-symbolic workflow."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import TenantContext, tenant_context
from app.core.settings import Settings, get_settings
from app.graphs.manifest import (
    GRAPH_VERSION,
    PROMPT_VERSION,
    SYSTEM_GRAPH_EDGES,
    SYSTEM_GRAPH_NODES,
    VERIFIER_VERSION,
)

router = APIRouter(prefix="/system", tags=["system"])


class ArchitectureNode(BaseModel):
    id: str
    label: str
    detail: str
    runtime: str
    kind: Literal["input", "guardrail", "deterministic", "store", "mesh", "verifier", "output"]
    x: int
    y: int


class ArchitectureEdge(BaseModel):
    source: str
    target: str
    label: str
    branch: Literal["normal", "revise", "reject", "audit", "mesh"]


class ArchitectureResponse(BaseModel):
    graph_version: str
    prompt_version: str
    verifier_version: str
    mesh_model: str | None
    nodes: list[ArchitectureNode]
    edges: list[ArchitectureEdge]


@router.get("/architecture", response_model=ArchitectureResponse)
async def architecture(
    _context: Annotated[TenantContext, Depends(tenant_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ArchitectureResponse:
    """Return the same versioned manifest used to assemble the executable advice graph."""
    return ArchitectureResponse(
        graph_version=GRAPH_VERSION,
        prompt_version=PROMPT_VERSION,
        verifier_version=VERIFIER_VERSION,
        mesh_model=settings.mesh_model or None,
        nodes=[ArchitectureNode.model_validate(node) for node in SYSTEM_GRAPH_NODES],
        edges=[ArchitectureEdge.model_validate(edge) for edge in SYSTEM_GRAPH_EDGES],
    )
