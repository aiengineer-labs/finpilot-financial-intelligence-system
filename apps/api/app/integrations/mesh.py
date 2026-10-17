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
    # Mesh nests token details and reports cost_usd as a number, so usage is not all integers.
    usage: dict[str, Any] | None = None


@dataclass(frozen=True)
class MeshResult:
    completion: MeshCompletion
    latency_ms: int
    guardrails: dict[str, str] | None = None


def _count(values: Any, key: str) -> int | None:
    value = values.get(key) if isinstance(values, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def token_usage(result: MeshResult) -> tuple[int, int]:
    """Prompt and completion tokens as Mesh reports them; missing counts are zero."""

    usage = result.completion.usage or {}
    return _count(usage, "prompt_tokens") or 0, _count(usage, "completion_tokens") or 0


def reported_billing(result: MeshResult) -> dict[str, Any]:
    """Cost facts exactly as Mesh reports them; absent fields are omitted, never estimated."""

    usage = result.completion.usage or {}
    billing: dict[str, Any] = {}
    cost = usage.get("cost_usd")
    if isinstance(cost, int | float | str) and not isinstance(cost, bool):
        billing["cost_usd"] = str(cost)
    cached = _count(usage.get("prompt_tokens_details"), "cached_tokens")
    if cached is not None:
        billing["cached_input_tokens"] = cached
    reasoning = _count(usage.get("completion_tokens_details"), "reasoning_tokens")
    if reasoning is not None:
        billing["reasoning_tokens"] = reasoning
    return billing


class MeshProviderError(RuntimeError):
    """Mesh refused or could not serve a request; the reason is fixed text, never upstream data."""

    def __init__(self, reason: str, status_code: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


def _provider_reason(status_code: int) -> str:
    if status_code == 402:
        return "the Mesh account has insufficient balance for this model"
    if status_code in (401, 403):
        return "Mesh rejected the configured API key"
    if status_code == 404:
        return "Mesh does not serve the configured model"
    if status_code == 429:
        return "Mesh rate-limited the request"
    if status_code >= 500:
        return "Mesh is temporarily unavailable"
    return f"Mesh rejected the request (HTTP {status_code})"


class MeshTransport(Protocol):
    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class MeshOutputGuard(Protocol):
    async def process_output(self, text: str) -> str: ...


def _strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return an OpenAI-compatible strict schema for a Pydantic response model."""
    schema = model.model_json_schema()

    def close_objects(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") == "object" and isinstance(value.get("properties"), dict):
                value["additionalProperties"] = False
                value["required"] = list(value["properties"])
            for nested in value.values():
                close_objects(nested)
        elif isinstance(value, list):
            for nested in value:
                close_objects(nested)

    close_objects(schema)
    return schema


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
        try:
            response = await self._client.post(path, json=payload)
        except httpx.TimeoutException as exc:
            raise MeshProviderError("Mesh did not respond in time") from exc
        except httpx.TransportError as exc:
            raise MeshProviderError("Mesh could not be reached") from exc
        if response.is_error:
            raise MeshProviderError(_provider_reason(response.status_code), response.status_code)
        return response.json()  # type: ignore[no-any-return]


class MeshClient:
    """The sole application boundary for all model inference."""

    def __init__(
        self,
        settings: Settings,
        transport: MeshTransport | None = None,
        output_guard: MeshOutputGuard | None = None,
    ) -> None:
        if not settings.mesh_model:
            raise RuntimeError("MESH_MODEL must be configured before model inference")
        self._settings = settings
        self._transport = transport or HttpMeshTransport(settings)
        self._output_guard = output_guard

    async def complete(
        self,
        messages: list[MeshMessage],
        *,
        max_tokens: int = 800,
        json_output: bool = False,
        response_schema: type[BaseModel] | None = None,
    ) -> MeshResult:
        started = time.monotonic()
        payload: dict[str, Any] = {
            "model": self._settings.mesh_model,
            "messages": [message.model_dump() for message in messages],
            "max_tokens": max_tokens,
        }
        effort = self._settings.mesh_reasoning_effort
        if effort is None:
            payload["temperature"] = 0
        else:
            # Reasoning models accept only their default temperature. Omitting it keeps the
            # request eligible for Mesh's 24-hour response cache.
            payload["reasoning"] = {"effort": effort}
        if response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.__name__,
                    "strict": True,
                    "schema": _strict_json_schema(response_schema),
                },
            }
        elif json_output:
            payload["response_format"] = {"type": "json_object"}
        raw = await self._transport.post("/chat/completions", payload)
        completion = MeshCompletion.model_validate(raw)
        guardrail_metadata: dict[str, str] | None = None
        if self._output_guard is not None:
            for choice in completion.choices:
                message = choice.get("message")
                if not isinstance(message, dict):
                    continue
                content = message.get("content")
                if isinstance(content, str):
                    message["content"] = await self._output_guard.process_output(content)
            guardrail_metadata = {"output": "passed", "stack": "NeMo Guardrails + Presidio"}
        return MeshResult(
            completion,
            int((time.monotonic() - started) * 1000),
            guardrail_metadata,
        )
