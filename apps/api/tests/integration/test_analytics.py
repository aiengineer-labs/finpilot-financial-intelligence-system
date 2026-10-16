import json

from httpx import AsyncClient


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


async def test_versioned_forecast_and_immutable_scenario_are_tenant_scoped(
    client: AsyncClient,
) -> None:
    token_a, tenant_a = await _identity(client, "analytics-a@example.com", "Analytics Alpha")
    token_b, tenant_b = await _identity(client, "analytics-b@example.com", "Analytics Beta")
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Tenant-ID": tenant_a}
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Tenant-ID": tenant_b}
    account = await client.post(
        "/api/v1/accounts",
        headers=headers_a,
        json={"name": "Salary", "currency": "INR", "external_reference": "analytics"},
    )
    account_id = account.json()["id"]
    csv_data = b"""Date,Amount,Merchant,Description,Transaction ID,Currency,Balance
2026-07-01,1000.00,ACME Payroll,Salary,jul,INR,1000.00
2026-08-01,1000.00,ACME Payroll,Salary,aug,INR,2000.00
2026-09-01,1000.00,ACME Payroll,Salary,sep,INR,3000.00
2026-10-01,1000.00,ACME Payroll,Salary,oct,INR,4000.00
"""
    mapping = {
        "date": "Date",
        "date_format": "%Y-%m-%d",
        "signed_amount": "Amount",
        "merchant": "Merchant",
        "description": "Description",
        "transaction_id": "Transaction ID",
        "currency": "Currency",
        "balance": "Balance",
    }
    uploaded = await client.post(
        f"/api/v1/accounts/{account_id}/transaction-uploads",
        headers=headers_a,
        data={"mapping": json.dumps(mapping)},
        files={"file": ("analytics.csv", csv_data, "text/csv")},
    )
    assert uploaded.status_code == 200, uploaded.text

    snapshot = await client.post(
        "/api/v1/analytics/snapshots",
        headers=headers_a,
        json={"account_id": account_id, "as_of": "2026-09-01"},
    )
    assert snapshot.status_code == 201, snapshot.text
    snapshot_body = snapshot.json()
    assert snapshot_body["opening_balance_minor"] == 300_000
    assert snapshot_body["source_transaction_count"] == 3
    assert len(snapshot_body["recurring_patterns"]) == 1

    replay = await client.post(
        "/api/v1/analytics/snapshots",
        headers=headers_a,
        json={"account_id": account_id, "as_of": "2026-09-01"},
    )
    assert replay.json()["id"] == snapshot_body["id"]

    forecast = await client.post(
        "/api/v1/analytics/forecasts",
        headers=headers_a,
        json={"snapshot_id": snapshot_body["id"], "horizon_days": 30},
    )
    assert forecast.status_code == 201, forecast.text
    forecast_body = forecast.json()
    assert len(forecast_body["points"]) == 30
    assert forecast_body["points"][-1]["balance_minor"] == 400_000

    scenario = await client.post(
        "/api/v1/analytics/scenarios",
        headers=headers_a,
        json={
            "forecast_id": forecast_body["id"],
            "name": "Laptop next month",
            "shocks": [
                {"day": "2026-09-10", "amount_minor": -750_000, "label": "Laptop"}
            ],
        },
    )
    assert scenario.status_code == 201, scenario.text
    scenario_body = scenario.json()
    assert scenario_body["ending_delta_minor"] == -750_000
    assert scenario_body["first_shortfall_date"] == "2026-09-10"
    assert len(scenario_body["points"]) == 30

    assert (
        await client.get(
            f"/api/v1/analytics/forecasts/{forecast_body['id']}", headers=headers_b
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/analytics/scenarios/{scenario_body['id']}", headers=headers_b
        )
    ).status_code == 404
