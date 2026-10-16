# AI risk register

The live tenant-scoped register is exposed at `GET /api/v1/governance/risks`. Each entry records a version, likelihood, impact, affected assets, cause, mitigation, test evidence, accountable role, residual risk, acceptance state, optional exception/expiry, and review date.

The baseline contains 13 risks: financial miscalculation, hallucinated advice, forecast reliability, quality drift, prompt injection, data leakage, tenant crossover, misclassification, profiling bias, model cost, scheduler failure, stale snapshots, and undetected degradation. Critical authorization, tenant-isolation, or numerical-verification controls have no exception path.

Current residual risks include the not-yet-run Mesh model red team, limited production drift history, and an upstream high-severity zlib image finding without a fixed Debian package. Public demonstrations must use synthetic data until consent, deletion/export, and production retention controls are completed.

