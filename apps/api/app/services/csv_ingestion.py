import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, Field, model_validator

from app.database.models import ClassificationMethod, TransactionKind
from app.engines.categorization import classify_transaction, normalize_merchant

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_ROWS = 10_000
SUPPORTED_DATE_FORMATS = {"%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"}


class CSVColumnMapping(BaseModel):
    date: str
    date_format: str
    merchant: str
    description: str | None = None
    transaction_id: str | None = None
    signed_amount: str | None = None
    debit: str | None = None
    credit: str | None = None
    currency: str | None = None
    default_currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    balance: str | None = None

    @model_validator(mode="after")
    def validate_amount_columns(self) -> "CSVColumnMapping":
        signed = self.signed_amount is not None
        split = self.debit is not None or self.credit is not None
        if signed == split:
            raise ValueError("configure signed_amount or debit/credit columns, but not both")
        if split and (self.debit is None or self.credit is None):
            raise ValueError("both debit and credit columns are required")
        if self.date_format not in SUPPORTED_DATE_FORMATS:
            raise ValueError("date_format must be explicit and supported")
        return self


@dataclass(frozen=True)
class ParsedTransaction:
    source_row: int
    transaction_date: datetime
    amount_minor: int
    currency: str
    merchant_raw: str
    merchant_normalized: str
    description: str
    external_transaction_id: str | None
    balance_minor: int | None
    kind: TransactionKind
    category: str
    classification_method: ClassificationMethod
    classification_confidence_bps: int
    fingerprint: str
    is_excluded_from_cashflow: bool


@dataclass(frozen=True)
class RowError:
    row: int
    code: str
    message: str


@dataclass(frozen=True)
class ParseResult:
    rows: list[ParsedTransaction]
    errors: list[RowError]
    duplicate_rows: int
    total_rows: int


_TRANSFER_TERMS = (
    "self transfer",
    "card payment",
    "credit card payment",
    "account transfer",
    "transfer to",
    "transfer from",
)
_REFUND_TERMS = ("refund", "reversal", "reversed", "chargeback")


def content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _money_to_minor(raw: str, *, field: str, allow_blank: bool = False) -> int | None:
    value = raw.strip().replace(",", "")
    if not value:
        if allow_blank:
            return None
        raise ValueError(f"{field} is required")
    negative_parentheses = value.startswith("(") and value.endswith(")")
    if negative_parentheses:
        value = value[1:-1]
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field} is not a valid amount") from exc
    exponent = amount.as_tuple().exponent
    if not amount.is_finite() or not isinstance(exponent, int) or exponent < -2:
        raise ValueError(f"{field} must have at most two decimal places")
    minor = int(amount * 100)
    return -minor if negative_parentheses else minor


def _signed_amount(row: dict[str, str], mapping: CSVColumnMapping) -> int:
    if mapping.signed_amount:
        value = _money_to_minor(row.get(mapping.signed_amount, ""), field="amount")
        if value is None:
            raise ValueError("amount is required")
        return value
    if not mapping.debit or not mapping.credit:
        raise ValueError("debit and credit mappings are required")
    debit = _money_to_minor(row.get(mapping.debit, ""), field="debit", allow_blank=True)
    credit = _money_to_minor(row.get(mapping.credit, ""), field="credit", allow_blank=True)
    if debit is not None and credit is not None:
        raise ValueError("row cannot contain both debit and credit")
    if debit is None and credit is None:
        raise ValueError("row must contain debit or credit")
    return abs(credit) if credit is not None else -abs(debit or 0)


def _kind(amount_minor: int, text: str) -> TransactionKind:
    normalized = text.casefold()
    if any(term in normalized for term in _TRANSFER_TERMS):
        return TransactionKind.TRANSFER
    if amount_minor > 0 and any(term in normalized for term in _REFUND_TERMS):
        return TransactionKind.REFUND
    return TransactionKind.INCOME if amount_minor > 0 else TransactionKind.EXPENSE


def _fingerprint(
    external_id: str | None,
    transaction_date: datetime,
    amount_minor: int,
    merchant: str,
    description: str,
) -> str:
    canonical = (
        f"id:{external_id.strip()}"
        if external_id
        else "|".join(
            (
                transaction_date.date().isoformat(),
                str(amount_minor),
                merchant.casefold().strip(),
                re.sub(r"\s+", " ", description.casefold()).strip(),
            )
        )
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def parse_csv(content: bytes, mapping: CSVColumnMapping) -> ParseResult:
    if not content:
        raise ValueError("CSV file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("CSV exceeds the 5 MiB upload limit")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames:
        raise ValueError("CSV header is missing")
    required = {mapping.date, mapping.merchant}
    required.add(mapping.signed_amount or mapping.debit or "")
    if mapping.credit:
        required.add(mapping.credit)
    missing = sorted(required.difference(reader.fieldnames))
    if missing:
        raise ValueError(f"CSV is missing mapped columns: {', '.join(missing)}")

    parsed: list[ParsedTransaction] = []
    errors: list[RowError] = []
    seen: set[str] = set()
    duplicates = 0
    total = 0
    for row_number, row in enumerate(reader, start=2):
        total += 1
        if total > MAX_UPLOAD_ROWS:
            raise ValueError("CSV exceeds the 10,000 row limit")
        try:
            transaction_date = datetime.strptime(row[mapping.date].strip(), mapping.date_format)
            amount_minor = _signed_amount(row, mapping)
            if amount_minor == 0:
                raise ValueError("zero-value transactions are not accepted")
            merchant = row[mapping.merchant].strip()
            if not merchant:
                raise ValueError("merchant is required")
            description = row.get(mapping.description, "").strip() if mapping.description else ""
            external_id = (
                row.get(mapping.transaction_id, "").strip() or None
                if mapping.transaction_id
                else None
            )
            currency = (
                row.get(mapping.currency, "").strip().upper() or mapping.default_currency
                if mapping.currency
                else mapping.default_currency
            )
            if not re.fullmatch(r"[A-Z]{3}", currency):
                raise ValueError("currency must be a three-letter ISO code")
            balance_minor = (
                _money_to_minor(row.get(mapping.balance, ""), field="balance", allow_blank=True)
                if mapping.balance
                else None
            )
            kind = _kind(amount_minor, f"{merchant} {description}")
            classification = classify_transaction(merchant, description, kind)
            fingerprint = _fingerprint(
                external_id, transaction_date, amount_minor, merchant, description
            )
            if fingerprint in seen:
                duplicates += 1
                continue
            seen.add(fingerprint)
            parsed.append(
                ParsedTransaction(
                    source_row=row_number,
                    transaction_date=transaction_date,
                    amount_minor=amount_minor,
                    currency=currency,
                    merchant_raw=merchant,
                    merchant_normalized=normalize_merchant(merchant),
                    description=description,
                    external_transaction_id=external_id,
                    balance_minor=balance_minor,
                    kind=kind,
                    category=classification.category,
                    classification_method=classification.method,
                    classification_confidence_bps=classification.confidence_bps,
                    fingerprint=fingerprint,
                    is_excluded_from_cashflow=kind is TransactionKind.TRANSFER,
                )
            )
        except (KeyError, ValueError) as exc:
            errors.append(RowError(row=row_number, code="INVALID_ROW", message=str(exc)))
    return ParseResult(parsed, errors, duplicates, total)
