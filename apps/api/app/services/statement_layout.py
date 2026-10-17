"""Deterministic layout recognition for heterogeneous bank and card statements.

Headers and cells are untrusted data. They only select which column feeds which canonical
field; every amount, date, and sign is still validated by the CSV truth parser.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime

from app.services.csv_ingestion import (
    SUPPORTED_DATE_FORMATS,
    CSVColumnMapping,
    parse_direction,
    parse_statement_date,
)

HEADER_SCAN_ROWS = 60
DATE_SAMPLE_ROWS = 200
MAX_DESCRIPTION_CHARS = 1_000
_DELIMITERS = (",", ";", "\t", "|")
_MONTH_FIRST_COUNTERPART = {"%d/%m/%Y": "%m/%d/%Y", "%d/%m/%y": "%m/%d/%y"}
_CARD_MARKERS = ("credit card", "card number", "card no", "minimum amount due", "credit limit")

_DIRECTION_LABELS = {
    "dr cr",
    "cr dr",
    "drcr",
    "crdr",
    "debit credit",
    "credit debit",
    "dr or cr",
    "debit or credit",
    "type",
    "txn type",
    "transaction type",
}
_DEBIT_WORDS = {"debit", "debits", "withdrawal", "withdrawals", "withdrawl", "dr"}
_CREDIT_WORDS = {"credit", "credits", "deposit", "deposits", "cr"}
_DETAIL_WORDS = {"narration", "description", "particulars", "details", "remarks"}
_MERCHANT_WORDS = {"merchant", "payee", "beneficiary"}

CANONICAL_HEADER = (
    "Date",
    "Merchant",
    "Description",
    "Debit",
    "Credit",
    "Amount",
    "Direction",
    "Balance",
    "Currency",
)


def normalize_label(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def column_role(label: str) -> tuple[str, int] | None:
    """Map a statement column label to a canonical role and a preference rank."""

    text = normalize_label(label)
    if not text:
        return None
    words = text.split()
    if "balance" in words or text == "bal":
        return "balance", 0
    if text in _DIRECTION_LABELS:
        return "direction", 0
    if words[0] in _DEBIT_WORDS or text in {"money out", "paid out", "amount debited"}:
        return "debit", 0
    if words[0] in _CREDIT_WORDS or text in {"money in", "paid in", "amount credited"}:
        return "credit", 0
    if "amount" in words or text in {"amt", "txn amt", "transaction amt"}:
        return "amount", 0
    if "date" in words or text in {"txn dt", "tran dt", "trans dt", "value dt"}:
        # The transaction/posting date is authoritative; a value date is only a fallback.
        return "date", 1 if "value" in words else 0
    if words[0] in _MERCHANT_WORDS or text == "merchant name":
        return "merchant", 0
    if any(word in _DETAIL_WORDS for word in words):
        return "details", 0
    if text in {"currency", "ccy", "currency code"}:
        return "currency", 0
    return None


def assign_roles(labels: list[str]) -> dict[str, int]:
    """Return the best column index for each role found in a header row."""

    best: dict[str, tuple[int, int]] = {}
    for index, label in enumerate(labels):
        found = column_role(label)
        if found is None:
            continue
        role, rank = found
        if role not in best or rank < best[role][0]:
            best[role] = (rank, index)
    return {role: index for role, (_, index) in best.items()}


def is_transaction_header(roles: dict[str, int]) -> bool:
    has_text = "details" in roles or "merchant" in roles
    has_money = ("debit" in roles and "credit" in roles) or "amount" in roles
    return "date" in roles and has_text and has_money


def infer_date_format(values: list[str]) -> tuple[str, bool] | None:
    """Choose the supported format that reads the most values; report day/month ambiguity."""

    samples = [value for value in values if value.strip()][:DATE_SAMPLE_ROWS]
    if not samples:
        return None
    counts: dict[str, int] = {}
    for date_format in SUPPORTED_DATE_FORMATS:
        count = 0
        for value in samples:
            try:
                parse_statement_date(value, date_format)
            except ValueError:
                continue
            count += 1
        counts[date_format] = count
    best = max(SUPPORTED_DATE_FORMATS, key=lambda date_format: counts[date_format])
    # A majority must agree so stray footer text cannot choose the format.
    if counts[best] == 0 or counts[best] * 2 < len(samples):
        return None
    counterpart = _MONTH_FIRST_COUNTERPART.get(best)
    ambiguous = counterpart is not None and counts[counterpart] == counts[best]
    return best, ambiguous


def has_card_markers(text: str) -> bool:
    normalized = text.casefold()
    return any(marker in normalized for marker in _CARD_MARKERS)


@dataclass(frozen=True)
class CanonicalTable:
    content: bytes
    mapping: CSVColumnMapping
    source_rows: list[int]
    warnings: list[str]
    card_statement: bool


def _sniff_header(text: str) -> tuple[str, int, list[str], str] | None:
    for delimiter in _DELIMITERS:
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
        preamble: list[str] = []
        for row_index, row in enumerate(reader):
            if row_index >= HEADER_SCAN_ROWS:
                break
            cells = [cell.strip() for cell in row]
            if len(cells) > 1 and is_transaction_header(assign_roles(cells)):
                return delimiter, row_index, cells, " ".join(preamble)
            preamble.append(" ".join(cells))
    return None


def canonicalize_csv(content: bytes, default_currency: str) -> CanonicalTable:
    """Locate the transaction table in an arbitrary bank/card CSV export."""

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded") from exc
    sniffed = _sniff_header(text)
    if sniffed is None:
        raise ValueError(
            "No transaction table was recognized. The CSV needs a header row with a date, "
            "a description, and either an amount or debit/credit columns"
        )
    delimiter, header_index, header, preamble = sniffed
    roles = assign_roles(header)

    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    raw_rows: list[tuple[int, list[str]]] = []
    for row_index, row in enumerate(reader):
        if row_index <= header_index:
            continue
        cells = [cell.strip() for cell in row]
        if any(cells):
            raw_rows.append((reader.line_num, cells))

    def cell(cells: list[str], role: str) -> str:
        index = roles.get(role)
        return cells[index] if index is not None and index < len(cells) else ""

    warnings = ["Recognized the statement columns automatically"]
    if "direction" in roles:
        directions = [cell(cells, "direction") for _, cells in raw_rows]
        present = [value for value in directions if value]
        recognized = sum(1 for value in present if parse_direction(value) is not None)
        if not present or recognized * 5 < len(present) * 4:
            # A "Type" column that holds UPI/NEFT channels rather than Dr/Cr is ignored.
            roles.pop("direction")
    use_split = "debit" in roles and "credit" in roles
    money_roles = ("debit", "credit") if use_split else ("amount",)

    detected = infer_date_format([cell(cells, "date") for _, cells in raw_rows])
    if detected is None:
        raise ValueError("The statement dates are not in a recognized format")
    date_format, ambiguous = detected
    if ambiguous:
        warnings.append("Dates were read as day/month/year")

    card_statement = has_card_markers(f"{preamble} {' '.join(header)}")
    output_rows: list[list[str]] = []
    source_rows: list[int] = []
    for line_number, cells in raw_rows:
        date_value = cell(cells, "date")
        details = cell(cells, "details")
        merchant = cell(cells, "merchant") or details
        if not date_value and not any(cell(cells, role) for role in money_roles):
            # Wrapped narration continues the previous transaction; other text is a footer.
            if details and output_rows:
                previous = output_rows[-1]
                previous[2] = f"{previous[2]} {details}".strip()[:MAX_DESCRIPTION_CHARS]
            continue
        amount = cell(cells, "amount")
        direction = cell(cells, "direction")
        if not use_split and not direction and card_statement and amount:
            # Card exports list charges unsigned and mark only payments/refunds as credits.
            direction = "Cr" if re.search(r"(?i)cr\.?$", amount) else "Dr"
        output_rows.append(
            [
                date_value,
                merchant[:255],
                details[:MAX_DESCRIPTION_CHARS],
                cell(cells, "debit") if use_split else "",
                cell(cells, "credit") if use_split else "",
                "" if use_split else amount,
                direction,
                cell(cells, "balance"),
                cell(cells, "currency"),
            ]
        )
        source_rows.append(line_number)

    has_direction = not use_split and ("direction" in roles or card_statement)
    mapping = CSVColumnMapping(
        date="Date",
        date_format=date_format,
        merchant="Merchant",
        description="Description",
        debit="Debit" if use_split else None,
        credit="Credit" if use_split else None,
        signed_amount=None if use_split else "Amount",
        direction="Direction" if has_direction else None,
        balance="Balance" if "balance" in roles else None,
        currency="Currency" if "currency" in roles else None,
        default_currency=default_currency,
    )
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(CANONICAL_HEADER)
    writer.writerows(output_rows)
    return CanonicalTable(
        content=buffer.getvalue().encode("utf-8"),
        mapping=mapping,
        source_rows=source_rows,
        warnings=warnings,
        card_statement=card_statement,
    )


def parse_flexible_date(raw: str, *, day_first: bool = True) -> datetime | None:
    """Parse one statement date for PDF tables, which carry no declared format."""

    value = re.sub(r"\s+", " ", raw).strip()
    if not value:
        return None
    formats = list(SUPPORTED_DATE_FORMATS)
    if not day_first:
        formats.sort(key=lambda date_format: date_format not in _MONTH_FIRST_COUNTERPART.values())
    for date_format in formats:
        try:
            return parse_statement_date(value, date_format)
        except ValueError:
            continue
    return None


def numeric_date_order(values: list[str]) -> bool:
    """Return True (day-first) unless the document proves a month-first ordering."""

    for value in values:
        match = re.match(r"^\s*(\d{1,2})[/-](\d{1,2})[/-]\d{2,4}", value)
        if match is None:
            continue
        first, second = int(match.group(1)), int(match.group(2))
        if first > 12:
            return True
        if second > 12:
            return False
    return True
