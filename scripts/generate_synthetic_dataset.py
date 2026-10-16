"""Generate the versioned synthetic household statement used by demos and the UI.

The output is fictional, deterministic, and safe to commit. Amounts are integer
paise; balances are a running integer total, so the CSV is internally consistent.
Run from the repository root:

    python3 scripts/generate_synthetic_dataset.py
"""

from __future__ import annotations

import csv
import io
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = (
    ROOT / "evaluation" / "datasets" / "synthetic_household_v1.csv",
    ROOT / "apps" / "web" / "public" / "samples" / "finpilot-synthetic-household-v1.csv",
)
SEED = 20261016
START = date(2026, 7, 1)
END = date(2026, 10, 15)
OPENING_BALANCE_MINOR = 12_450_000
HEADER = (
    "Date", "Debit", "Credit", "Merchant", "Description", "Transaction ID", "Currency", "Balance"
)


@dataclass(frozen=True)
class Event:
    day: date
    amount_minor: int  # negative = debit, positive = credit
    merchant: str
    description: str


def _paise(rng: random.Random, low_rupees: int, high_rupees: int, step_minor: int = 100) -> int:
    value = rng.randint(low_rupees * 100, high_rupees * 100)
    return max(step_minor, value - value % step_minor)


def _month_days(day_of_month: int) -> list[date]:
    days = []
    for month in range(START.month, END.month + 1):
        candidate = date(START.year, month, day_of_month)
        if START <= candidate < END:
            days.append(candidate)
    return days


def _every(weekday: int) -> list[date]:
    day = START + timedelta(days=(weekday - START.weekday()) % 7)
    days = []
    while day < END:
        days.append(day)
        day += timedelta(days=7)
    return days


def build_events(rng: random.Random) -> list[Event]:
    events: list[Event] = []
    add = events.append

    for day in _month_days(1):
        add(Event(day, 14_850_000, "ACME Payroll", "Monthly salary credit"))
    for day in _month_days(2):
        add(Event(day, -2_000_000, "HDFC Savings", "Self transfer to savings"))
    for day in _month_days(3):
        add(Event(day, -3_800_000, "Green Homes Rent", "Monthly rent - Flat 4B"))
    for day in _month_days(5):
        add(Event(day, -64_900, "Netflix", "Netflix subscription"))
    for day in _month_days(8):
        add(Event(day, -117_882, "Airtel Broadband", "Broadband monthly plan"))
    for day in _month_days(12):
        add(Event(day, -11_900, "Spotify", "Spotify Premium"))
    for day in _month_days(18):
        add(Event(day, -_paise(rng, 8_500, 14_500), "Bank Credit Card", "Credit card payment"))
    for day in _month_days(20):
        add(Event(day, -39_900, "Jio Mobile Bill", "Mobile bill postpaid"))
    for day in _month_days(22):
        add(Event(day, -199_900, "Cult Fit", "Gym membership"))
    for day in _month_days(25):
        add(Event(day, -50_000, "Namma Metro", "Metro card recharge"))
    # Electricity lands on the 15th; the final statement day carries only this row.
    for month, amount in ((7, 218_400), (8, 243_650), (9, 201_275), (10, 194_820)):
        add(Event(date(2026, month, 15), -amount, "BESCOM Electricity", "Electricity bill"))

    for day in _every(6):  # Sundays
        add(Event(day, -_paise(rng, 1_850, 3_450, 50), "BigBasket", "Weekly grocery order"))
    for day in _every(2):  # Wednesdays
        add(Event(day, -_paise(rng, 240, 690, 10), "Swiggy", "Food delivery"))
    for day in _every(5):  # Saturdays
        merchant = rng.choice(("Zomato", "Third Wave Cafe", "Swiggy"))
        add(Event(day, -_paise(rng, 320, 890, 10), merchant, "Weekend dining"))
    for day in _every(1) + _every(4):  # Tuesdays and Fridays
        add(Event(day, -_paise(rng, 160, 480, 10), "Uber", "Ride to office"))

    for offset in range(4, (END - START).days, 11):
        amount = -_paise(rng, 499, 3_299, 100)
        merchant = rng.choice(("Amazon", "Flipkart"))
        add(Event(START + timedelta(days=offset), amount, merchant, "Online order"))
    for offset in range(9, (END - START).days, 16):
        amount = -_paise(rng, 280, 1_450, 10)
        add(Event(START + timedelta(days=offset), amount, "Apollo Pharmacy", "Pharmacy purchase"))

    # Irregular income, a refund, and three deliberate outliers for the anomaly engine.
    add(Event(date(2026, 7, 24), 1_850_000, "Upwork Global", "Freelance design project"))
    add(Event(date(2026, 9, 19), 2_725_000, "Upwork Global", "Freelance design project"))
    add(Event(date(2026, 8, 21), 219_900, "Amazon", "Order refund - returned shoes"))
    add(Event(date(2026, 8, 14), -1_185_000, "Taj Restaurant", "Anniversary dinner"))
    add(Event(date(2026, 9, 9), -2_499_000, "Flipkart", "Noise-cancelling headphones"))
    add(Event(date(2026, 9, 26), -214_000, "Uber", "Airport ride"))
    return events


def _money(minor: int) -> str:
    return f"{minor // 100}.{minor % 100:02d}"


def render(events: list[Event]) -> str:
    ordered = sorted(events, key=lambda item: (item.day, -item.amount_minor, item.merchant))
    finals = [item for item in ordered if item.day == END]
    if len(finals) != 1:
        raise SystemExit(f"{END} must hold exactly one row so the snapshot balance is unambiguous")

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADER)
    balance = OPENING_BALANCE_MINOR
    duplicate_row: list[str] | None = None
    for index, event in enumerate(ordered, start=1):
        balance += event.amount_minor
        row = [
            event.day.strftime("%d/%m/%Y"),
            _money(-event.amount_minor) if event.amount_minor < 0 else "",
            _money(event.amount_minor) if event.amount_minor > 0 else "",
            event.merchant,
            event.description,
            f"syn-{index:04d}",
            "INR",
            _money(balance),
        ]
        writer.writerow(row)
        if duplicate_row is None and event.merchant == "Swiggy" and event.day.month == 8:
            # Validation edge cases: an exact re-export of one row and an impossible date.
            duplicate_row = row
            writer.writerow(row)
            invalid = ["31/09/2026", "450.00", "", "Swiggy", "Food delivery", "syn-invalid-date"]
            writer.writerow([*invalid, "INR", ""])
    if balance < 0:
        raise SystemExit("synthetic balance went negative; adjust the generator")
    return buffer.getvalue()


def main() -> None:
    content = render(build_events(random.Random(SEED)))
    for path in OUTPUTS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({content.count(chr(10)) - 1} data rows)")


if __name__ == "__main__":
    main()
