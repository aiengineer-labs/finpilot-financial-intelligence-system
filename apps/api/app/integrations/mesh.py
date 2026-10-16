import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.settings import Settings


class MeshMessage(BaseModel):
    role: str
    content: str = Field(max_length=20_000)


class MeshCompletion(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    model: str
    choices: list[dict[str, Any]]
    usage: dict[str, int] | None = None


@dataclass(frozen=True)
class MeshResult:
    completion: MeshCompletion
    latency_ms: int


class MeshTransport(Protocol):
    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class HttpMeshTransport:
    def __init__(self, settings: Settings) -> None:
        if settings.mesh_api_key is None:
            raise RuntimeError("MESH_API_KEY is required for model inference")
        self._client = httpx.AsyncClient(
            base_url=str(settings.mesh_base_url).rstrip("/"),
            timeout=settings.mesh_timeout_seconds,
            headers={"Authorization": f"Bearer {settings.mesh_api_key.get_secret_value()}"},
        )

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post(path, json=payload)
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]


class MeshClient:
    """The sole application boundary for all model inference."""

    def __init__(self, settings: Settings, transport: MeshTransport | None = None) -> None:
        if not settings.mesh_model:
            raise RuntimeError("MESH_MODEL must be configured before model inference")
        self._settings = settings
        self._transport = transport or HttpMeshTransport(settings)

    async def complete(self, messages: list[MeshMessage], *, max_tokens: int = 800) -> MeshResult:
        started = time.monotonic()
        payload = {
            "model": self._settings.mesh_model,
            "messages": [message.model_dump() for message in messages],
            "max_tokens": max_tokens,
            "temperature": 0,
        }
        raw = await self._transport.post("/chat/completions", payload)
        completion = MeshCompletion.model_validate(raw)
        return MeshResult(completion, int((time.monotonic() - started) * 1000))
