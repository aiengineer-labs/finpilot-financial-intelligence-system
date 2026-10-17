"""Deterministic spending summary that grounds spending-reduction advice.

Every value is an integer in minor units (or basis points) computed in code. The advisor
may only cite these values, and the financial verifier rejects any other amount.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

TOP_ITEMS = 6
REDUCTION_PERCENT = 20
COMBINED_CATEGORIES = 3
_MONTH_DAYS = 30


def round_div(numerator: int, denominator: int) -> int:
    """Exact integer division rounded half away from zero."""

    if denominator <= 0:
        raise ValueError("denominator must be positive")
    quotient, remainder = divmod(abs(numerator), denominator)
    if remainder * 2 >= denominator:
        quotient += 1
    return quotient if numerator >= 0 else -quotient


@dataclass(frozen=True)
class SpendingRow:
    day: date
    amount_minor: int
    category: str
    merchant: str
    kind: str
    excluded: bool


@dataclass(frozen=True)
class RecurringCharge:
    pattern_id: str
    merchant: str
    cadence: str
    amount_minor: int
    period_days: int


def summarize_spending(
    rows: list[SpendingRow], recurring: list[RecurringCharge], *, account_type: str
) -> dict[str, Any]:
    """Summarise where money goes and what a bounded reduction would save per month."""

    if not rows:
        raise ValueError("at least one transaction is required")
    first_day = min(row.day for row in rows)
    last_day = max(row.day for row in rows)
    period_days = (last_day - first_day).days + 1
    spending = [row for row in rows if row.amount_minor < 0 and not row.excluded]
    inflows = [
        row for row in rows if row.amount_minor > 0 and not row.excluded and row.kind != "refund"
    ]
    total_spend = sum(-row.amount_minor for row in spending)
    inflow = sum(row.amount_minor for row in inflows)
    refunds = sum(row.amount_minor for row in rows if row.amount_minor > 0 and row.kind == "refund")

    def monthly(amount: int) -> int:
        return round_div(amount * _MONTH_DAYS, period_days)

    by_category: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    by_merchant: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in spending:
        by_category[row.category][0] += -row.amount_minor
        by_category[row.category][1] += 1
        by_merchant[row.merchant][0] += -row.amount_minor
        by_merchant[row.merchant][1] += 1

    ranked_categories = sorted(by_category.items(), key=lambda item: (-item[1][0], item[0]))
    categories = []
    for key, (amount, count) in ranked_categories[:TOP_ITEMS]:
        monthly_amount = monthly(amount)
        categories.append(
            {
                "category": key,
                "spend_minor": amount,
                "transaction_count": count,
                "share_bps": round_div(amount * 10_000, total_spend) if total_spend else 0,
                "monthly_spend_minor": monthly_amount,
                "monthly_saving_minor": round_div(monthly_amount * REDUCTION_PERCENT, 100),
            }
        )
    merchants = [
        {
            "merchant": name,
            "spend_minor": amount,
            "transaction_count": count,
            "monthly_spend_minor": monthly(amount),
        }
        for name, (amount, count) in sorted(
            by_merchant.items(), key=lambda item: (-item[1][0], item[0])
        )[:TOP_ITEMS]
    ]
    recurring_charges = [
        {
            "pattern_id": charge.pattern_id,
            "merchant": charge.merchant,
            "cadence": charge.cadence,
            "amount_minor": charge.amount_minor,
            "monthly_equivalent_minor": round_div(
                charge.amount_minor * _MONTH_DAYS, max(charge.period_days, 1)
            ),
        }
        for charge in sorted(recurring, key=lambda item: (-item.amount_minor, item.merchant))[
            :TOP_ITEMS
        ]
    ]
    net_flow = inflow - total_spend
    return {
        "account_type": account_type,
        "period_start": first_day.isoformat(),
        "period_end": last_day.isoformat(),
        "period_days": period_days,
        "total_spend_minor": total_spend,
        "inflow_minor": inflow,
        "refunds_minor": refunds,
        "net_flow_minor": net_flow,
        "savings_rate_bps": round_div(net_flow * 10_000, inflow) if inflow else None,
        "average_daily_spend_minor": round_div(total_spend, period_days),
        "projected_30_day_spend_minor": monthly(total_spend),
        "reduction_percent": REDUCTION_PERCENT,
        "combined_monthly_saving_minor": sum(
            item["monthly_saving_minor"] for item in categories[:COMBINED_CATEGORIES]
        ),
        "categories": categories,
        "merchants": merchants,
        "recurring_charges": recurring_charges,
    }


def money_values(summary: dict[str, Any]) -> set[int]:
    """Every minor-unit amount in a summary, i.e. the amounts advice may cite."""

    values: set[int] = set()

    def visit(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for nested_key, nested in value.items():
                visit(nested, nested_key)
        elif isinstance(value, list):
            for nested in value:
                visit(nested, key)
        elif isinstance(value, int) and not isinstance(value, bool) and key.endswith("_minor"):
            values.update({value, abs(value)})

    visit(summary)
    return values
