import json
from typing import Any
from uuid import UUID

from httpx import AsyncClient
from pydantic import SecretStr

from app.core.settings import Settings
from app.database.session import SessionFactory
from app.integrations.mesh import MeshClient
from app.services.agent_runs import execute_advice


class FakeAgentTransport:
    def __init__(self, contents: list[dict[str, Any]]) -> None:
        self.contents = contents

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        content = self.contents.pop(0)
        return {
            "id": "fake-agent",
            "model": "mesh-test-model",
            "choices": [{"message": {"content": json.dumps(content)}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8},
        }


async def _identity(client: AsyncClient, email: str, household: str) -> tuple[str, str, str]:
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
    return token, me.json()["tenants"][0]["id"], me.json()["id"]


async def test_versioned_forecast_and_immutable_scenario_are_tenant_scoped(
    client: AsyncClient,
) -> None:
    token_a, tenant_a, user_a = await _identity(
        client, "analytics-a@example.com", "Analytics Alpha"
    )
    token_b, tenant_b, _ = await _identity(client, "analytics-b@example.com", "Analytics Beta")
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
            "shocks": [{"day": "2026-09-10", "amount_minor": -750_000, "label": "Laptop"}],
        },
    )
    assert scenario.status_code == 201, scenario.text
    scenario_body = scenario.json()
    assert scenario_body["ending_delta_minor"] == -750_000
    assert scenario_body["first_shortfall_date"] == "2026-09-10"
    assert len(scenario_body["points"]) == 30

    assert (
        await client.get(f"/api/v1/analytics/forecasts/{forecast_body['id']}", headers=headers_b)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/analytics/scenarios/{scenario_body['id']}", headers=headers_b)
    ).status_code == 404

    transport = FakeAgentTransport(
        [
            {
                "findings": [
                    {
                        "finding": "The simulated purchase creates a shortfall.",
                        "evidence_ids": [scenario_body["id"]],
                        "limitation": "Only recorded assumptions are included.",
                    }
                ],
                "summary": "The deterministic scenario falls below zero.",
            },
            {
                "recommendations": [
                    {
                        "title": "Delay or reduce the purchase",
                        "explanation": "The scenario evidence shows a projected shortfall.",
                        "amount_minor": 750_000,
                        "currency": "INR",
                        "evidence_ids": [scenario_body["id"]],
                        "assumptions": ["No unobserved income"],
                        "confidence_bps": 8500,
                    }
                ]
            },
        ]
    )
    settings = Settings(
        session_secret=SecretStr("test-only-secret-with-at-least-thirty-two-chars"),
        database_url="sqlite+aiosqlite://",
        mesh_model="mesh-test-model",
    )
    async with SessionFactory() as session:
        execution = await execute_advice(
            session,
            tenant_id=UUID(tenant_a),
            user_id=UUID(user_a),
            forecast_id=UUID(forecast_body["id"]),
            scenario_id=UUID(scenario_body["id"]),
            question="Can I afford this purchase without a shortfall?",
            mesh=MeshClient(settings, transport),
        )
    own_run = await client.get(f"/api/v1/agent-runs/{execution.id}", headers=headers_a)
    assert own_run.status_code == 200, own_run.text
    assert own_run.json()["verification_status"] == "accept"
    assert [event["node"] for event in own_run.json()["events"]] == [
        "nemo_input",
        "presidio_minimization",
        "supervisor",
        "behavior_analyst",
        "financial_advisor",
        "verification",
    ]
    assert len(own_run.json()["recommendations"]) == 1
    recommendation_id = own_run.json()["recommendations"][0]["id"]
    original_lineage = own_run.json()["artifact_lineage"]
    assert own_run.json()["recommendations"][0]["artifact_lineage"] == original_lineage
    assert original_lineage["financial_verifier"]
    proposed_prompt = await client.post(
        "/api/v1/governance/artifacts",
        headers=headers_a,
        json={
            "artifact_type": "prompt",
            "name": "advice-prompts",
            "version": "unapproved-v2",
            "configuration": {"template_version": "unapproved-v2"},
        },
    )
    assert proposed_prompt.status_code == 201
    historical_run = await client.get(f"/api/v1/agent-runs/{execution.id}", headers=headers_a)
    assert historical_run.json()["artifact_lineage"] == original_lineage
    assert historical_run.json()["recommendations"][0]["artifact_lineage"] == original_lineage
    cross_run = await client.get(f"/api/v1/agent-runs/{execution.id}", headers=headers_b)
    assert cross_run.status_code == 404
    recommendation_review = await client.post(
        "/api/v1/governance/reviews",
        headers=headers_a,
        json={
            "recommendation_id": recommendation_id,
            "reason": "I want an independent review of the evidence for this recommendation.",
            "risk_level": "medium",
            "evidence_ids": [scenario_body["id"]],
        },
    )
    assert recommendation_review.status_code == 201, recommendation_review.text
    assert recommendation_review.json()["execution_id"] == str(execution.id)
    assert recommendation_review.json()["artifact_lineage"] == original_lineage
    cross_tenant_review = await client.post(
        "/api/v1/governance/reviews",
        headers=headers_b,
        json={
            "recommendation_id": recommendation_id,
            "reason": "A different tenant must not be able to reference this recommendation.",
            "risk_level": "medium",
            "evidence_ids": [],
        },
    )
    assert cross_tenant_review.status_code == 404


