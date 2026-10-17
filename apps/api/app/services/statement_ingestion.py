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

MAX_PDF_PAGES = 25
MAX_PDF_OBJECTS = 25_000
MAX_EXTRACTED_TEXT_CHARS = 2_000_000
MAX_POSITIONED_TEXT_FRAGMENTS = 100_000
PDF_PARSER_NAME = "pypdf-text-table"
PDF_PARSER_VERSION = "2"
CSV_PARSER_NAME = "python-csv"
CSV_PARSER_VERSION = "1"

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


class StatementValidationError(ValueError):
    """A stable, user-safe failure raised before ledger mutation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ParsedStatement:
    format: StatementFormat
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
    first_nonempty = next((line for line in text.splitlines() if line.strip()), "")
    if not first_nonempty or not any(separator in first_nonempty for separator in (",", "\t", ";")):
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
    return required


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


def _normalized_fragment(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_positioned_text(
    page: Any, page_number: int, fragment_budget: int
) -> list[_PositionedText]:
    fragments: list[_PositionedText] = []

    def visitor(
        text: str,
        _current_matrix: list[float],
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
                fragment.text for fragment in sorted(date_fragments, key=lambda item: item.y)
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
                    for fragment in sorted(detail_fragments, key=lambda item: (item.y, item.x))
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
        csv_content, source_locations = _aligned_pdf_table_as_csv(positioned_pages, mapping)
        extraction_method = "embedded_aligned_columns"
        warnings.append("Parsed a visually aligned transaction table")
    transactions = parse_csv(csv_content, mapping)
    return ParsedStatement(
        format=StatementFormat.PDF,
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
    try:
        transactions = parse_csv(content, mapping)
    except ValueError as exc:
        raise StatementValidationError("INVALID_CSV", str(exc)) from exc
    return ParsedStatement(
        format=StatementFormat.CSV,
        detected_content_type="text/csv",
        parser_name=CSV_PARSER_NAME,
        parser_version=CSV_PARSER_VERSION,
        extraction_method="structured_text",
        page_count=None,
        warnings=[],
        source_evidence={
            row.fingerprint: {"format": "csv", "row": row.source_row}
            for row in transactions.rows
        },
        transactions=transactions,
    )
