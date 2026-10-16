# FinPilot governance charter

Status: implemented baseline, 2026-10-16. This charter describes project controls; it does not claim regulatory certification.

## Principles

FinPilot requires human accountability, reproducibility, version traceability, explainability, proportional oversight, privacy minimization, contestability, safe fallback, and fairness testing where a feature can affect people differently. Authorization, tenant isolation, the tool allowlist, and deterministic financial verification cannot be waived by a model or reviewer.

## Accountable roles

- Product Owner accepts residual product risk and approves scope.
- AI System Owner owns graph behavior, model use, evaluation quality, and safe degradation.
- Financial Engine Owner owns integer-minor-unit calculations, forecasts, backtests, and verifier correctness.
- Security Owner owns threat controls and time-bounded security exceptions.
- Data Owner owns data quality, minimization, purpose, and retention decisions.
- Human Reviewer resolves escalated advice without overriding code-level safety constraints.

In the current hackathon implementation one developer may occupy several roles. Separation is therefore enforced where possible through independent automated gates and a rule that an artifact owner or review requester cannot approve their own change/case.

## Authority and evidence

The PostgreSQL governance registry, immutable recommendation lineage, evaluation results, risk register, and human decisions are the system of record. Git history is the change record. The governance UI is a read-only operational view except for the explicit synthetic review demonstration. Production promotion is blocked while any required evaluation is failed or not run.

