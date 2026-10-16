from httpx import AsyncClient


async def _register(client: AsyncClient, email: str, household: str) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "household_name": household,
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    return token, me.json()["tenants"][0]["id"]


async def test_authentication_and_tenant_isolation(client: AsyncClient) -> None:
    token_a, tenant_a = await _register(client, "a@example.com", "Alpha")
    token_b, tenant_b = await _register(client, "b@example.com", "Beta")

    created = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token_a}", "X-Tenant-ID": tenant_a},
        json={"name": "Alpha Current", "currency": "INR", "external_reference": "alpha-1"},
    )
    assert created.status_code == 201

    forbidden = await client.get(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token_b}", "X-Tenant-ID": tenant_a},
    )
    assert forbidden.status_code == 404

    own = await client.get(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token_b}", "X-Tenant-ID": tenant_b},
    )
    assert own.status_code == 200
    assert own.json() == []


async def test_missing_authentication_is_rejected(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/accounts", headers={"X-Tenant-ID": "00000000-0000-0000-0000-000000000001"}
    )
    assert response.status_code == 401


async def test_duplicate_registration_is_a_conflict(client: AsyncClient) -> None:
    await _register(client, "repeat@example.com", "First")
    repeated = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "Repeat@example.com",
            "password": "another-long-password",
            "household_name": "Second",
        },
    )
    assert repeated.status_code == 409
    assert repeated.json()["detail"] == "email already registered"
