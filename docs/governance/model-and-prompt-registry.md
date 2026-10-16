# Model, prompt, and policy registry

`governance_artifacts` stores tenant-scoped, versioned and SHA-256-hashed records for the Mesh model, prompts, LangGraph graph, NeMo/Presidio guardrails, deterministic verifier, financial engine, categorization rules, tool policy, evaluation dataset, and human-review thresholds. Secrets and full sensitive prompts are excluded.

Every agent execution and recommendation stores the exact approved artifact IDs used at creation. Draft artifacts are never selected for runtime lineage. The database uniqueness key is tenant, artifact type, name, and version; old recommendations retain their historical lineage after a new draft is proposed.

Only owners can propose changes. Approval requires an owner or reviewer other than the artifact owner and all release evaluation gates must pass. Approval records the reviewer, reason, source, and time. Rollback pointers are supported, but automated rollback execution and configuration diffs remain future work.

