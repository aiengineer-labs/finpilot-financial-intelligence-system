# Model, prompt, and policy registry

`governance_artifacts` stores tenant-scoped, versioned and SHA-256-hashed records for these artifacts:

- the Mesh model
- the advice prompts and the categorizer prompt (`categorizer-prompts-v1`)
- the LangGraph graph
- the NeMo/Presidio guardrails
- the deterministic verifier and the financial engine
- the categorization rules
- the tool policy
- the evaluation dataset
- the human-review thresholds

Secrets and full sensitive prompts are excluded.

The categorizer prompt artifact records the controls on the categorizer:

- Categories come from a fixed list.
- A proposal is applied only at 7000 bps confidence or more.
- Stored confidence is capped at 8500 bps.
- A pass sends at most 40 labels.
- No amounts are sent.
- Human corrections cannot be overridden.

Every agent execution, recommendation, and categorization run stores the exact approved artifact IDs used at creation. Draft artifacts are never selected for runtime lineage. The database uniqueness key is tenant, artifact type, name, and version; old recommendations retain their historical lineage after a new draft is proposed.

Only owners can propose changes. Approval requires an owner or reviewer other than the artifact owner and all release evaluation gates must pass. Approval records the reviewer, reason, source, and time. Rollback pointers are supported, but automated rollback execution and configuration diffs remain future work.

