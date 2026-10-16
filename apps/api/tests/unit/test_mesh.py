from typing import Any

import pytest
from pydantic import SecretStr

from app.core.settings import Settings
from app.integrations.mesh import MeshClient, MeshMessage


class FakeMeshTransport:
    def __init__(self) -> None:
        self.path = ""
        self.payload: dict[str, Any] = {}

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.path = path
        self.payload = payload
        return {
            "id": "fake-1",
            "model": "mesh-test-model",
            "choices": [{"message": {"content": "ok"}}],
        }


async def test_mesh_client_uses_only_central_transport() -> None:
    settings = Settings(
        session_secret=SecretStr("test-only-secret-with-at-least-thirty-two-chars"),
        database_url="sqlite+aiosqlite://",
        mesh_model="mesh-test-model",
    )
    transport = FakeMeshTransport()
    result = await MeshClient(settings, transport).complete(
        [MeshMessage(role="user", content="hello")]
    )
    assert result.completion.model == "mesh-test-model"
    assert transport.path == "/chat/completions"
    assert transport.payload["temperature"] == 0


def test_non_mesh_endpoint_is_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(
            session_secret=SecretStr("test-only-secret-with-at-least-thirty-two-chars"),
            database_url="sqlite+aiosqlite://",
            mesh_base_url="https://api.openai.com/v1",
        )
