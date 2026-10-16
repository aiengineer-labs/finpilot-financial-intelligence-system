from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from app.database.models import TransactionKind
from app.engines.financial import (
    EngineTransaction,
    ScenarioShock,
    build_forecast,
    detect_anomalies,
    detect_recurrence,
    run_scenario,
)


def _transaction(
    identity: str,
    day: date,
    amount: int,
    merchant: str = "merchant",
    category: str = "general",
    kind: TransactionKind = TransactionKind.EXPENSE,
    excluded: bool = False,
) -> EngineTransaction:
    return EngineTransaction(identity, day, amount, merchant, category, kind, excluded)


def test_monthly_recurrence_and_transfer_exclusion() -> None:
    transactions = [
        _transaction("r1", date(2026, 7, 1), -30_000, "landlord", "housing"),
        _transaction("r2", date(2026, 8, 1), -30_000, "landlord", "housing"),
        _transaction("r3", date(2026, 9, 1), -31_000, "landlord", "housing"),
        _transaction(
            "t1", date(2026, 7, 3), -50_000, "self", "transfer", TransactionKind.TRANSFER, True
        ),
        _transaction(
            "t2", date(2026, 8, 3), -50_000, "self", "transfer", TransactionKind.TRANSFER, True
        ),
        _transaction(
            "t3", date(2026, 9, 3), -50_000, "self", "transfer", TransactionKind.TRANSFER, True
        ),
    ]
    patterns = detect_recurrence(transactions)
    assert len(patterns) == 1
    assert patterns[0].merchant == "landlord"
    assert patterns[0].cadence == "monthly"
    assert patterns[0].typical_amount_minor == -30_000


def test_robust_anomaly_requires_enough_evidence() -> None:
    days = [date(2026, 9, 1) + timedelta(days=index) for index in range(6)]
    values = [-1_000, -1_050, -950, -1_000, -1_025, -20_000]
    anomalies = detect_anomalies(
        [
            _transaction(str(index), day, value, category="dining")
            for index, (day, value) in enumerate(zip(days, values, strict=True))
        ]
    )
    assert [item.transaction_id for item in anomalies] == ["5"]
    assert anomalies[0].severity == "high"


def test_forecast_is_deterministic_and_requires_known_balance() -> None:
    as_of = date(2026, 10, 1)
    history = [
        _transaction("v1", date(2026, 9, 10), -3_000),
        _transaction(
            "x1", date(2026, 9, 12), -99_000, kind=TransactionKind.TRANSFER, excluded=True
        ),
    ]
    first = build_forecast(
        as_of=as_of, horizon_days=30, opening_balance_minor=100_000, transactions=history
    )
    second = build_forecast(
        as_of=as_of, horizon_days=30, opening_balance_minor=100_000, transactions=history
    )
    assert first == second
    assert first.points[-1].balance_minor == 97_000


@given(opening=st.integers(min_value=-10_000_000, max_value=10_000_000))
def test_zero_impact_scenario_preserves_baseline(opening: int) -> None:
    baseline = build_forecast(
        as_of=date(2026, 10, 1),
        horizon_days=30,
        opening_balance_minor=opening,
        transactions=[],
    )
    result = run_scenario(baseline, [ScenarioShock(date(2026, 10, 15), 0, "zero impact")])
    assert [point.balance_minor for point in result.points] == [
        point.balance_minor for point in baseline.points
    ]
    assert result.ending_delta_minor == 0


def test_purchase_scenario_reports_shortfall_without_mutating_baseline() -> None:
    baseline = build_forecast(
        as_of=date(2026, 10, 1),
        horizon_days=30,
        opening_balance_minor=100_000,
        transactions=[],
    )
    original = baseline.points
    result = run_scenario(baseline, [ScenarioShock(date(2026, 10, 10), -150_000, "laptop")])
    assert baseline.points is original
    assert result.first_shortfall_date == date(2026, 10, 10)
    assert result.ending_delta_minor == -150_000
