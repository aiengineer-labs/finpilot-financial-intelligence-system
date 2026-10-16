import base64
import binascii
import html
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import unquote


class InputDecision(StrEnum):
    ALLOW = "allow"
    FLAG = "flag"
    BLOCK = "block"


@dataclass(frozen=True)
class InputAssessment:
    decision: InputDecision
    reasons: tuple[str, ...]


_BLOCK_PATTERNS = (
    re.compile(
        r"\b(reveal|print|show|leak|exfiltrate|return)\b.{0,48}"
        r"\b(api[-_ ]?key|secret|system\s+prompt|credentials?|all\s+accounts?)\b",
        re.I,
    ),
    re.compile(
        r"\b(ignore|override|disable|bypass|forget|discard)\b.{0,56}"
        r"\b(policy|instructions?|verification|guardrails?|rules?|system)\b",
        re.I,
    ),
    re.compile(r"\b(execute|run)\b.{0,20}\b(shell|sql|python|command)\b", re.I),
    re.compile(
        r"\b(system|developer|assistant)\s*(message|prompt|override)?\s*[:=-]"
        r".{0,80}\b(ignore|reveal|execute|bypass)\b",
        re.I,
    ),
    re.compile(
        r"\b(tool|function)\s*(call|result)?\s*[:=-].{0,80}"
        r"\b(transfer|shell|sql|eval)\b",
        re.I,
    ),
)


_CONFUSABLES = str.maketrans({"і": "i", "ӏ": "l", "о": "o", "а": "a", "е": "e", "ѕ": "s"})


def _normalized_candidates(value: str) -> tuple[str, ...]:
    decoded = html.unescape(value)
    for _ in range(2):
        decoded = unquote(decoded)
    normalized = unicodedata.normalize("NFKC", decoded).translate(_CONFUSABLES)
    normalized = "".join(
        character for character in normalized if unicodedata.category(character) not in {"Cf", "Cc"}
    )
    candidates = [normalized]
    compact = re.sub(r"\s+", "", normalized)
    if len(compact) >= 16 and len(compact) % 4 == 0 and re.fullmatch(r"[A-Za-z0-9+/=]+", compact):
        try:
            decoded_bytes = base64.b64decode(compact, validate=True)
            candidates.append(decoded_bytes.decode("utf-8"))
        except (binascii.Error, UnicodeDecodeError):
            pass
    return tuple(candidates)


def assess_untrusted_text(value: str) -> InputAssessment:
    candidates = _normalized_candidates(value)
    reasons = tuple(
        pattern.pattern
        for pattern in _BLOCK_PATTERNS
        if any(pattern.search(candidate) for candidate in candidates)
    )
    return InputAssessment(InputDecision.BLOCK if reasons else InputDecision.ALLOW, reasons)


def neutralize_csv_formula(value: str) -> str:
    """Make exported cells inert without changing persisted ledger source values."""
    return f"'{value}" if value.lstrip().startswith(("=", "+", "-", "@")) else value
