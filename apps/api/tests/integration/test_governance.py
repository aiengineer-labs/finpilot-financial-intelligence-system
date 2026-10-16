from uuid import UUID

from httpx import AsyncClient

from app.database.models import Membership, TenantRole
from app.database.session import SessionFactory


async def _identity(client: AsyncClient, email: str, household: str) -> tuple[str, str, str]:
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
    return token, me.json()["tenants"][0]["id"], me.json()["id"]


def _headers(token: str, tenant_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant_id}


async def test_governance_registry_release_gate_and_tenant_isolation(
    client: AsyncClient,
) -> None:
    owner_token, tenant_id, _ = await _identity(
        client, "governance-owner@example.com", "Governance Household"
    )
    reviewer_token, _, reviewer_id = await _identity(
        client, "governance-reviewer@example.com", "Reviewer Household"
    )
    outsider_token, outsider_tenant, _ = await _identity(
        client, "governance-outsider@example.com", "Outsider Household"
    )
    async with SessionFactory() as session:
        session.add(
            Membership(
                user_id=UUID(reviewer_id),
                tenant_id=UUID(tenant_id),
                role=TenantRole.REVIEWER,
            )
        )
        await session.commit()

    owner_headers = _headers(owner_token, tenant_id)
    reviewer_headers = _headers(reviewer_token, tenant_id)
    outsider_headers = _headers(outsider_token, tenant_id)

    summary = await client.get("/api/v1/governance/summary", headers=owner_headers)
    assert summary.status_code == 200, summary.text
    assert summary.json()["artifacts"] == 10
    assert summary.json()["risks"] == 13
    assert summary.json()["evaluation_failures"] == 1
    assert summary.json()["release_ready"] is False
    assert "evaluation:mesh-model-redteam:not_run" in summary.json()["release_blockers"]

    risks = await client.get("/api/v1/governance/risks", headers=owner_headers)
    assert risks.status_code == 200
    assert {item["risk_id"] for item in risks.json()} == {
        f"R-{index:03d}" for index in range(1, 14)
    }

    proposed = await client.post(
        "/api/v1/governance/artifacts",
        headers=owner_headers,
        json={
            "artifact_type": "tool_policy",
            "name": "static-agent-allowlist",
            "version": "malicious-draft-v2",
            "configuration": {"money_movement": True, "permissions": ["all"]},
        },
    )
    assert proposed.status_code == 201, proposed.text
    artifact_id = proposed.json()["id"]
    assert proposed.json()["status"] == "draft"

    self_approval = await client.post(
        f"/api/v1/governance/artifacts/{artifact_id}/approve",
        headers=owner_headers,
        json={"reason": "I created this change and should not self approve it."},
    )
    assert self_approval.status_code == 403

    gated_approval = await client.post(
        f"/api/v1/governance/artifacts/{artifact_id}/approve",
        headers=reviewer_headers,
        json={"reason": "Independent review cannot pass a failing release gate."},
    )
    assert gated_approval.status_code == 409
    assert "mesh-model-redteam" in gated_approval.text

    artifacts = await client.get("/api/v1/governance/artifacts", headers=reviewer_headers)
    assert artifacts.status_code == 200
    active_tool_policy = [
        item
        for item in artifacts.json()
        if item["artifact_type"] == "tool_policy" and item["status"] == "approved"
    ]
    assert len(active_tool_policy) == 1
    assert active_tool_policy[0]["configuration"]["money_movement"] is False

    cross_tenant = await client.get("/api/v1/governance/artifacts", headers=outsider_headers)
    assert cross_tenant.status_code == 404
    own_outsider = await client.get(
        "/api/v1/governance/summary", headers=_headers(outsider_token, outsider_tenant)
    )
    assert own_outsider.status_code == 200


async def test_review_queue_requires_independent_authorized_decision(client: AsyncClient) -> None:
    owner_token, tenant_id, _ = await _identity(
        client, "review-owner@example.com", "Review Household"
    )
    reviewer_token, _, reviewer_id = await _identity(
        client, "review-reviewer@example.com", "Second Household"
    )
    member_token, _, member_id = await _identity(
        client, "review-member@example.com", "Member Household"
    )
    async with SessionFactory() as session:
        session.add_all(
            [
                Membership(
                    user_id=UUID(reviewer_id),
                    tenant_id=UUID(tenant_id),
                    role=TenantRole.REVIEWER,
                ),
                Membership(
                    user_id=UUID(member_id),
                    tenant_id=UUID(tenant_id),
                    role=TenantRole.MEMBER,
                ),
            ]
        )
        await session.commit()

    owner_headers = _headers(owner_token, tenant_id)
    reviewer_headers = _headers(reviewer_token, tenant_id)
    member_headers = _headers(member_token, tenant_id)
    requested = await client.post(
        "/api/v1/governance/reviews",
        headers=owner_headers,
        json={
            "reason": "I contest the assumptions behind this recommendation.",
            "risk_level": "high",
            "evidence_ids": ["synthetic:user-contest"],
        },
    )
    assert requested.status_code == 201, requested.text
    case_id = requested.json()["id"]

    own_decision = await client.post(
        f"/api/v1/governance/reviews/{case_id}/decisions",
        headers=owner_headers,
        json={"outcome": "approve", "reason": "A requester may not approve their own case."},
    )
    assert own_decision.status_code == 403

    member_decision = await client.post(
        f"/api/v1/governance/reviews/{case_id}/decisions",
        headers=member_headers,
        json={"outcome": "reject", "reason": "A member is not an authorized reviewer."},
    )
    assert member_decision.status_code == 403

    reviewed = await client.post(
        f"/api/v1/governance/reviews/{case_id}/decisions",
        headers=reviewer_headers,
        json={
            "outcome": "request_revision",
            "reason": "The evidence is valid, but the explanation needs a bounded revision.",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["source_evidence"] == ["synthetic:user-contest"]
    assert reviewed.json()["artifact_lineage"]["financial_verifier"]

    cases = await client.get("/api/v1/governance/reviews", headers=owner_headers)
    assert cases.json()[0]["status"] == "resolved"

    demo = await client.post("/api/v1/governance/demo-review", headers=owner_headers)
    assert demo.status_code == 201
    assert demo.json()["source"] == "synthetic_demo"
    assert demo.json()["requested_by_user_id"] is None
    demo_decision = await client.post(
        f"/api/v1/governance/reviews/{demo.json()['id']}/decisions",
        headers=owner_headers,
        json={
            "outcome": "reject",
            "reason": "Guaranteed-return language remains forbidden after human review.",
        },
    )
    assert demo_decision.status_code == 200