UI_MAPPING = {
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


async def test_card_and_bank_statements_are_routed_and_analysed_by_kind(
    client: AsyncClient,
) -> None:
    token, tenant, _ = await _identity(client, "statements@example.com", "Statement Mix")
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant}
    primary = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Primary account", "currency": "INR", "external_reference": "primary"},
    )
    card_id = primary.json()["id"]
    assert primary.json()["account_type"] == "unknown"

    card_csv = b"""Synthetic Card Services
Credit Card Number,XXXX XXXX XXXX 0001
Transaction Date,Transaction Details,Amount (INR)
01-Jul-2026,Streaming Service,499.00
01-Aug-2026,Streaming Service,499.00
01-Sep-2026,Streaming Service,499.00
01-Oct-2026,Streaming Service,499.00
05-Oct-2026,Grocery Market,"2,150.00"
06-Oct-2026,Grocery Market refund,150.00 Cr
"""
    uploaded = await client.post(
        f"/api/v1/accounts/{card_id}/transaction-uploads",
        headers=headers,
        data={"mapping": json.dumps(UI_MAPPING)},
        files={"file": ("card.csv", card_csv, "text/csv")},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["statement_kind"] == "credit_card"
    assert uploaded.json()["accepted_rows"] == 6
    accounts = (await client.get("/api/v1/accounts", headers=headers)).json()
    assert accounts[0]["account_type"] == "credit_card"

    snapshot = await client.post(
        "/api/v1/analytics/snapshots",
        headers=headers,
        json={"account_id": card_id, "as_of": "2026-10-06"},
    )
    assert snapshot.status_code == 201, snapshot.text
    assert snapshot.json()["analysis_mode"] == "spending"
    assert snapshot.json()["opening_balance_minor"] is None
    assert snapshot.json()["source_transaction_count"] == 6
    assert any(
        pattern["merchant"] == "streaming service"
        for pattern in snapshot.json()["recurring_patterns"]
    )
    forecast = await client.post(
        "/api/v1/analytics/forecasts",
        headers=headers,
        json={"snapshot_id": snapshot.json()["id"], "horizon_days": 30},
    )
    assert forecast.status_code == 422
    assert "Cash forecasting is unavailable" in forecast.json()["detail"]

    bank_csv = b"""Date,Narration,Withdrawal Amt.,Deposit Amt.,Closing Balance
01/10/2026,Salary ACME,,"1,000.00","5,000.00"
02/10/2026,Coffee Roasters,50.00,,"4,750.00"
02/10/2026,Grocery Market,200.00,,"4,800.00"
"""
    mismatch = await client.post(
        f"/api/v1/accounts/{card_id}/transaction-uploads",
        headers=headers,
        data={"mapping": json.dumps(UI_MAPPING)},
        files={"file": ("bank.csv", bank_csv, "text/csv")},
    )
    assert mismatch.status_code == 409, mismatch.text
    assert mismatch.json()["detail"]["code"] == "ACCOUNT_TYPE_MISMATCH"
    assert mismatch.json()["detail"]["statement_kind"] == "deposit"

    bank = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "name": "Bank account",
            "currency": "INR",
            "external_reference": "bank",
            "account_type": "deposit",
        },
    )
    bank_id = bank.json()["id"]
    imported = await client.post(
        f"/api/v1/accounts/{bank_id}/transaction-uploads",
        headers=headers,
        data={"mapping": json.dumps(UI_MAPPING)},
        files={"file": ("bank.csv", bank_csv, "text/csv")},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["statement_kind"] == "deposit"

    card_rows = await client.get(
        f"/api/v1/transactions?account_id={card_id}&limit=200", headers=headers
    )
    bank_rows = await client.get(
        f"/api/v1/transactions?account_id={bank_id}&limit=200", headers=headers
    )
    all_rows = await client.get("/api/v1/transactions?limit=200", headers=headers)
    assert card_rows.json()["total"] == 6
    assert bank_rows.json()["total"] == 3
    assert all_rows.json()["total"] == 9
    assert {row["account_id"] for row in bank_rows.json()["items"]} == {bank_id}

    cash = await client.post(
        "/api/v1/analytics/snapshots",
        headers=headers,
        json={"account_id": bank_id, "as_of": "2026-10-02"},
    )
    assert cash.status_code == 201, cash.text
    assert cash.json()["analysis_mode"] == "cashflow"
    # The chain 5,000 -> 4,800 (groceries) -> 4,750 (coffee) closes the day, whatever the
    # storage order of the two same-day rows.
    assert cash.json()["opening_balance_minor"] == 475_000


TEST_SETTINGS = Settings(
    session_secret=SecretStr("test-only-secret-with-at-least-thirty-two-chars"),
    database_url="sqlite+aiosqlite://",
    mesh_model="mesh-test-model",
)


async def test_card_statement_gets_verified_spending_advice_without_a_forecast(
    client: AsyncClient,
) -> None:
    token, tenant, user = await _identity(client, "card-advice@example.com", "Card Advice")
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant}
    account = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Primary account", "currency": "INR", "external_reference": "card"},
    )
    account_id = account.json()["id"]
    card_csv = b"""Synthetic Card Services
Credit Card Number,XXXX XXXX XXXX 0002
Transaction Date,Transaction Details,Amount (INR)
01-Sep-2026,Swift Eats Delivery,600.00
08-Sep-2026,Swift Eats Delivery,400.00
12-Sep-2026,Fresh Mart Groceries,300.00
30-Sep-2026,Netflix Subscription,499.00
"""
    uploaded = await client.post(
        f"/api/v1/accounts/{account_id}/transaction-uploads",
        headers=headers,
        data={"mapping": json.dumps(UI_MAPPING)},
        files={"file": ("card.csv", card_csv, "text/csv")},
    )
    assert uploaded.status_code == 200, uploaded.text
    snapshot = await client.post(
        "/api/v1/analytics/snapshots",
        headers=headers,
        json={"account_id": account_id, "as_of": "2026-09-30"},
    )
    assert snapshot.status_code == 201, snapshot.text
    body = snapshot.json()
    assert body["analysis_mode"] == "spending"
    spending = body["spending"]
    assert spending["account_type"] == "credit_card"
    assert spending["total_spend_minor"] == 179_900
    top = spending["categories"][0]
    assert top["spend_minor"] == 100_000 and top["monthly_saving_minor"] == 20_000
    evidence = f"category:{top['category']}"

    invented = {
        "recommendations": [
            {
                "title": "Cut delivery orders",
                "explanation": "Delivery is the largest category.",
                "amount_minor": 12_345,
                "currency": "INR",
                "evidence_ids": [evidence],
                "assumptions": ["Spending pattern continues"],
                "confidence_bps": 7000,
            }
        ]
    }
    grounded = {
        "recommendations": [
            {
                "title": f"Cut {top['category']} spending by 20%",
                "explanation": "It is the largest card category; a 20% cut saves this monthly.",
                "amount_minor": top["monthly_saving_minor"],
                "currency": "INR",
                "evidence_ids": [evidence, "spending_summary"],
                "assumptions": ["Spending pattern continues"],
                "confidence_bps": 8000,
            }
        ]
    }
    transport = FakeAgentTransport(
        [
            {
                "findings": [
                    {
                        "finding": "Food delivery is the largest card category.",
                        "evidence_ids": [evidence],
                        "limitation": "One statement period only.",
                    }
                ],
                "summary": "Spending concentrates in delivery.",
            },
            invented,
            {"issues": ["Amount is not in the evidence"], "revision_instructions": "Use 20000."},
            grounded,
        ]
    )
    async with SessionFactory() as session:
        execution = await execute_advice(
            session,
            tenant_id=UUID(tenant),
            user_id=UUID(user),
            forecast_id=None,
            snapshot_id=UUID(body["id"]),
            scenario_id=None,
            question="Where can I reduce my credit-card spending?",
            mesh=MeshClient(TEST_SETTINGS, transport),
        )
    run = await client.get(f"/api/v1/agent-runs/{execution.id}", headers=headers)
    assert run.status_code == 200, run.text
    payload = run.json()
    assert payload["forecast_id"] is None
    assert payload["intent"] == "spending_advice"
    assert payload["verification_status"] == "accept"
    assert payload["revision_attempts"] == 1
    nodes = [event["node"] for event in payload["events"]]
    assert nodes[-6:] == [
        "behavior_analyst",
        "financial_advisor",
        "verification",
        "critic",
        "revision",
        "verification",
    ]
    assert payload["recommendations"][0]["amount_minor"] == 20_000

    both = await client.post(
        "/api/v1/agent-runs",
        headers=headers,
        json={"forecast_id": body["id"], "snapshot_id": body["id"], "question": "Help me"},
    )
    assert both.status_code == 422
    stranger_token, stranger_tenant, _ = await _identity(
        client, "card-stranger@example.com", "Stranger"
    )
    foreign = await client.post(
        "/api/v1/agent-runs",
        headers={"Authorization": f"Bearer {stranger_token}", "X-Tenant-ID": stranger_tenant},
        json={"snapshot_id": body["id"], "question": "Where can I cut spending?"},
    )
    assert foreign.status_code == 404


