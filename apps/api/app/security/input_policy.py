import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum


class InputDecision(StrEnum):
    ALLOW = "allow"
    FLAG = "flag"
    BLOCK = "block"


@dataclass(frozen=True)
class InputAssessment:
    decision: InputDecision
    reasons: tuple[str, ...]


_BLOCK_PATTERNS = (
    re.compile(r"\b(reveal|print|show)\b.{0,32}\b(api[-_ ]?key|secret|system prompt)\b", re.I),
    re.compile(
        r"\b(ignore|override|disable)\b.{0,40}\b(policy|instructions?|verification)\b", re.I
    ),
    re.compile(r"\b(execute|run)\b.{0,20}\b(shell|sql|python|command)\b", re.I),
)


def assess_untrusted_text(value: str) -> InputAssessment:
    normalized = unicodedata.normalize("NFKC", value)
    reasons = tuple(pattern.pattern for pattern in _BLOCK_PATTERNS if pattern.search(normalized))
    return InputAssessment(InputDecision.BLOCK if reasons else InputDecision.ALLOW, reasons)


def neutralize_csv_formula(value: str) -> str:
    """Make exported cells inert without changing persisted ledger source values."""
    return f"'{value}" if value.lstrip().startswith(("=", "+", "-", "@")) else value
