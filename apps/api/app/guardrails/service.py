from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from nemoguardrails import LLMRails, RailsConfig  # type: ignore[import-untyped]
from nemoguardrails.rails.llm.options import RailStatus  # type: ignore[import-untyped]

from app.security.pii import PiiMinimizer

NEMO_POLICY_VERSION = "finpilot-nemo-v1"
PII_POLICY_VERSION = "finpilot-presidio-v1"


class GuardrailViolation(ValueError):
    pass


@dataclass(frozen=True)
class PreparedModelInput:
    question: str
    context: dict[str, Any]
    events: list[dict[str, Any]]


class ModelGuardrails:
    """NeMo execution rails plus Presidio minimization at the Mesh boundary."""

    def __init__(self) -> None:
        config_path = Path(__file__).with_name("nemo")
        self._rails = LLMRails(RailsConfig.from_path(str(config_path)))
        self._pii = PiiMinimizer()

    async def prepare_input(
        self, question: str, context: dict[str, Any]
    ) -> PreparedModelInput:
        result = await self._rails.check_async([{"role": "user", "content": question}])
        if result.status is RailStatus.BLOCKED:
            raise GuardrailViolation(f"input blocked by NeMo rail: {result.rail or 'unknown'}")
        minimized_question = self._pii.minimize(question)
        minimized_context, context_entities, context_count = self._pii.minimize_structure(context)
        entity_types = tuple(sorted(set(minimized_question.entity_types) | set(context_entities)))
        detection_count = minimized_question.detection_count + context_count
        return PreparedModelInput(
            question=minimized_question.text,
            context=cast(dict[str, Any], minimized_context),
            events=[
                {
                    "node": "nemo_input",
                    "event_type": "guardrail",
                    "summary": "NeMo input rail passed",
                    "details": {"policy_version": NEMO_POLICY_VERSION},
                },
                {
                    "node": "presidio_minimization",
                    "event_type": "privacy",
                    "summary": f"Minimized {detection_count} sensitive text spans",
                    "details": {
                        "policy_version": PII_POLICY_VERSION,
                        "entity_types": list(entity_types),
                        "detection_count": detection_count,
                    },
                },
            ],
        )

    async def process_output(self, text: str) -> str:
        result = await self._rails.check_async(
            [
                {"role": "user", "content": "financial analysis request"},
                {"role": "assistant", "content": text},
            ]
        )
        if result.status is RailStatus.BLOCKED:
            raise GuardrailViolation(f"output blocked by NeMo rail: {result.rail or 'unknown'}")
        return self._pii.minimize(text).text


@lru_cache(maxsize=1)
def get_model_guardrails() -> ModelGuardrails:
    return ModelGuardrails()
