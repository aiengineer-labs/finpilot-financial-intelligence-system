"""Security boundary and format adapters for untrusted bank statements."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

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
PDF_PARSER_NAME = "pypdf-text-table"
PDF_PARSER_VERSION = "1"
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


def _pdf_table_as_csv(
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
        extracted_chars = 0
        for page in reader.pages:
            text = page.extract_text(extraction_mode="layout") or ""
            extracted_chars += len(text)
            if extracted_chars > MAX_EXTRACTED_TEXT_CHARS:
                raise StatementValidationError(
                    "PDF_TEXT_LIMIT", "The PDF expands beyond the safe text extraction limit"
                )
            page_texts.append(text)
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
    csv_content, source_locations = _pdf_table_as_csv(page_texts, mapping)
    transactions = parse_csv(csv_content, mapping)
    return ParsedStatement(
        format=StatementFormat.PDF,
        detected_content_type="application/pdf",
        parser_name=PDF_PARSER_NAME,
        parser_version=PDF_PARSER_VERSION,
        extraction_method="embedded_text",
        page_count=page_count,
        warnings=[],
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
