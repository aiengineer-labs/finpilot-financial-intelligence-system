from datetime import date

import pytest

from app.engines.spending import (
    RecurringCharge,
    SpendingRow,
    money_values,
    round_div,
    summarize_spending,
)


def _row(day: int, amount: int, category: str, merchant: str, *, kind: str = "expense",
         excluded: bool = False) -> SpendingRow:
    return SpendingRow(
        day=date(2026, 6, day),
        amount_minor=amount,
        category=category,
        merchant=merchant,
        kind=kind,
        excluded=excluded,
    )


def test_round_div_is_exact_half_away_from_zero() -> None:
    assert round_div(5, 2) == 3
    assert round_div(-5, 2) == -3
    assert round_div(4, 3) == 1
    assert round_div(10_000_000_000_001, 2) == 5_000_000_000_001
    with pytest.raises(ValueError):
        round_div(1, 0)


def test_card_summary_ranks_categories_and_prices_a_bounded_cut() -> None:
    rows = [
        _row(1, -60_000, "food_delivery", "swift eats"),
        _row(10, -40_000, "food_delivery", "quick bites"),
        _row(5, -30_000, "shopping", "mega mart"),
        _row(15, -49_900, "subscriptions", "stream plus"),
        _row(20, 15_000, "refund", "mega mart", kind="refund"),
        _row(30, 100_000, "transfer", "card payment", kind="transfer", excluded=True),
    ]
    recurring = [
        RecurringCharge(
            pattern_id="pattern-1",
            merchant="stream plus",
            cadence="monthly",
            amount_minor=49_900,
            period_days=30,
        )
    ]
    summary = summarize_spending(rows, recurring, account_type="credit_card")

    assert summary["period_days"] == 30
    assert summary["total_spend_minor"] == 179_900
    assert summary["refunds_minor"] == 15_000
    assert summary["inflow_minor"] == 0
    assert summary["savings_rate_bps"] is None
    assert summary["projected_30_day_spend_minor"] == 179_900
    assert summary["average_daily_spend_minor"] == 5_997
    food = summary["categories"][0]
    assert food == {
        "category": "food_delivery",
        "spend_minor": 100_000,
        "transaction_count": 2,
        "share_bps": 5_559,
        "monthly_spend_minor": 100_000,
        "monthly_saving_minor": 20_000,
    }
    # Top three categories at a 20% cut: 20,000 + 9,980 + 6,000.
    assert summary["combined_monthly_saving_minor"] == 35_980
    assert summary["recurring_charges"][0]["monthly_equivalent_minor"] == 49_900
    # Transfers (card repayments) never count as spending.
    assert all(item["merchant"] != "card payment" for item in summary["merchants"])
    assert {100_000, 20_000, 179_900, 49_900}.issubset(money_values(summary))
    assert 2 not in money_values(summary)  # counts are not citable amounts


def test_bank_summary_reports_net_flow_and_savings_rate() -> None:
    rows = [
        _row(1, 5_000_000, "salary", "acme payroll", kind="income"),
        _row(3, -2_000_000, "rent", "green homes"),
        _row(14, -500_000, "groceries", "fresh mart"),
    ]
    summary = summarize_spending(rows, [], account_type="deposit")
    assert summary["inflow_minor"] == 5_000_000
    assert summary["net_flow_minor"] == 2_500_000
    assert summary["savings_rate_bps"] == 5_000
    # 14-day window normalised to 30 days.
    assert summary["projected_30_day_spend_minor"] == 5_357_143
