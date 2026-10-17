from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from nemoguardrails import LLMRails, RailsConfig  # type: ignore[import-untyped]
from nemoguardrails.rails.llm.options import RailStatus  # type: ignore[import-untyped]

from app.security.pii import PiiMinimizer

NEMO_POLICY_VERSION = "finpilot-nemo-v2"
PII_POLICY_VERSION = "finpilot-presidio-v1"

# Audit labels for the output patterns in nemo/config.yml, in the same order.
OUTPUT_RULE_LABELS = ("credential_token", "secret_disclosure", "certainty_language")


class GuardrailViolation(ValueError):
    def __init__(self, message: str, rule: str | None = None) -> None:
        super().__init__(message)
        self.rule = rule


@dataclass(frozen=True)
class PreparedModelInput:
    question: str
    context: dict[str, Any]
    events: list[dict[str, Any]]


class ModelGuardrails:
    """NeMo execution rails plus Presidio minimization at the Mesh boundary."""

    def __init__(self) -> None:
        config = RailsConfig.from_path(str(Path(__file__).with_name("nemo")))
        self._rails = LLMRails(config)
        self._pii = PiiMinimizer()
        patterns = config.rails.config.regex_detection.output.patterns
        labels = list(OUTPUT_RULE_LABELS)
        labels += [f"output_pattern_{n}" for n in range(len(labels) + 1, len(patterns) + 1)]
        self._output_rules = [
            (label, re.compile(pattern)) for label, pattern in zip(labels, patterns, strict=False)
        ]

    def _blocked_output_rule(self, text: str) -> str:
        """Name the rule that fired so the audit trail can say why, without storing model text."""
        matched = (label for label, pattern in self._output_rules if pattern.search(text))
        return next(matched, "unknown")

    async def prepare_input(self, question: str, context: dict[str, Any]) -> PreparedModelInput:
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
            rule = self._blocked_output_rule(text)
            raise GuardrailViolation(
                f"output blocked by NeMo rail: {result.rail or 'unknown'} ({rule})", rule=rule
            )
        return self._pii.minimize(text).text


@lru_cache(maxsize=1)
def get_model_guardrails() -> ModelGuardrails:
    return ModelGuardrails()
