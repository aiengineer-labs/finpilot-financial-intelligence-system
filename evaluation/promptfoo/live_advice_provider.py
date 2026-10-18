"""Promptfoo target for the live FinPilot advisor: each attack is asked as the advice question.

The request goes through the real API, so every layer applies: input policy, NeMo and Presidio,
the Mesh specialists, the output rail, and the deterministic verifier. The workspace holds only
the versioned synthetic household dataset. Standard library only, so it runs in the pinned
Promptfoo container.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

API = os.environ.get("FINPILOT_API_URL", "http://api:8000").rstrip("/")
ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evaluation" / "datasets" / "synthetic_household_v1.csv"
STATE = Path(__file__).resolve().parent / ".promptfoo" / "live-advice-state.json"
MAPPING = {
    "date": "Date", "date_format": "%d/%m/%Y", "debit": "Debit", "credit": "Credit",
    "merchant": "Merchant", "description": "Description", "transaction_id": "Transaction ID",
    "currency": "Currency", "balance": "Balance",
}
AS_OF = "2026-10-15"
TIMEOUT_SECONDS = 230


def _call(
    method: str, path: str, *, token: str | None = None, tenant: str | None = None,
    body: bytes | None = None, content_type: str = "application/json",
) -> tuple[int, Any]:
    headers = {"Content-Type": content_type}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if tenant:
        headers["X-Tenant-ID"] = tenant
    request = urllib.request.Request(API + path, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            return error.code, json.loads(raw)
        except json.JSONDecodeError:
            return error.code, raw.decode("utf-8", "replace")


def _expect(status: int, payload: Any, wanted: int, step: str) -> Any:
    if status != wanted:
        raise RuntimeError(f"{step} returned HTTP {status}: {payload}")
    return payload


def _multipart(fields: dict[str, str], filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        for name, value in fields.items()
    ]
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: text/csv\r\n\r\n".encode() + content + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _bootstrap() -> dict[str, str]:
    """A fresh synthetic workspace with an imported statement and a 30-day forecast."""

    token = _expect(*_call("POST", "/api/v1/workspace/bootstrap"), 201, "bootstrap")["access_token"]
    me = _expect(*_call("GET", "/api/v1/auth/me", token=token), 200, "auth/me")
    tenant = me["tenants"][0]["id"]
    account = _expect(
        *_call(
            "POST", "/api/v1/accounts", token=token, tenant=tenant,
            body=json.dumps(
                {"name": "Red team", "currency": "INR", "external_reference": "redteam"}
            ).encode(),
        ),
        201, "create account",
    )
    body, content_type = _multipart(
        {"mapping": json.dumps(MAPPING)}, DATASET.name, DATASET.read_bytes()
    )
    _expect(
        *_call(
            "POST", f"/api/v1/accounts/{account['id']}/transaction-uploads",
            token=token, tenant=tenant, body=body, content_type=content_type,
        ),
        200, "upload",
    )
    snapshot = _expect(
        *_call(
            "POST", "/api/v1/analytics/snapshots", token=token, tenant=tenant,
            body=json.dumps({"account_id": account["id"], "as_of": AS_OF}).encode(),
        ),
        201, "snapshot",
    )
    forecast = _expect(
        *_call(
            "POST", "/api/v1/analytics/forecasts", token=token, tenant=tenant,
            body=json.dumps({"snapshot_id": snapshot["id"], "horizon_days": 30}).encode(),
        ),
        201, "forecast",
    )
    state = {"token": token, "tenant": tenant, "forecast_id": forecast["id"]}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state))
    return state


def _state() -> dict[str, str]:
    try:
        return dict(json.loads(STATE.read_text()))
    except (OSError, ValueError):
        return _bootstrap()


def _ask(state: dict[str, str], question: str) -> tuple[int, Any]:
    return _call(
        "POST", "/api/v1/agent-runs", token=state["token"], tenant=state["tenant"],
        body=json.dumps({"forecast_id": state["forecast_id"], "question": question}).encode(),
    )


def _visible_text(run: dict[str, Any]) -> str:
    """Everything a user can read about the run in Analyze or the Console Advisor view."""

    lines = [f"Verification: {run['verification_status']}.", run["final_response"]]
    for item in run["recommendations"]:
        lines.append(f"Option {item['rank']} ({item['verification_status']}): {item['title']}")
        lines.append(item["explanation"])
        lines.extend(f"Assumption: {text}" for text in item["assumptions"])
    return "\n".join(line for line in lines if line)


def call_api(prompt: str, options: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    del options, context
    state = _state()
    status, payload = _ask(state, prompt)
    if status == 401:  # the access token expired during a long run
        state = _bootstrap()
        status, payload = _ask(state, prompt)
    detail = payload.get("detail") if isinstance(payload, dict) else payload
    if status == 201:
        mesh_calls = sum(1 for event in payload["events"] if event.get("model_id"))
        return {
            "output": _visible_text(payload),
            "metadata": {
                "layer": "model_answered",
                "verification": payload["verification_status"],
                "mesh_calls": mesh_calls,
            },
            "tokenUsage": {
                "prompt": payload["total_input_tokens"],
                "completion": payload["total_output_tokens"],
                "total": payload["total_input_tokens"] + payload["total_output_tokens"],
            },
        }
    if status == 422:
        text = json.dumps(detail) if not isinstance(detail, str) else detail
        layer = (
            "input_policy" if "prompt-injection policy" in text
            else "nemo_input" if "programmable guardrails" in text
            else "request_validation"
        )
        return {"output": f"Request refused by FinPilot ({layer}).", "metadata": {"layer": layer}}
    if status == 502 and isinstance(detail, str) and "output guardrail" in detail:
        return {
            "output": "The run failed safely: the output guardrail blocked the model's text.",
            "metadata": {"layer": "output_guardrail"},
        }
    # Provider or infrastructure failures are not security results; report them as errors.
    return {"error": f"HTTP {status}: {detail}"}
