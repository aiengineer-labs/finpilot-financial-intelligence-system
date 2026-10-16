from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

from app.database.models import TransactionKind


@dataclass(frozen=True)
class EngineTransaction:
    id: str
    transaction_date: date
    amount_minor: int
    merchant: str
    category: str
    kind: TransactionKind
    is_excluded_from_cashflow: bool = False


@dataclass(frozen=True)
class RecurringPattern:
    merchant: str
    cadence: str
    period_days: int
    typical_amount_minor: int
    confidence_bps: int
    last_observed: date
    supporting_transaction_ids: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class Anomaly:
    transaction_id: str
    observed_amount_minor: int
    baseline_median_minor: int
    robust_score_milli: int
    severity: str
    explanation: str


@dataclass(frozen=True)
class ForecastPoint:
    day: date
    balance_minor: int
    recurring_flow_minor: int
    estimated_variable_spend_minor: int


@dataclass(frozen=True)
class Forecast:
    as_of: date
    horizon_days: int
    opening_balance_minor: int
    points: tuple[ForecastPoint, ...]
    assumptions: tuple[str, ...]

    @property
    def minimum_balance_minor(self) -> int:
        return min(
            (point.balance_minor for point in self.points), default=self.opening_balance_minor
        )


@dataclass(frozen=True)
class ScenarioShock:
    day: date
    amount_minor: int
    label: str


@dataclass(frozen=True)
class ScenarioResult:
    baseline: Forecast
    points: tuple[ForecastPoint, ...]
    shocks: tuple[ScenarioShock, ...]
    minimum_balance_minor: int
    first_shortfall_date: date | None
    ending_delta_minor: int


def _median_int(values: list[int]) -> int:
    return int(median(values))


def detect_recurrence(transactions: list[EngineTransaction]) -> list[RecurringPattern]:
    groups: dict[tuple[str, bool], list[EngineTransaction]] = defaultdict(list)
    for transaction in transactions:
        if transaction.is_excluded_from_cashflow or transaction.kind is TransactionKind.REFUND:
            continue
        groups[(transaction.merchant, transaction.amount_minor > 0)].append(transaction)

    patterns: list[RecurringPattern] = []
    for (merchant, _), group in groups.items():
        ordered = sorted(group, key=lambda item: (item.transaction_date, item.id))
        if len(ordered) < 3:
            continue
        intervals = [
            (current.transaction_date - previous.transaction_date).days
            for previous, current in zip(ordered, ordered[1:], strict=False)
        ]
        median_interval = _median_int(intervals)
        cadence: str | None = None
        period_days = median_interval
        if 5 <= median_interval <= 9:
            cadence, period_days = "weekly", 7
        elif 25 <= median_interval <= 35:
            cadence, period_days = "monthly", 30
        elif 350 <= median_interval <= 380:
            cadence, period_days = "yearly", 365
        if cadence is None:
            continue
        amounts = [item.amount_minor for item in ordered]
        typical = _median_int(amounts)
        amount_deviations = [abs(value - typical) for value in amounts]
        relative_deviation_bps = max(amount_deviations) * 10_000 // max(abs(typical), 1)
        interval_deviation = max(abs(value - median_interval) for value in intervals)
        confidence = max(
            5_000,
            10_000 - min(relative_deviation_bps, 3_000) - min(interval_deviation * 150, 2_000),
        )
        patterns.append(
            RecurringPattern(
                merchant=merchant,
                cadence=cadence,
                period_days=period_days,
                typical_amount_minor=typical,
                confidence_bps=confidence,
                last_observed=ordered[-1].transaction_date,
                supporting_transaction_ids=tuple(item.id for item in ordered),
                explanation=(
                    f"{len(ordered)} observations; median interval {median_interval} days; "
                    f"typical amount {typical} minor units"
                ),
            )
        )
    return sorted(patterns, key=lambda item: (item.merchant, item.cadence))


