import csv
from pathlib import Path

import pytest

from app.security.input_policy import InputDecision, assess_untrusted_text

DATASET = (
    Path(__file__).resolve().parents[4] / "evaluation" / "security" / "prompt_injection_cases.csv"
)


def load_cases(expected: str) -> tuple[str, ...]:
    with DATASET.open(encoding="utf-8", newline="") as handle:
        return tuple(
            row["payload"]
            for row in csv.DictReader(handle)
            if row["__expected"] == f"equals:{expected}"
        )


ATTACK_CASES = load_cases("block")
BENIGN_CASES = load_cases("allow")


@pytest.mark.parametrize("payload", ATTACK_CASES)
def test_versioned_prompt_injection_matrix_is_blocked(payload: str) -> None:
    assert assess_untrusted_text(payload).decision is InputDecision.BLOCK


@pytest.mark.parametrize("payload", BENIGN_CASES)
def test_legitimate_financial_text_is_allowed(payload: str) -> None:
    assert assess_untrusted_text(payload).decision is InputDecision.ALLOW


def test_matrix_contains_more_than_one_hundred_cases() -> None:
    assert len(ATTACK_CASES) >= 100
    assert len(BENIGN_CASES) >= 10
