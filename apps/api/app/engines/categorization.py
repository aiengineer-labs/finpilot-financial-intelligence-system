import re
from dataclasses import dataclass

from app.database.models import ClassificationMethod, TransactionKind


@dataclass(frozen=True)
class Classification:
    category: str
    method: ClassificationMethod
    confidence_bps: int


_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("housing", ("rent", "landlord", "maintenance society")),
    ("groceries", ("grocery", "supermarket", "bigbasket", "dmart", "blinkit")),
    ("transport", ("uber", "ola", "metro", "irctc", "fuel", "petrol")),
    ("utilities", ("electricity", "water bill", "broadband", "mobile bill", "gas bill")),
    ("dining", ("restaurant", "cafe", "swiggy", "zomato")),
    ("healthcare", ("hospital", "pharmacy", "clinic", "medical")),
    ("salary", ("salary", "payroll")),
    ("entertainment", ("netflix", "spotify", "cinema")),
    ("shopping", ("amazon", "flipkart", "mall")),
)


def normalize_merchant(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
    normalized = re.sub(r"\b(pos|upi|neft|imps|txn|ref)\b", "", normalized)
    return re.sub(r"\s+", " ", normalized).strip() or "unknown merchant"


def classify_transaction(merchant: str, description: str, kind: TransactionKind) -> Classification:
    if kind is TransactionKind.TRANSFER:
        return Classification("transfer", ClassificationMethod.RULE, 10_000)
    if kind is TransactionKind.REFUND:
        return Classification("refund", ClassificationMethod.RULE, 9_500)

    haystack = f"{merchant} {description}".casefold()
    for category, keywords in _CATEGORY_RULES:
        if any(keyword in haystack for keyword in keywords):
            return Classification(category, ClassificationMethod.RULE, 9_000)
    if kind is TransactionKind.INCOME:
        return Classification("other_income", ClassificationMethod.MESH_REQUIRED, 4_000)
    return Classification("uncategorized", ClassificationMethod.MESH_REQUIRED, 3_000)
