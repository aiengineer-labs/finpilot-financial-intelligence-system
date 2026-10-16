from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
API_BASE = os.getenv("DEMO_API_BASE", "http://localhost:8000").rstrip("/")
DATASETS = {
    # name: (fixture, account external reference, account name, default demo email)
    "household": (
        "synthetic_household_v1.csv",
        "synthetic-household-v1",
        "Synthetic household account",
        "finpilot-household-demo@example.com",
    ),
    "golden": (
        "phase2_golden.csv",
        "phase2-golden",
        "Synthetic primary account",
        "finpilot-synthetic-demo@example.com",
    ),
}
DATASET = os.getenv("DEMO_DATASET", "household")
if DATASET not in DATASETS:
    raise SystemExit(f"DEMO_DATASET must be one of: {', '.join(DATASETS)}")
FIXTURE, EXTERNAL_REFERENCE, ACCOUNT_NAME, DEFAULT_EMAIL = DATASETS[DATASET]
EMAIL = os.getenv("DEMO_EMAIL", DEFAULT_EMAIL)
PASSWORD = os.getenv("DEMO_PASSWORD")
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


def main() -> None:
    if not PASSWORD or len(PASSWORD) < 12:
        raise SystemExit(
            "Set DEMO_PASSWORD to a synthetic password of at least 12 characters."
        )
    with httpx.Client(base_url=API_BASE, timeout=30) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": EMAIL,
                "password": PASSWORD,
                "household_name": "FinPilot Demo",
            },
        )
        if response.status_code == 409:
            response = client.post(
                "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
            )
        response.raise_for_status()
        token = response.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}
        identity = client.get("/api/v1/auth/me", headers=auth)
        identity.raise_for_status()
        tenant_id = identity.json()["tenants"][0]["id"]
        headers = {**auth, "X-Tenant-ID": tenant_id}

        accounts = client.get("/api/v1/accounts", headers=headers)
        accounts.raise_for_status()
        account = next(
            (
                item
                for item in accounts.json()
                if item["external_reference"] == EXTERNAL_REFERENCE
            ),
            None,
        )
        if account is None:
            created = client.post(
                "/api/v1/accounts",
                headers=headers,
                json={
                    "name": ACCOUNT_NAME,
                    "currency": "INR",
                    "external_reference": EXTERNAL_REFERENCE,
                },
            )
            created.raise_for_status()
            account = created.json()

        fixture = ROOT / "evaluation" / "datasets" / FIXTURE
        with fixture.open("rb") as source:
            uploaded = client.post(
                f"/api/v1/accounts/{account['id']}/transaction-uploads",
                headers=headers,
                data={"mapping": json.dumps(MAPPING)},
                files={"file": (fixture.name, source, "text/csv")},
            )
        uploaded.raise_for_status()
        client.put(
            "/api/v1/digests/preference",
            headers=headers,
            json={
                "enabled": True,
                "weekday": 0,
                "local_time": "09:00",
                "timezone": "Asia/Kolkata",
            },
        ).raise_for_status()
        result = uploaded.json()
        print(
            f"Seeded {DATASET} dataset into synthetic tenant "
            f"{tenant_id}: {result['accepted_rows']} accepted, "
            f"{result['duplicate_rows']} duplicate, {result['rejected_rows']} rejected, "
            f"replayed={result['replayed']}"
        )


if __name__ == "__main__":
    main()
