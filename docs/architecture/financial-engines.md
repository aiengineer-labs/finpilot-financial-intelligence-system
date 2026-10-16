# Deterministic financial engines

The first Phase 3 engine checkpoint is implemented in `apps/api/app/engines/financial.py`. All authoritative amounts are integer minor units. Inputs and outputs are immutable dataclasses, and no model is used for recurrence, anomalies, forecasts, or scenarios.

## Implemented

- Recurrence groups normalized merchants by cash-flow direction, requires at least three observations, recognizes bounded weekly/monthly/yearly intervals, excludes transfers/refunds, reports source transaction IDs, and derives a deterministic confidence score from amount/interval variation.
- Anomaly detection groups actual expenses by category, refuses to score sparse groups below five items, uses median/MAD modified scores, and has a stable-median fallback when MAD is zero.
- Daily 30/60/90-day forecasts require a known opening balance, project detected recurring cash flows, use trailing 30-day non-recurring expense history for the explicit variable-spend assumption, and exclude transfers.
- Scenarios branch from an immutable baseline, apply dated signed shocks only within its horizon, and return the minimum balance, first shortfall date, and ending delta.

## Verified invariants

Property and exact-fixture tests prove deterministic repeats, zero-impact scenario identity across generated opening balances, transfer exclusion, baseline immutability, recurrence recognition, robust outlier detection, exact ending balances, and shortfall dates.

## Not yet wired

Phase 3 remains `IN_PROGRESS`: database snapshots/forecast/scenario versions, APIs, chronological backtesting reports, prediction-interval policy, and forecast/scenario UI are not yet implemented. The engine refuses balance forecasts when the opening balance is unknown rather than inventing one.
