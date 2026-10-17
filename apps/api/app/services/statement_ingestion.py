"""Security boundary and format adapters for untrusted bank statements."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

from app.services.csv_ingestion import (
    MAX_UPLOAD_BYTES,
    CSVColumnMapping,
    ParseResult,
    parse_csv,
)
from app.services.statement_layout import (
    HEADER_SCAN_ROWS,
    assign_roles,
    canonicalize_csv,
    column_role,
    has_card_markers,
    is_transaction_header,
    numeric_date_order,
    parse_flexible_date,
)

MAX_PDF_PAGES = 25
MAX_PDF_OBJECTS = 25_000
MAX_EXTRACTED_TEXT_CHARS = 2_000_000
MAX_POSITIONED_TEXT_FRAGMENTS = 100_000
PDF_PARSER_NAME = "pypdf-text-table"
PDF_PARSER_VERSION = "2"
CSV_PARSER_NAME = "python-csv"
CSV_PARSER_VERSION = "2"
MAX_CONTINUATION_LINES = 6

_PDF_HEADER = b"%PDF-"
_ACTIVE_PDF_KEYS = {
    "/AA": "PDF_ADDITIONAL_ACTION",
    "/EmbeddedFile": "PDF_EMBEDDED_FILE",
    "/EmbeddedFiles": "PDF_EMBEDDED_FILE",
    "/JavaScript": "PDF_JAVASCRIPT",
    "/JS": "PDF_JAVASCRIPT",
    "/Launch": "PDF_LAUNCH_ACTION",
    "/OpenAction": "PDF_OPEN_ACTION",
    "/RichMedia": "PDF_RICH_MEDIA",
    "/XFA": "PDF_XFA_FORM",
}
_CSV_CONTENT_TYPES = {
    "",
    "application/csv",
    "application/octet-stream",
    "application/vnd.ms-excel",
    "text/csv",
    "text/plain",
}
_PDF_CONTENT_TYPES = {"", "application/octet-stream", "application/pdf"}


class StatementFormat(StrEnum):
    CSV = "csv"
    PDF = "pdf"


class StatementKind(StrEnum):
    UNKNOWN = "unknown"
    DEPOSIT = "deposit"
    CREDIT_CARD = "credit_card"


class StatementValidationError(ValueError):
    """A stable, user-safe failure raised before ledger mutation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ParsedStatement:
    format: StatementFormat
    statement_kind: StatementKind
    mapping: CSVColumnMapping
    detected_content_type: str
    parser_name: str
    parser_version: str
    extraction_method: str
    page_count: int | None
    warnings: list[str]
    source_evidence: dict[str, dict[str, int | str]]
    transactions: ParseResult


@dataclass(frozen=True)
class _PositionedText:
    page: int
    x: float
    y: float
    font_size: float
    text: str
    # False when the page's transformation matrix flips the y axis, so a larger text-matrix
    # y is lower on the page (common in HTML-to-PDF output).
    y_up: bool = True