def detect_anomalies(transactions: list[EngineTransaction]) -> list[Anomaly]:
    groups: dict[str, list[EngineTransaction]] = defaultdict(list)
    for transaction in transactions:
        if (
            transaction.amount_minor < 0
            and not transaction.is_excluded_from_cashflow
            and transaction.kind is TransactionKind.EXPENSE
        ):
            groups[transaction.category].append(transaction)

    anomalies: list[Anomaly] = []
    for category, group in groups.items():
        if len(group) < 5:
            continue
        magnitudes = [abs(item.amount_minor) for item in group]
        baseline = _median_int(magnitudes)
        mad = _median_int([abs(value - baseline) for value in magnitudes])
        if mad == 0:
            threshold = max(baseline // 2, 100)
            for item, magnitude in zip(group, magnitudes, strict=True):
                deviation = abs(magnitude - baseline)
                if deviation <= threshold:
                    continue
                score_milli = deviation * 1_000 // max(threshold, 1)
                anomalies.append(
                    Anomaly(
                        item.id,
                        item.amount_minor,
                        baseline,
                        score_milli,
                        "high" if score_milli >= 3_000 else "medium",
                        f"{category} amount differs from stable median by {deviation} minor units",
                    )
                )
            continue
        for item, magnitude in zip(group, magnitudes, strict=True):
            # Modified z-score = 0.6745 * deviation / MAD, stored as thousandths.
            score_milli = 675 * abs(magnitude - baseline) // mad
            if score_milli < 3_500:
                continue
            anomalies.append(
                Anomaly(
                    item.id,
                    item.amount_minor,
                    baseline,
                    score_milli,
                    "high" if score_milli >= 7_000 else "medium",
                    f"{category} robust deviation score {score_milli / 1000:.3f}",
                )
            )
    return sorted(anomalies, key=lambda item: (-item.robust_score_milli, item.transaction_id))


def build_forecast(
    *,
    as_of: date,
    horizon_days: int,
    opening_balance_minor: int | None,
    transactions: list[EngineTransaction],
    patterns: list[RecurringPattern] | None = None,
) -> Forecast:
    if opening_balance_minor is None:
        raise ValueError("a known opening balance is required for balance forecasting")
    if horizon_days not in {30, 60, 90}:
        raise ValueError("forecast horizon must be 30, 60, or 90 days")
    recurrence = patterns if patterns is not None else detect_recurrence(transactions)
    recurring_ids = {
        transaction_id
        for pattern in recurrence
        for transaction_id in pattern.supporting_transaction_ids
    }
    lookback_start = as_of - timedelta(days=30)
    variable_spend = sum(
        abs(item.amount_minor)
        for item in transactions
        if lookback_start < item.transaction_date <= as_of
        and item.amount_minor < 0
        and item.id not in recurring_ids
        and not item.is_excluded_from_cashflow
        and item.kind is TransactionKind.EXPENSE
    )
    daily_variable_spend = variable_spend // 30
    recurring_by_day: dict[date, int] = defaultdict(int)
    for pattern in recurrence:
        next_day = pattern.last_observed + timedelta(days=pattern.period_days)
        while next_day <= as_of:
            next_day += timedelta(days=pattern.period_days)
        end = as_of + timedelta(days=horizon_days)
        while next_day <= end:
            recurring_by_day[next_day] += pattern.typical_amount_minor
            next_day += timedelta(days=pattern.period_days)

    balance = opening_balance_minor
    points: list[ForecastPoint] = []
    for offset in range(1, horizon_days + 1):
        day = as_of + timedelta(days=offset)
        recurring_flow = recurring_by_day[day]
        balance += recurring_flow - daily_variable_spend
        points.append(ForecastPoint(day, balance, recurring_flow, daily_variable_spend))
    assumptions = (
        f"Known opening balance: {opening_balance_minor} minor units",
        f"Recurring schedule inferred from {len(recurrence)} patterns",
        f"Variable spend baseline: {daily_variable_spend} minor units/day from trailing 30 days",
        "No unobserved income, fees, interest, or discretionary shocks are assumed",
    )
    return Forecast(as_of, horizon_days, opening_balance_minor, tuple(points), assumptions)


def run_scenario(baseline: Forecast, shocks: list[ScenarioShock]) -> ScenarioResult:
    shock_by_day: dict[date, int] = defaultdict(int)
    for shock in shocks:
        if shock.day <= baseline.as_of or shock.day > baseline.as_of + timedelta(
            days=baseline.horizon_days
        ):
            raise ValueError("scenario shock must fall inside the forecast horizon")
        shock_by_day[shock.day] += shock.amount_minor

    cumulative_delta = 0
    points: list[ForecastPoint] = []
    first_shortfall: date | None = None
    for baseline_point in baseline.points:
        cumulative_delta += shock_by_day[baseline_point.day]
        scenario_balance = baseline_point.balance_minor + cumulative_delta
        if scenario_balance < 0 and first_shortfall is None:
            first_shortfall = baseline_point.day
        points.append(
            ForecastPoint(
                baseline_point.day,
                scenario_balance,
                baseline_point.recurring_flow_minor + shock_by_day[baseline_point.day],
                baseline_point.estimated_variable_spend_minor,
            )
        )
    minimum = min((point.balance_minor for point in points), default=baseline.opening_balance_minor)
    return ScenarioResult(
        baseline=baseline,
        points=tuple(points),
        shocks=tuple(shocks),
        minimum_balance_minor=minimum,
        first_shortfall_date=first_shortfall,
        ending_delta_minor=cumulative_delta,
    )
