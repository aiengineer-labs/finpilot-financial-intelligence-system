import re
from dataclasses import dataclass

from app.database.models import ClassificationMethod, TransactionKind


@dataclass(frozen=True)
class Classification:
    category: str
    method: ClassificationMethod
    confidence_bps: int


# Order matters: the first matching category wins (e.g. "swiggyinstamart" is groceries
# before "swiggy" is dining). Keywords match at the start of a word, so UPI handles such as
# "swiggy1online@merchantbank" match while "coffee" does not match "fee".
_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("housing", ("rent", "landlord", "maintenance society", "housing society")),
    (
        "groceries",
        (
            "grocer", "supermarket", "hypermarket", "bigbasket", "dmart", "blinkit", "zepto",
            "instamart", "swiggyinstamart", "jiomart", "reliance fresh", "more retail",
            "freshtohome", "milkbasket", "country delight",
        ),
    ),
    (
        "transport",
        (
            "uber", "ola", "rapido", "metro", "irctc", "redbus", "fuel", "petrol", "diesel",
            "fastag", "parking", "indigo", "air india", "akasa",
        ),
    ),
    (
        "utilities",
        (
            "electricity", "water bill", "broadband", "mobile bill", "gas bill", "recharge",
            "jio", "airtel", "vodafone", "bescom", "tata play", "dth", "act fibernet",
        ),
    ),
    (
        "dining",
        (
            "restaurant", "cafe", "coffee", "swiggy", "zomato", "canteen", "eats", "food", "bakery",
            "pizza", "domino", "mcdonald", "kfc", "starbucks", "pure veg", "dhaba",
        ),
    ),
    (
        "healthcare",
        ("hospital", "pharmacy", "clinic", "medical", "apollo", "pharmeasy", "1mg", "medplus"),
    ),
    ("salary", ("salary", "payroll")),
    (
        "subscriptions",
        (
            "netflix", "spotify", "prime video", "hotstar", "youtube premium", "jiocinema",
            "apple.com", "google play",
        ),
    ),
    ("entertainment", ("cinema", "bookmyshow", "pvr", "inox")),
    ("education", ("udemy", "coursera", "course", "tuition", "school", "college", "byju")),
    (
        "shopping",
        ("amazon", "flipkart", "myntra", "ajio", "meesho", "nykaa", "mall", "decathlon"),
    ),
    (
        "fees_and_charges",
        (
            "joining fee", "annual fee", "late fee", "late payment", "finance charge",
            "interest charge", "gst", "penalty",
        ),
    ),
)
_CATEGORY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (
        category,
        re.compile(
            r"(?<![a-z0-9])(?:" + "|".join(re.escape(keyword) for keyword in keywords) + ")"
        ),
    )
    for category, keywords in _CATEGORY_RULES
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
    for category, pattern in _CATEGORY_PATTERNS:
        if pattern.search(haystack):
            return Classification(category, ClassificationMethod.RULE, 9_000)
    if kind is TransactionKind.INCOME:
        return Classification("other_income", ClassificationMethod.MESH_REQUIRED, 4_000)
    return Classification("uncategorized", ClassificationMethod.MESH_REQUIRED, 3_000)
