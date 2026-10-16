from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from presidio_analyzer import Pattern, PatternRecognizer, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


@dataclass(frozen=True)
class MinimizedText:
    text: str
    entity_types: tuple[str, ...]
    detection_count: int


def _recognizer(entity: str, name: str, regex: str, score: float = 0.8) -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity=entity,
        name=name,
        patterns=[Pattern(name=name, regex=regex, score=score)],
    )


class PiiMinimizer:
    """Presidio-backed minimization for free text sent to model inference."""

    def __init__(self) -> None:
        # Pattern-only recognizers avoid runtime model downloads and make cold starts reproducible.
        self._recognizers = (
            _recognizer("EMAIL_ADDRESS", "email", r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
            _recognizer("IN_PHONE_NUMBER", "india-phone", r"(?<!\d)(?:\+91[- ]?)?[6-9]\d{9}(?!\d)"),
            _recognizer("IN_PAN", "india-pan", r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", 0.9),
            _recognizer(
                "IN_AADHAAR",
                "india-aadhaar-context",
                r"\b(?:aadhaar|aadhar)[\s:#-]*\d{4}[ -]?\d{4}[ -]?\d{4}\b",
                0.95,
            ),
            _recognizer(
                "BANK_ACCOUNT",
                "bank-account-context",
                r"\b(?:account|acct)[\s:#-]*\d{9,18}\b",
                0.9,
            ),
        )
        self._anonymizer = AnonymizerEngine()  # type: ignore[no-untyped-call]

    def minimize(self, value: str) -> MinimizedText:
        results: list[RecognizerResult] = []
        for recognizer in self._recognizers:
            results.extend(recognizer.analyze(value, [recognizer.supported_entities[0]]))
        if not results:
            return MinimizedText(value, (), 0)
        operators = {
            entity: OperatorConfig("replace", {"new_value": f"<{entity}>"})
            for entity in {result.entity_type for result in results}
        }
        anonymized = self._anonymizer.anonymize(
            text=value,
            analyzer_results=results,  # type: ignore[arg-type]
            operators=operators,
        )
        return MinimizedText(
            anonymized.text,
            tuple(sorted({result.entity_type for result in results})),
            len(results),
        )

    def minimize_structure(self, value: Any) -> tuple[Any, tuple[str, ...], int]:
        if isinstance(value, str):
            result = self.minimize(value)
            return result.text, result.entity_types, result.detection_count
        if isinstance(value, list):
            minimized_items: list[Any] = []
            entity_types: set[str] = set()
            count = 0
            for item in value:
                minimized, entities, detected = self.minimize_structure(item)
                minimized_items.append(minimized)
                entity_types.update(entities)
                count += detected
            return minimized_items, tuple(sorted(entity_types)), count
        if isinstance(value, dict):
            minimized_dict: dict[str, Any] = {}
            entity_types = set()
            count = 0
            for key, item in value.items():
                minimized, entities, detected = self.minimize_structure(item)
                minimized_dict[key] = minimized
                entity_types.update(entities)
                count += detected
            return minimized_dict, tuple(sorted(entity_types)), count
        return value, (), 0
