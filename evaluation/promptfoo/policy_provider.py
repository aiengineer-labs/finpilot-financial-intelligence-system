"""Promptfoo provider for FinPilot's deterministic untrusted-text boundary."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

API_ROOT = Path(__file__).resolve().parents[2] / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.security.input_policy import assess_untrusted_text


def call_api(prompt: str, options: dict[str, Any], context: dict[str, Any]) -> dict[str, str]:
    """Return the same allow/block decision used at FinPilot's production boundary."""
    del options, context
    return {"output": assess_untrusted_text(prompt).decision.value}
