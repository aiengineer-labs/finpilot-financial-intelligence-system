import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SESSION_SECRET", "test-only-secret-with-at-least-thirty-two-chars")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./.test-finpilot.db")
os.environ.setdefault("CRON_SECRET", "test-cron-secret-with-at-least-thirty-two-chars")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database.base import Base
from app.database.session import engine
from app.main import app


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
