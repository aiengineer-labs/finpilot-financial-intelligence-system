import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SESSION_SECRET", "test-only-secret-with-at-least-thirty-two-chars")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./.test-finpilot.db")
os.environ.setdefault("CRON_SECRET", "test-cron-secret-with-at-least-thirty-two-chars")

from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database.base import Base
from app.database.session import engine
from app.main import app
from app.services import governance


@pytest.fixture(autouse=True)
def no_committed_redteam_evidence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Tests start from "never run"; a test that needs evidence writes this path itself."""

    path = tmp_path / "model_redteam.json"
    monkeypatch.setattr(governance, "MODEL_REDTEAM_EVIDENCE", path)
    return path


@pytest_asyncio.fixture(autouse=True)
async def reset_database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value
