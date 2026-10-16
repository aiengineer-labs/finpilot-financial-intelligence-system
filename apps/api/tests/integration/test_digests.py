from datetime import UTC, datetime, timedelta
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import update

from app.database.models import DigestPreference
from app.database.session import SessionFactory
from app.services.digests import next_weekly_due


async def _identity(client: AsyncClient, email: str, household: str) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "household_name": household,
        },
    )
    token = response.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    return token, me.json()["tenants"][0]["id"]


def _headers(token: str, tenant_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant_id}


def test_next_weekly_due_respects_local_timezone() -> None:
    due = next_weekly_due(
        weekday=0,
        local_time="09:00",
        timezone="Asia/Kolkata",
        after=datetime(2026, 10, 16, 12, 0, tzinfo=UTC),
    )
    assert due == datetime(2026, 10, 19, 3, 30, tzinfo=UTC)


async def test_signed_digest_dispatch_is_persisted_idempotent_and_tenant_safe(
    client: AsyncClient,
) -> None:
    preflight = await client.options(
        "/api/v1/digests/preference",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PUT",
        },
    )
    assert preflight.status_code == 200
    assert "PUT" in preflight.headers["access-control-allow-methods"]

    token_a, tenant_a = await _identity(client, "digest-a@example.com", "Digest Alpha")
    token_b, tenant_b = await _identity(client, "digest-b@example.com", "Digest Beta")
    headers_a = _headers(token_a, tenant_a)
    headers_b = _headers(token_b, tenant_b)

    preference = await client.put(
        "/api/v1/digests/preference",
        headers=headers_a,
        json={"enabled": True, "weekday": 0, "local_time": "09:00", "timezone": "Asia/Kolkata"},
    )
    assert preference.status_code == 200, preference.text
    assert (await client.get("/api/v1/digests/preference", headers=headers_b)).json() is None

    async with SessionFactory() as session:
        await session.execute(
            update(DigestPreference)
            .where(DigestPreference.id == UUID(preference.json()["id"]))
            .values(next_due_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()

    unauthorized = await client.get("/api/v1/digests/dispatch")
    assert unauthorized.status_code == 401
    dispatched = await client.get(
        "/api/v1/digests/dispatch",
        headers={"Authorization": "Bearer test-cron-secret-with-at-least-thirty-two-chars"},
    )
    assert dispatched.status_code == 200, dispatched.text
    assert dispatched.json()["claimed"] == 1
    assert dispatched.json()["delivered"] == 1

    replay = await client.get(
        "/api/v1/digests/dispatch",
        headers={"Authorization": "Bearer test-cron-secret-with-at-least-thirty-two-chars"},
    )
    assert replay.status_code == 200
    assert replay.json()["claimed"] == 0

    jobs = await client.get("/api/v1/digests/jobs", headers=headers_a)
    notifications = await client.get("/api/v1/digests/notifications", headers=headers_a)
    assert len(jobs.json()) == 1
    assert jobs.json()[0]["status"] == "delivered"
    assert jobs.json()[0]["insight_kind"] == "setup_required"
    assert len(notifications.json()) == 1
    assert notifications.json()[0]["digest_job_id"] == jobs.json()[0]["id"]
    assert (await client.get("/api/v1/digests/jobs", headers=headers_b)).json() == []
    assert (await client.get("/api/v1/digests/notifications", headers=headers_b)).json() == []
