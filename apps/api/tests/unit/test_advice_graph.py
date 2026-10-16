import json
from typing import Any

from pydantic import SecretStr

from app.agents.specialists import AdvisorOutput
from app.core.settings import Settings
from app.database.models import VerificationStatus
from app.graphs.advice import AdviceWorkflow, verify_advice
from app.integrations.mesh import MeshClient


class SequenceTransport:
    def __init__(self, contents: list[dict[str, Any]]) -> None:
        self.contents = contents
        self.calls = 0

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        assert path == "/chat/completions"
        content = self.contents[self.calls]
        self.calls += 1
        return {
            "id": f"fake-{self.calls}",
            "model": "mesh-test-model",
            "choices": [{"message": {"content": json.dumps(content)}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        }


def _settings() -> Settings:
    return Settings(
        session_secret=SecretStr("test-only-secret-with-at-least-thirty-two-chars"),
        database_url="sqlite+aiosqlite://",
        mesh_model="mesh-test-model",
    )


def _context() -> dict[str, Any]:
    return {
        "currency": "INR",
        "evidence_ids": ["snapshot-1", "forecast-1", "scenario-1"],
        "allowed_amount_minor": [550_000, 7_500_000],
        "snapshot": {"id": "snapshot-1", "opening_balance_minor": 11_050_000},
        "forecast": {"id": "forecast-1", "minimum_balance_minor": 8_050_000},
        "scenario": {"id": "scenario-1", "minimum_balance_minor": 550_000},
        "scenario_id": "scenario-1",
    }


def _analysis() -> dict[str, Any]:
    return {
        "findings": [
            {
                "finding": "The scenario remains above zero.",
                "evidence_ids": ["scenario-1"],
                "limitation": "Future unobserved costs are excluded.",
            }
        ],
        "summary": "The deterministic scenario has no projected shortfall.",
    }


def _recommendation(amount: int) -> dict[str, Any]:
    return {
        "recommendations": [
            {
                "title": "Preserve a cash buffer",
                "explanation": "Compare the scenario minimum before purchasing.",
                "amount_minor": amount,
                "currency": "INR",
                "evidence_ids": ["scenario-1"],
                "assumptions": ["No unobserved charges"],
                "confidence_bps": 8000,
            }
        ]
    }


async def test_invalid_amount_is_criticized_revised_and_accepted() -> None:
    transport = SequenceTransport(
        [
            _analysis(),
            _recommendation(123),
            {
                "issues": ["The amount is not in deterministic evidence."],
                "revision_instructions": "Use the scenario purchase amount exactly.",
            },
            _recommendation(7_500_000),
        ]
    )
    state = await AdviceWorkflow(MeshClient(_settings(), transport)).run(
        question="Can I afford the laptop?", context=_context()
    )
    assert state["verification_status"] == VerificationStatus.ACCEPT.value
    assert state["revision_attempts"] == 1
    assert transport.calls == 4
    assert [event["node"] for event in state["events"]] == [
        "supervisor",
        "behavior_analyst",
        "financial_advisor",
        "verification",
        "critic",
        "revision",
        "verification",
    ]
    assert "Verified options" in state["final_response"]


async def test_repeated_unsupported_advice_is_rejected() -> None:
    transport = SequenceTransport(
        [
            _analysis(),
            _recommendation(123),
            {
                "issues": ["Unsupported amount."],
                "revision_instructions": "Use only an allowed value.",
            },
            _recommendation(456),
        ]
    )
    state = await AdviceWorkflow(MeshClient(_settings(), transport)).run(
        question="Can I afford the laptop?", context=_context()
    )
    assert state["verification_status"] == VerificationStatus.REJECT.value
    assert "withheld" in state["final_response"]


def test_verifier_rejects_wrong_currency_and_prohibited_certainty() -> None:
    draft = AdvisorOutput.model_validate(
        {
            "recommendations": [
                {
                    "title": "Guaranteed result",
                    "explanation": "This is risk-free.",
                    "amount_minor": 550_000,
                    "currency": "USD",
                    "evidence_ids": ["scenario-1"],
                    "assumptions": [],
                    "confidence_bps": 9000,
                }
            ]
        }
    )
    status, reasons = verify_advice(draft, _context(), revision_attempts=1)
    assert status is VerificationStatus.REJECT
    assert "wrong currency" in " ".join(reasons)
    assert "prohibited certainty" in " ".join(reasons)
