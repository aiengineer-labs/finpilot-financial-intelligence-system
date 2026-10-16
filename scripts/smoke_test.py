"""End-to-end smoke test for a running FinPilot stack (Docker Compose or dev servers).

Exercises the deterministic path only — no Mesh inference — using the versioned
synthetic household statement. Each run registers fresh synthetic households, so it
is safe to repeat. Run from the repository root:

    make smoke
"""

from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
API_BASE = os.getenv("SMOKE_API_BASE", "http://localhost:8000").rstrip("/")
WEB_BASE = os.getenv("SMOKE_WEB_BASE", "http://localhost:3000").rstrip("/")
FIXTURE = ROOT / "evaluation" / "datasets" / "synthetic_household_v1.csv"
SAMPLE_PATH = "/samples/finpilot-synthetic-household-v1.csv"
MAPPING = {
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

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(
        f"  [{'PASS' if condition else 'FAIL'}] {label}" + (f" — {detail}" if detail != "" else "")
    )
    if not condition:
        failures.append(label)


def register(client: httpx.Client, household: str) -> tuple[dict[str, str], str]:
    email = f"smoke-{secrets.token_hex(6)}@example.com"
    password = f"smoke-{secrets.token_hex(12)}"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "household_name": household},
    )
    response.raise_for_status()
    auth = {"Authorization": f"Bearer {response.json()['access_token']}"}
    tenant = client.get("/api/v1/auth/me", headers=auth).json()["tenants"][0]["id"]
    return {**auth, "X-Tenant-ID": tenant}, email


def upload(client: httpx.Client, headers: dict[str, str], account_id: str) -> dict:
    with FIXTURE.open("rb") as source:
        response = client.post(
            f"/api/v1/accounts/{account_id}/transaction-uploads",
            headers=headers,
            data={"mapping": json.dumps(MAPPING)},
            files={"file": (FIXTURE.name, source, "text/csv")},
        )
    response.raise_for_status()
    return response.json()


def main() -> int:
    print(f"FinPilot smoke test · API {API_BASE} · web {WEB_BASE}")
    with httpx.Client(base_url=API_BASE, timeout=60) as client:
        print("Service health")
        health = client.get("/health")
        check(
            "API /health",
            health.status_code == 200 and health.json() == {"status": "ok"},
            health.text,
        )
        ready = client.get("/ready")
        check("API /ready", ready.status_code == 200, ready.text)
        try:
            page = httpx.get(WEB_BASE, timeout=30)
            check("web console responds", page.status_code == 200, page.status_code)
            sample = httpx.get(f"{WEB_BASE}{SAMPLE_PATH}", timeout=30)
            check(
                "web serves synthetic sample CSV",
                sample.status_code == 200 and sample.content == FIXTURE.read_bytes(),
            )
        except httpx.HTTPError as exc:
            check("web console responds", False, exc)

        print("Authentication and ingestion")
        headers, email = register(client, "Smoke test household")
        repeat = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "another-long-password", "household_name": "Again"},
        )
        check("duplicate registration is 409", repeat.status_code == 409, repeat.status_code)
        account = client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"name": "Smoke account", "currency": "INR", "external_reference": "smoke-v1"},
        ).json()
        first = upload(client, headers, account["id"])
        check(
            "import 139 accepted / 1 duplicate / 1 rejected",
            (first["accepted_rows"], first["duplicate_rows"], first["rejected_rows"])
            == (139, 1, 1),
            f"{first['accepted_rows']}/{first['duplicate_rows']}/{first['rejected_rows']}",
        )
        replay = upload(client, headers, account["id"])
        check(
            "re-upload is an idempotent replay",
            replay["replayed"] is True and replay["id"] == first["id"],
        )
        ledger = client.get("/api/v1/transactions?limit=200", headers=headers).json()
        check("ledger holds 139 rows", ledger["total"] == 139, ledger["total"])

        print("Deterministic analytics")
        snapshot = client.post(
            "/api/v1/analytics/snapshots",
            headers=headers,
            json={"account_id": account["id"], "as_of": "2026-10-15"},
        ).json()
        check(
            "opening balance ₹3,37,554.07",
            snapshot["opening_balance_minor"] == 33_755_407,
            snapshot["opening_balance_minor"],
        )
        check(
            "11 recurring patterns",
            len(snapshot["recurring_patterns"]) == 11,
            len(snapshot["recurring_patterns"]),
        )
        check(
            "3 robust anomalies",
            len(snapshot["anomaly_results"]) == 3,
            len(snapshot["anomaly_results"]),
        )
        forecast = client.post(
            "/api/v1/analytics/forecasts",
            headers=headers,
            json={"snapshot_id": snapshot["id"], "horizon_days": 30},
        ).json()
        check(
            "30-day forecast has 30 daily points",
            len(forecast["points"]) == 30,
            len(forecast["points"]),
        )
        outcomes = {}
        for label, amount in (("laptop", 7_500_000), ("car", 35_000_000)):
            outcomes[label] = client.post(
                "/api/v1/analytics/scenarios",
                headers=headers,
                json={
                    "forecast_id": forecast["id"],
                    "name": label,
                    "shocks": [{"day": "2026-10-25", "amount_minor": -amount, "label": label}],
                },
            ).json()
        check(
            "₹75,000 what-if has no shortfall", outcomes["laptop"]["first_shortfall_date"] is None
        )
        check(
            "₹3,50,000 what-if falls short on 2026-10-25",
            outcomes["car"]["first_shortfall_date"] == "2026-10-25",
            outcomes["car"]["first_shortfall_date"],
        )

        print("Tenant isolation")
        other, _ = register(client, "Smoke outsider")
        crossed = client.get(
            "/api/v1/accounts", headers={**other, "X-Tenant-ID": headers["X-Tenant-ID"]}
        )
        check(
            "another user cannot read this tenant", crossed.status_code == 404, crossed.status_code
        )
        own = client.get("/api/v1/transactions", headers=other).json()
        check("another tenant sees an empty ledger", own["total"] == 0, own["total"])

    print(
        f"\n{'All checks passed' if not failures else f'{len(failures)} check(s) failed: ' + ', '.join(failures)}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