async def test_bank_forecast_advice_also_receives_spending_evidence(client: AsyncClient) -> None:
    token, tenant, user = await _identity(client, "bank-advice@example.com", "Bank Advice")
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant}
    account = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Bank", "currency": "INR", "external_reference": "bank-advice"},
    )
    account_id = account.json()["id"]
    bank_csv = b"""Date,Narration,Withdrawal Amt.,Deposit Amt.,Closing Balance
01/09/2026,SALARY ACME,,"50,000.00","60,000.00"
05/09/2026,GREEN HOMES RENT,"20,000.00",,"40,000.00"
20/09/2026,FRESH MART GROCERIES,"5,000.00",,"35,000.00"
"""
    await client.post(
        f"/api/v1/accounts/{account_id}/transaction-uploads",
        headers=headers,
        data={"mapping": json.dumps(UI_MAPPING)},
        files={"file": ("bank.csv", bank_csv, "text/csv")},
    )
    snapshot = (
        await client.post(
            "/api/v1/analytics/snapshots",
            headers=headers,
            json={"account_id": account_id, "as_of": "2026-09-20"},
        )
    ).json()
    assert snapshot["spending"]["savings_rate_bps"] == 5_000
    forecast = (
        await client.post(
            "/api/v1/analytics/forecasts",
            headers=headers,
            json={"snapshot_id": snapshot["id"], "horizon_days": 30},
        )
    ).json()
    saving = snapshot["spending"]["combined_monthly_saving_minor"]
    transport = FakeAgentTransport(
        [
            {
                "findings": [
                    {
                        "finding": "Rent and groceries are the main outflows.",
                        "evidence_ids": ["spending_summary"],
                        "limitation": "One month of data.",
                    }
                ],
                "summary": "Half of income is retained.",
            },
            {
                "recommendations": [
                    {
                        "title": "Trim the top categories to save more",
                        "explanation": "A 20% cut in the largest categories adds this monthly.",
                        "amount_minor": saving,
                        "currency": "INR",
                        "evidence_ids": ["spending_summary", forecast["id"]],
                        "assumptions": ["Income continues"],
                        "confidence_bps": 7500,
                    }
                ]
            },
        ]
    )
    async with SessionFactory() as session:
        execution = await execute_advice(
            session,
            tenant_id=UUID(tenant),
            user_id=UUID(user),
            forecast_id=UUID(forecast["id"]),
            scenario_id=None,
            question="How can I reduce spending and save more each month?",
            mesh=MeshClient(TEST_SETTINGS, transport),
        )
    run = (await client.get(f"/api/v1/agent-runs/{execution.id}", headers=headers)).json()
    assert run["intent"] == "forecast_advice"
    assert run["verification_status"] == "accept"
    assert run["recommendations"][0]["amount_minor"] == saving
