import json
from pathlib import Path

from httpx import AsyncClient

GOLDEN_CSV = Path("../../evaluation/datasets/phase2_golden.csv").read_bytes()


async def _identity(client: AsyncClient, email: str, household: str) -> tuple[str, str]:
    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "household_name": household,
        },
    )
    token = registered.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    return token, me.json()["tenants"][0]["id"]


async def test_upload_is_idempotent_scoped_and_correctable(client: AsyncClient) -> None:
    token_a, tenant_a = await _identity(client, "csv-a@example.com", "CSV Alpha")
    token_b, tenant_b = await _identity(client, "csv-b@example.com", "CSV Beta")
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Tenant-ID": tenant_a}
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Tenant-ID": tenant_b}
    account_response = await client.post(
        "/api/v1/accounts",
        headers=headers_a,
        json={"name": "Current", "currency": "INR", "external_reference": "current"},
    )
    account_id = account_response.json()["id"]
    mapping = {
        "date": "Date",
        "date_format": "%d/%m/%Y",
        "debit": "Debit",
        "credit": "Credit",
        "merchant": "Merchant",
        "description": "Description",
        "transaction_id": "Transaction ID",
        "currency": "Currency",
        "balance": "Balance",
    }
    first = await client.post(
        f"/api/v1/accounts/{account_id}/transaction-uploads",
        headers=headers_a,
        data={"mapping": json.dumps(mapping)},
        files={"file": ("golden.csv", GOLDEN_CSV, "text/csv")},
    )
    assert first.status_code == 200, first.text
    assert first.json()["accepted_rows"] == 5
    assert first.json()["duplicate_rows"] == 1
    assert first.json()["rejected_rows"] == 1
    assert not first.json()["replayed"]

    replay = await client.post(
        f"/api/v1/accounts/{account_id}/transaction-uploads",
        headers=headers_a,
        data={"mapping": json.dumps(mapping)},
        files={"file": ("renamed.csv", GOLDEN_CSV, "text/csv")},
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["replayed"]

    page = await client.get("/api/v1/transactions", headers=headers_a)
    assert page.status_code == 200
    assert page.json()["total"] == 5
    transfer = next(item for item in page.json()["items"] if item["kind"] == "transfer")
    assert transfer["is_excluded_from_cashflow"]

    corrected = await client.patch(
        f"/api/v1/transactions/{page.json()['items'][0]['id']}/category",
        headers=headers_a,
        json={"category": "household_supplies", "reason": "User verified receipt"},
    )
    assert corrected.status_code == 200
    assert corrected.json()["classification_method"] == "human"

    cross_tenant = await client.post(
        f"/api/v1/accounts/{account_id}/transaction-uploads",
        headers=headers_b,
        data={"mapping": json.dumps(mapping)},
        files={"file": ("golden.csv", GOLDEN_CSV, "text/csv")},
    )
    assert cross_tenant.status_code == 404
