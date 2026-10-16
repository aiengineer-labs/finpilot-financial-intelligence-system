# ADR 0001: deterministic financial authority

Status: accepted.

FinPilot uses language models only for semantic classification and explanation. Exact amounts, ledger state, forecasts, scenario arithmetic, authorization, tool permissions, and release decisions remain deterministic code.

This increases implementation work but makes calculations reproducible and independently verifiable. A model failure degrades to withheld advice while ledger and deterministic analytics remain available.

