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