def _normalized_content_type(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().casefold()


def _filename_extension(filename: str) -> str:
    return Path(filename).suffix.casefold()


def detect_statement_format(content: bytes) -> StatementFormat:
    if not content:
        raise StatementValidationError("EMPTY_FILE", "The statement file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise StatementValidationError(
            "FILE_TOO_LARGE", "The statement exceeds the 5 MiB upload limit"
        )
    if content.startswith(_PDF_HEADER):
        return StatementFormat.PDF
    if b"\x00" in content:
        raise StatementValidationError(
            "UNSUPPORTED_FILE_TYPE", "The file is neither a valid CSV nor a PDF"
        )
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise StatementValidationError(
            "UNSUPPORTED_FILE_TYPE", "The file is neither a UTF-8 CSV nor a PDF"
        ) from exc
    # Bank exports may open with a few title lines before the delimited table.
    leading = [line for line in text.splitlines()[:HEADER_SCAN_ROWS] if line.strip()]
    if not any(separator in line for line in leading for separator in (",", "\t", ";", "|")):
        raise StatementValidationError(
            "UNSUPPORTED_FILE_TYPE", "The file is neither a recognizable CSV nor a PDF"
        )
    return StatementFormat.CSV


def _validate_claims(
    *, filename: str, claimed_content_type: str | None, detected_format: StatementFormat
) -> None:
    extension = _filename_extension(filename)
    expected_extension = f".{detected_format.value}"
    if extension not in {".csv", ".pdf"}:
        raise StatementValidationError(
            "UNSUPPORTED_EXTENSION", "Only .csv and .pdf bank statements are accepted"
        )
    if extension != expected_extension:
        raise StatementValidationError(
            "FILE_TYPE_MISMATCH",
            f"The file contents are {detected_format.value.upper()}, "
            f"but the filename ends in {extension}",
        )
    claimed = _normalized_content_type(claimed_content_type)
    allowed = _CSV_CONTENT_TYPES if detected_format is StatementFormat.CSV else _PDF_CONTENT_TYPES
    if claimed not in allowed:
        raise StatementValidationError(
            "CONTENT_TYPE_MISMATCH",
            f"The browser content type {claimed or 'unknown'} does not match the file contents",
        )


def _required_headers(mapping: CSVColumnMapping) -> set[str]:
    required = {mapping.date, mapping.merchant, mapping.signed_amount or mapping.debit or ""}
    if mapping.credit:
        required.add(mapping.credit)
    if mapping.direction:
        required.add(mapping.direction)
    return required


def _first_csv_row(content: bytes) -> set[str]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded") from exc
    first = next(csv.reader(io.StringIO(text, newline="")), [])
    return {cell.strip() for cell in first}


def _delimited_pdf_table_as_csv(
    page_texts: list[str], mapping: CSVColumnMapping
) -> tuple[bytes, list[dict[str, int | str]]]:
    required = _required_headers(mapping)
    selected_delimiter: str | None = None
    header: list[str] | None = None
    data_rows: list[list[str]] = []
    source_locations: list[dict[str, int | str]] = []

    for page_number, text in enumerate(page_texts, start=1):
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            if header is None:
                for delimiter in (",", "\t", "|"):
                    cells = next(csv.reader([line], delimiter=delimiter))
                    normalized = {cell.strip() for cell in cells}
                    if required.issubset(normalized):
                        selected_delimiter = delimiter
                        header = [cell.strip() for cell in cells]
                        break
                continue
            if selected_delimiter is None:
                continue
            cells = next(csv.reader([line], delimiter=selected_delimiter))
            normalized_cells = [cell.strip() for cell in cells]
            if normalized_cells == header:
                continue
            if len(normalized_cells) == len(header):
                data_rows.append(normalized_cells)
                source_locations.append(
                    {"format": "pdf", "page": page_number, "text_line": line_number}
                )

    if header is None:
        raise StatementValidationError(
            "PDF_TABLE_NOT_FOUND",
            "No supported transaction table was found. Use a text-based PDF with the "
            "mapped column headers",
        )
    if not data_rows:
        raise StatementValidationError(
            "PDF_NO_TRANSACTIONS", "The PDF transaction table does not contain any readable rows"
        )
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(data_rows)
    return buffer.getvalue().encode("utf-8"), source_locations


_AMOUNT_PATTERN = re.compile(r"^[+-]?[0-9][0-9,]*\.\d{2}$")
_DAY_MONTH_PATTERN = re.compile(r"\b(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]{3})\b")
_YEAR_PATTERN = re.compile(
    r"[\u2018\u2019'](?P<short_year>\d{2})\b|\b(?P<long_year>20\d{2})\b"
)


def _reads_downward(fragments: list[_PositionedText]) -> bool:
    """Return True when a larger text-matrix y is higher on the page (the PDF default).

    The transformation matrix is authoritative and present on every page, including
    continuation pages that do not repeat the table header.
    """

    flipped = sum(1 for fragment in fragments if not fragment.y_up)
    return flipped * 2 < len(fragments) or not fragments


def _normalized_fragment(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _statement_kind(page_texts: list[str], transactions: ParseResult) -> StatementKind:
    # Per-row running balances only appear on bank accounts, so they outrank card wording,
    # which savings statements can also contain in offers and footers.
    if any(row.balance_minor is not None for row in transactions.rows):
        return StatementKind.DEPOSIT
    # Layout extraction pads words with spaces; collapse them before matching phrases.
    normalized = re.sub(r"\s+", " ", " ".join(page_texts)).casefold()
    card_terms = ("credit limit", "minimum payment due", "total payment due", "minimum amount due")
    if "credit card" in normalized and any(term in normalized for term in card_terms):
        return StatementKind.CREDIT_CARD
    return StatementKind.UNKNOWN


def _extract_positioned_text(
    page: Any, page_number: int, fragment_budget: int
) -> list[_PositionedText]:
    fragments: list[_PositionedText] = []

    def visitor(
        text: str,
        current_matrix: list[float],
        text_matrix: list[float],
        _font: object,
        font_size: float,
    ) -> None:
        normalized = _normalized_fragment(text)
        if normalized:
            if len(fragments) >= fragment_budget:
                raise StatementValidationError(
                    "PDF_TEXT_FRAGMENT_LIMIT",
                    "The PDF contains too many independently positioned text fragments",
                )
            fragments.append(
                _PositionedText(
                    page=page_number,
                    x=float(text_matrix[4]),
                    y=float(text_matrix[5]),
                    font_size=max(float(font_size), 1.0),
                    text=normalized,
                    y_up=float(current_matrix[3]) >= 0,
                )
            )

    page.extract_text(visitor_text=visitor)
    return fragments


def _format_statement_date(raw: str, output_format: str) -> str | None:
    day_month = _DAY_MONTH_PATTERN.search(raw)
    year_match = _YEAR_PATTERN.search(raw)
    if day_month is None or year_match is None:
        return None
    year = year_match.group("short_year") or year_match.group("long_year")
    if year is None:
        return None
    source_format = "%d %b %Y" if len(year) == 4 else "%d %b %y"
    try:
        parsed = datetime.strptime(
            f"{day_month.group('day')} {day_month.group('month')} {year}", source_format
        )
    except ValueError:
        return None
    return parsed.strftime(output_format)


def _aligned_pdf_table_as_csv(
    pages: list[list[_PositionedText]], mapping: CSVColumnMapping
) -> tuple[bytes, list[dict[str, int | str]]]:
    """Convert common visually aligned statement columns to canonical CSV rows.

    This adapter intentionally relies on semantic column labels and relative coordinates,
    not a bank name or fixed page dimensions. It handles statements whose PDF text layer
    stores the date over multiple lines and the amount/direction as separate fragments.
    """

    fieldnames = [mapping.date, mapping.merchant]
    for optional in (
        mapping.description,
        mapping.transaction_id,
        mapping.signed_amount,
        mapping.debit,
        mapping.credit,
        mapping.currency,
        mapping.balance,
    ):
        if optional and optional not in fieldnames:
            fieldnames.append(optional)

    rows: list[dict[str, str]] = []
    source_locations: list[dict[str, int | str]] = []
    saw_supported_header = False
    for page_fragments in pages:
        downward = _reads_downward(page_fragments)
        joined_text = " ".join(fragment.text.casefold() for fragment in page_fragments)
        has_date_header = bool(re.search(r"\bdate\b", joined_text))
        has_detail_header = "transaction details" in joined_text or "description" in joined_text
        has_direction_header = "debit/credit" in joined_text or (
            "debit" in joined_text and "credit" in joined_text
        )
        page_is_supported = has_date_header and has_detail_header and has_direction_header
        saw_supported_header = saw_supported_header or page_is_supported
        if not saw_supported_header:
            continue

        directions = [
            fragment
            for fragment in page_fragments
            if fragment.text.casefold() in {"debit", "credit"}
        ]
        for direction in directions:
            same_line = [
                fragment
                for fragment in page_fragments
                if abs(fragment.y - direction.y) <= max(direction.font_size * 0.6, 3.0)
                and fragment.x < direction.x
                and _AMOUNT_PATTERN.fullmatch(fragment.text.replace(" ", ""))
            ]
            if not same_line:
                continue
            amount_fragment = max(same_line, key=lambda fragment: fragment.x)
            row_height = max(direction.font_size * 2.2, 16.0)
            row_fragments = [
                fragment
                for fragment in page_fragments
                if fragment.x < amount_fragment.x
                and abs(fragment.y - direction.y) <= row_height
            ]
            if not row_fragments:
                continue
            date_column_x = min(fragment.x for fragment in row_fragments)
            date_column_limit = date_column_x + max(direction.font_size * 1.8, 18.0)
            date_fragments = [
                fragment
                for fragment in row_fragments
                if fragment.x <= date_column_limit
            ]
            raw_date = " ".join(
                fragment.text
                for fragment in sorted(
                    date_fragments, key=lambda item: -item.y if downward else item.y
                )
            )
            statement_date = _format_statement_date(raw_date, mapping.date_format)
            if statement_date is None:
                continue

            detail_fragments = [
                fragment
                for fragment in row_fragments
                if fragment.x > date_column_limit
                and fragment.text not in {"₹", "$", "€", "£"}
            ]
            details = _normalized_fragment(
                " ".join(
                    fragment.text
                    for fragment in sorted(
                        detail_fragments,
                        key=lambda item: (-item.y if downward else item.y, item.x),
                    )
                )
            )
            if not details:
                continue
            merchant = details[:255]
            amount = amount_fragment.text.replace(" ", "")
            direction_name = direction.text.casefold()
            row = {field: "" for field in fieldnames}
            row[mapping.date] = statement_date
            row[mapping.merchant] = merchant
            if mapping.description:
                row[mapping.description] = details
            if mapping.currency:
                row[mapping.currency] = mapping.default_currency
            if mapping.signed_amount:
                row[mapping.signed_amount] = f"-{amount}" if direction_name == "debit" else amount
            elif mapping.debit and mapping.credit:
                row[mapping.debit if direction_name == "debit" else mapping.credit] = amount
            rows.append(row)
            source_locations.append(
                {
                    "format": "pdf",
                    "page": direction.page,
                    "text_y": round(direction.y),
                }
            )

    if not saw_supported_header:
        raise StatementValidationError(
            "PDF_TABLE_NOT_FOUND",
            "No supported transaction table was found. The PDF needs recognizable date, "
            "transaction-details, amount, and debit/credit columns",
        )
    if not rows:
        raise StatementValidationError(
            "PDF_NO_TRANSACTIONS", "The PDF transaction table does not contain any readable rows"
        )
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8"), source_locations


_PDF_AMOUNT = re.compile(r"(?i)^(?:₹|rs\.?|inr)?[-+]?\(?\d[\d,]*\.\d{2}\)?(?:cr|dr)?\.?$")
_DIRECTION_SUFFIX = re.compile(r"(?i)(cr|dr)\.?$")
_MOVEMENT_ROLES = ("debit", "credit", "amount")
_NUMERIC_ROLES = (*_MOVEMENT_ROLES, "balance")


@dataclass(frozen=True)
class _PdfColumn:
    left: float
    center: float


@dataclass
class _PdfLine:
    page: int
    y: float
    font_size: float
    date_parts: list[str]
    details: list[str]
    amounts: dict[str, str]
    direction: str | None


def _estimated_center(fragment: _PositionedText) -> float:
    # Helvetica-like glyphs average roughly half an em in width.
    return fragment.x + len(fragment.text) * fragment.font_size * 0.25


def _pdf_lines(fragments: list[_PositionedText]) -> list[list[_PositionedText]]:
    """Group fragments into visual lines in reading order (top of the page first)."""

    downward = _reads_downward(fragments)
    lines: list[list[_PositionedText]] = []
    for fragment in sorted(fragments, key=lambda item: (-item.y if downward else item.y, item.x)):
        if lines:
            anchor = lines[-1][0]
            tolerance = max(min(anchor.font_size, fragment.font_size) * 0.5, 2.0)
            if abs(anchor.y - fragment.y) <= tolerance:
                lines[-1].append(fragment)
                continue
        lines.append([fragment])
    return [sorted(line, key=lambda item: item.x) for line in lines]


def _line_labels(line: list[_PositionedText]) -> list[tuple[str, float, float]]:
    """Join same-line header words ("Transaction" + "Details") into column labels."""

    labels: list[tuple[str, float, float]] = []
    previous_end = float("-inf")
    for fragment in line:
        end = fragment.x + len(fragment.text) * fragment.font_size * 0.5
        adjacent = labels and fragment.x - previous_end <= fragment.font_size * 1.5
        # Two complete labels ("Withdrawal Amt." "Deposit Amt.") stay separate columns.
        if adjacent and (column_role(labels[-1][0]) is None or column_role(fragment.text) is None):
            text, left, _ = labels[-1]
            labels[-1] = (f"{text} {fragment.text}", left, (left + end) / 2)
        else:
            labels.append((fragment.text, fragment.x, _estimated_center(fragment)))
        previous_end = end
    return labels


def _header_columns(
    lines: list[list[_PositionedText]], index: int
) -> tuple[dict[str, _PdfColumn], int] | None:
    labels = _line_labels(lines[index])
    candidates = [(labels, 1)]
    if index + 1 < len(lines):
        below = lines[index + 1]
        gap = abs(lines[index][0].y - below[0].y)
        below_is_data = any(
            _PDF_AMOUNT.fullmatch(fragment.text.replace(" ", "")) for fragment in below
        )
        if gap <= max(lines[index][0].font_size * 2.5, 12.0) and not below_is_data:
            # Two-line headers such as "Withdrawal" over "Amount (INR)".
            merged = list(labels)
            for text, left, center in _line_labels(below):
                nearest = min(
                    range(len(merged)), key=lambda position: abs(merged[position][2] - center)
                )
                if abs(merged[nearest][2] - center) <= 40:
                    label, label_left, label_center = merged[nearest]
                    merged[nearest] = (f"{label} {text}", label_left, label_center)
                else:
                    merged.append((text, left, center))
            candidates.append((merged, 2))
    for candidate, consumed in candidates:
        roles = assign_roles([label for label, _, _ in candidate])
        if is_transaction_header(roles):
            names = {position: role for role, position in roles.items()}
            # Unused columns (Chq./Ref.No., Value Dt) still bound their neighbours' text.
            return (
                {
                    names.get(position, f"other{position}"): _PdfColumn(left=left, center=center)
                    for position, (_, left, center) in enumerate(candidate)
                },
                consumed,
            )
    return None


def _classify_pdf_line(
    line: list[_PositionedText], columns: dict[str, _PdfColumn]
) -> _PdfLine:
    numeric = {role: column for role, column in columns.items() if role in _NUMERIC_ROLES}
    ordered = sorted(columns.items(), key=lambda item: item[1].left)
    parsed = _PdfLine(
        page=line[0].page,
        y=line[0].y,
        font_size=line[0].font_size,
        date_parts=[],
        details=[],
        amounts={},
        direction=None,
    )
    for fragment in line:
        compact = fragment.text.replace(" ", "")
        if numeric and _PDF_AMOUNT.fullmatch(compact):
            center = _estimated_center(fragment)
            nearest = min(numeric, key=lambda name: abs(numeric[name].center - center))
            parsed.amounts.setdefault(nearest, compact)
            continue
        if compact.casefold().rstrip(".") in {"cr", "dr"}:
            parsed.direction = compact
            continue
        role: str | None = None
        for name, column in ordered:
            if column.left <= fragment.x + 4:
                role = name
        if role == "date":
            parsed.date_parts.append(fragment.text)
        elif role in {"details", "merchant"}:
            parsed.details.append(fragment.text)
        elif role == "direction":
            parsed.direction = fragment.text
    return parsed


def _pdf_date(raw: str, *, day_first: bool) -> datetime | None:
    parsed = parse_flexible_date(raw, day_first=day_first)
    if parsed is not None:
        return parsed
    formatted = _format_statement_date(raw, "%Y-%m-%d")
    return datetime.strptime(formatted, "%Y-%m-%d") if formatted else None


def _movement(line: _PdfLine, card_statement: bool) -> tuple[str, int] | None:
    """Return the unsigned amount and its sign (+1 credit, -1 debit) for one table row."""

    for role in _MOVEMENT_ROLES:
        token = line.amounts.get(role)
        if token is None:
            continue
        sign: int | None = {"debit": -1, "credit": 1}.get(role)
        suffix = _DIRECTION_SUFFIX.search(token)
        if suffix:
            token = token[: suffix.start()]
            sign = sign or (1 if suffix.group(1).casefold() == "cr" else -1)
        token = re.sub(r"(?i)₹|rs\.?|inr", "", token)
        if token.startswith("(") and token.endswith(")"):
            token, sign = token[1:-1], sign or -1
        if token[:1] in {"-", "+"}:
            sign = sign or (-1 if token[0] == "-" else 1)
            token = token[1:]
        if sign is None and line.direction:
            sign = 1 if line.direction.casefold().startswith("c") else -1
        if sign is None:
            # Card statements list charges unsigned; bank amounts without a marker are inflows.
            sign = -1 if card_statement else 1
        return token, sign
    return None


def _row_anchors(classified: list[_PdfLine]) -> dict[int, str]:
    """Return the lines that carry one transaction's date and movement amount."""

    is_movement = [any(role in line.amounts for role in _MOVEMENT_ROLES) for line in classified]
    anchors: dict[int, str] = {}
    for position, line in enumerate(classified):
        if not is_movement[position]:
            continue
        # A date split over lines ("08 Jun" / "'25") may borrow from a text-only neighbour.
        above = (
            classified[position - 1].date_parts
            if position > 0 and not is_movement[position - 1]
            else []
        )
        below = (
            classified[position + 1].date_parts
            if position + 1 < len(classified) and not is_movement[position + 1]
            else []
        )
        for parts in (
            line.date_parts,
            line.date_parts + below,
            above + line.date_parts,
            above + line.date_parts + below,
        ):
            raw_date = " ".join(parts)
            if parts and _pdf_date(raw_date, day_first=True) is not None:
                anchors[position] = raw_date
                break
    return anchors


def _rows_are_centered(table_pages: list[tuple[list[_PdfLine], dict[int, str], bool]]) -> bool:
    """Decide whether rows put their date/amounts mid-row with text above and below.

    Top-aligned tables print the first narration line beside the date, and nothing sits
    between the header and the first row. Vertically centered tables (common in
    HTML-rendered statements) show text above the first row, or dates between text lines.
    """

    anchor_lines = [
        classified[position] for classified, anchors, _ in table_pages for position in anchors
    ]
    if not anchor_lines:
        return False
    bare = sum(1 for line in anchor_lines if not line.details)
    if bare * 4 >= len(anchor_lines):
        return True
    for classified, anchors, header_on_page in table_pages:
        if not header_on_page:
            continue
        first_position = min(anchors)
        first = classified[first_position]
        if any(
            line.details and not line.amounts and abs(line.y - first.y) <= first.font_size * 2.2
            for line in classified[:first_position]
        ):
            return True
    return False


def _attach_wrapped_text(
    classified: list[_PdfLine], positions: list[int], *, centered: bool
) -> None:
    """Join each row's wrapped text lines to its anchor, in reading order."""

    candidates: dict[int, list[int]] = {}
    for position, line in enumerate(classified):
        if position in positions or line.amounts or not line.details:
            continue
        if centered:
            target = min(positions, key=lambda anchor: abs(classified[anchor].y - line.y))
        else:
            earlier = [anchor for anchor in positions if anchor < position]
            if not earlier:
                continue
            target = earlier[-1]
        candidates.setdefault(target, []).append(position)

    def contiguous(anchor: _PdfLine, order: list[int]) -> list[int]:
        # Walk outward from the anchor; a large vertical gap ends the row.
        kept: list[int] = []
        reference = anchor.y
        for position in order:
            line = classified[position]
            too_far = abs(line.y - reference) > line.font_size * 2.4
            if too_far or len(kept) >= MAX_CONTINUATION_LINES:
                break
            kept.append(position)
            reference = line.y
        return kept

    for target in positions:
        anchor = classified[target]
        own = candidates.get(target, [])
        above = contiguous(anchor, sorted((p for p in own if p < target), reverse=True))[::-1]
        below = contiguous(anchor, sorted(p for p in own if p > target))
        anchor.details = [
            *(text for position in above for text in classified[position].details),
            *anchor.details,
            *(text for position in below for text in classified[position].details),
        ]


def _columnar_pdf_table_as_csv(
    pages: list[list[_PositionedText]], page_texts: list[str], mapping: CSVColumnMapping
) -> tuple[bytes, list[dict[str, int | str]]]:
    """Read bank tables laid out as Date | Narration | Withdrawal | Deposit | Balance.

    Columns are located from header labels and fragment coordinates, so the adapter does
    not depend on a bank name or page size. Wrapped narration lines join their row.
    """

    card_statement = has_card_markers(" ".join(page_texts))
    columns: dict[str, _PdfColumn] | None = None
    # (lines below the table header, anchor position -> raw date, header is on this page)
    table_pages: list[tuple[list[_PdfLine], dict[int, str], bool]] = []
    for page_fragments in pages:
        lines = _pdf_lines(page_fragments)
        start = 0
        header_on_page = False
        for index in range(len(lines)):
            found = _header_columns(lines, index)
            if found is not None:
                columns, consumed = found
                start = index + consumed
                header_on_page = True
                break
        if columns is None:
            continue
        classified = [_classify_pdf_line(line, columns) for line in lines[start:]]
        page_anchors = _row_anchors(classified)
        if page_anchors:
            table_pages.append((classified, page_anchors, header_on_page))

    if columns is None:
        raise StatementValidationError(
            "PDF_TABLE_NOT_FOUND",
            "No supported transaction table was found. The PDF needs recognizable date, "
            "description, and amount or withdrawal/deposit columns",
        )
    centered = _rows_are_centered(table_pages)
    anchors: list[tuple[_PdfLine, str]] = []
    for classified, page_anchors, _ in table_pages:
        _attach_wrapped_text(classified, sorted(page_anchors), centered=centered)
        anchors.extend(
            (classified[position], page_anchors[position]) for position in sorted(page_anchors)
        )
    day_first = numeric_date_order([raw_date for _, raw_date in anchors])
    fieldnames = [mapping.date, mapping.merchant]
    for optional in (
        mapping.description,
        mapping.signed_amount,
        mapping.debit,
        mapping.credit,
        mapping.currency,
        mapping.balance,
    ):
        if optional and optional not in fieldnames:
            fieldnames.append(optional)
    rows: list[dict[str, str]] = []
    source_locations: list[dict[str, int | str]] = []
    for line, raw_date in anchors:
        parsed_date = _pdf_date(raw_date, day_first=day_first)
        movement = _movement(line, card_statement)
        details = _normalized_fragment(" ".join(line.details))
        if parsed_date is None or movement is None or not details:
            continue
        amount, sign = movement
        row = {field: "" for field in fieldnames}
        row[mapping.date] = parsed_date.strftime(mapping.date_format)
        row[mapping.merchant] = details[:255]
        if mapping.description:
            row[mapping.description] = details
        if mapping.currency:
            row[mapping.currency] = mapping.default_currency
        if mapping.signed_amount:
            row[mapping.signed_amount] = amount if sign > 0 else f"-{amount}"
        elif mapping.debit and mapping.credit:
            row[mapping.credit if sign > 0 else mapping.debit] = amount
        if mapping.balance and "balance" in line.amounts:
            row[mapping.balance] = line.amounts["balance"]
        rows.append(row)
        source_locations.append({"format": "pdf", "page": line.page, "text_y": round(line.y)})
    if not rows:
        raise StatementValidationError(
            "PDF_NO_TRANSACTIONS", "The PDF transaction table does not contain any readable rows"
        )
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8"), source_locations


def _reject_active_pdf_objects(value: object) -> None:
    pending: list[tuple[object, int]] = [(value, 0)]
    visited: set[tuple[int, int]] = set()
    while pending:
        current, depth = pending.pop()
        if depth > 64:
            raise StatementValidationError(
                "PDF_STRUCTURE_DEPTH", "The PDF object graph exceeds the safe depth limit"
            )
        if isinstance(current, IndirectObject):
            identity = (current.idnum, current.generation)
            if identity in visited:
                continue
            visited.add(identity)
            pending.append((current.get_object(), depth + 1))
            continue
        if isinstance(current, DictionaryObject):
            for key, nested in current.items():
                code = _ACTIVE_PDF_KEYS.get(str(key))
                if code:
                    raise StatementValidationError(
                        code,
                        "PDFs containing active content, attachments, or executable actions "
                        "are not accepted",
                    )
                pending.append((nested, depth + 1))
            continue
        if isinstance(current, ArrayObject):
            pending.extend((nested, depth + 1) for nested in current)


def _parse_pdf(content: bytes, mapping: CSVColumnMapping) -> ParsedStatement:
    try:
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise StatementValidationError(
                "PDF_ENCRYPTED", "Password-protected or encrypted PDFs are not supported"
            )
        page_count = len(reader.pages)
        object_count = sum(len(objects) for objects in reader.xref.values())
        if page_count == 0:
            raise StatementValidationError("PDF_NO_PAGES", "The PDF contains no pages")
        if page_count > MAX_PDF_PAGES:
            raise StatementValidationError(
                "PDF_PAGE_LIMIT", f"The PDF exceeds the {MAX_PDF_PAGES}-page limit"
            )
        if object_count > MAX_PDF_OBJECTS:
            raise StatementValidationError(
                "PDF_OBJECT_LIMIT", "The PDF is too structurally complex to process safely"
            )
        _reject_active_pdf_objects(reader.trailer)
        page_texts: list[str] = []
        positioned_pages: list[list[_PositionedText]] = []
        extracted_chars = 0
        extracted_fragments = 0
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text(extraction_mode="layout") or ""
            extracted_chars += len(text)
            if extracted_chars > MAX_EXTRACTED_TEXT_CHARS:
                raise StatementValidationError(
                    "PDF_TEXT_LIMIT", "The PDF expands beyond the safe text extraction limit"
                )
            page_texts.append(text)
            fragments = _extract_positioned_text(
                page, page_number, MAX_POSITIONED_TEXT_FRAGMENTS - extracted_fragments
            )
            extracted_fragments += len(fragments)
            positioned_pages.append(fragments)
    except StatementValidationError:
        raise
    except (PdfReadError, RecursionError, ValueError) as exc:
        raise StatementValidationError(
            "MALFORMED_PDF", "The file has a PDF header but is not a structurally valid PDF"
        ) from exc
    except Exception as exc:
        raise StatementValidationError(
            "PDF_EXTRACTION_FAILED", "The PDF could not be safely read"
        ) from exc

    if not any(text.strip() for text in page_texts):
        raise StatementValidationError(
            "PDF_OCR_REQUIRED",
            "This appears to be a scanned PDF. OCR is intentionally not enabled for "
            "untrusted uploads",
        )
    extraction_method = "embedded_text"
    warnings: list[str] = []
    try:
        csv_content, source_locations = _delimited_pdf_table_as_csv(page_texts, mapping)
    except StatementValidationError as exc:
        if exc.code != "PDF_TABLE_NOT_FOUND":
            raise
        try:
            csv_content, source_locations = _aligned_pdf_table_as_csv(positioned_pages, mapping)
            extraction_method = "embedded_aligned_columns"
            warnings.append("Parsed a visually aligned transaction table")
        except StatementValidationError as aligned_exc:
            if aligned_exc.code not in {"PDF_TABLE_NOT_FOUND", "PDF_NO_TRANSACTIONS"}:
                raise
            csv_content, source_locations = _columnar_pdf_table_as_csv(
                positioned_pages, page_texts, mapping
            )
            extraction_method = "embedded_column_table"
            warnings.append("Parsed a column-aligned transaction table")
    transactions = parse_csv(csv_content, mapping)
    return ParsedStatement(
        format=StatementFormat.PDF,
        statement_kind=_statement_kind(page_texts, transactions),
        mapping=mapping,
        detected_content_type="application/pdf",
        parser_name=PDF_PARSER_NAME,
        parser_version=PDF_PARSER_VERSION,
        extraction_method=extraction_method,
        page_count=page_count,
        warnings=warnings,
        source_evidence={
            row.fingerprint: source_locations[row.source_row - 2] for row in transactions.rows
        },
        transactions=transactions,
    )


def parse_statement(
    content: bytes,
    *,
    filename: str,
    claimed_content_type: str | None,
    mapping: CSVColumnMapping,
) -> ParsedStatement:
    """Validate claims and dispatch trusted bytes to a bounded format parser."""

    detected_format = detect_statement_format(content)
    _validate_claims(
        filename=filename,
        claimed_content_type=claimed_content_type,
        detected_format=detected_format,
    )
    if detected_format is StatementFormat.PDF:
        return _parse_pdf(content, mapping)
    effective_mapping = mapping
    warnings: list[str] = []
    card_statement = False
    try:
        if _required_headers(mapping).issubset(_first_csv_row(content)):
            transactions = parse_csv(content, mapping)
            source_rows = [row.source_row for row in transactions.rows]
        else:
            # Real bank and card exports name their columns differently; recognize them.
            table = canonicalize_csv(content, mapping.default_currency)
            effective_mapping = table.mapping
            warnings = table.warnings
            card_statement = table.card_statement
            transactions = parse_csv(table.content, table.mapping)
            source_rows = [table.source_rows[row.source_row - 2] for row in transactions.rows]
    except ValueError as exc:
        raise StatementValidationError("INVALID_CSV", str(exc)) from exc
    if any(row.balance_minor is not None for row in transactions.rows):
        statement_kind = StatementKind.DEPOSIT
    elif card_statement:
        statement_kind = StatementKind.CREDIT_CARD
    else:
        statement_kind = StatementKind.UNKNOWN
    return ParsedStatement(
        format=StatementFormat.CSV,
        statement_kind=statement_kind,
        mapping=effective_mapping,
        detected_content_type="text/csv",
        parser_name=CSV_PARSER_NAME,
        parser_version=CSV_PARSER_VERSION,
        extraction_method="structured_text",
        page_count=None,
        warnings=warnings,
        source_evidence={
            row.fingerprint: {"format": "csv", "row": source_row}
            for row, source_row in zip(transactions.rows, source_rows, strict=True)
        },
        transactions=transactions,
    )
