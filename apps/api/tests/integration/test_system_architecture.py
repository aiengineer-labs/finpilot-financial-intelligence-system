from httpx import AsyncClient


async def test_architecture_manifest_requires_an_isolated_workspace(client: AsyncClient) -> None:
    unauthorized = await client.get("/api/v1/system/architecture")
    assert unauthorized.status_code == 401

    bootstrapped = await client.post("/api/v1/workspace/bootstrap")
    assert bootstrapped.status_code == 201
    token = bootstrapped.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    tenant_id = me.json()["tenants"][0]["id"]

    response = await client.get(
        "/api/v1/system/architecture",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant_id},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["graph_version"] == "advice-graph-v2"
    assert {node["id"] for node in payload["nodes"]} >= {
        "upload",
        "semantic_categorizer",
        "supervisor",
        "behavior_analyst",
        "financial_advisor",
        "critic",
        "verification",
        "audit",
    }
    assert {edge["branch"] for edge in payload["edges"]} >= {"normal", "revise", "mesh"}
