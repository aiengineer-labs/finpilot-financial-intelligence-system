# Change management and release gates

Production-facing model, prompt, graph, financial-engine, guardrail, categorization, tool-policy, dataset, and threshold changes require a new immutable registry version. Runtime selection remains on approved versions. A separate reviewer and passing evaluation gates are required before approval.

Required engineering gates are Ruff, strict mypy, pytest, frontend ESLint/TypeScript/production build, Promptfoo injection regression, dependency and secret scanning, Docker migration/health checks, and relevant tenant-isolation tests. A pushed branch is not evidence that hosted CI or deployment passed.

Emergency degradation disables AI advice while retaining read-only ledger and deterministic analytics. Rollback selects an earlier approved artifact; it never rewrites historical lineage. The current release remains blocked because the Mesh model-based red team is recorded as `NOT_RUN` pending explicit external egress approval.

