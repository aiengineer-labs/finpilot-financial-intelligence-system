# Human oversight

Users can contest advice through `POST /api/v1/governance/reviews`; the service verifies that referenced executions and recommendations belong to the authenticated tenant and records their immutable artifact lineage. Automatic verifier rejection also creates a review case. Cases contain reason, risk level, source evidence, requester, status, and resolution time.

Owners and reviewers may decide cases with approve, reject, request-information, or request-revision outcomes. The requester cannot decide their own case and ordinary members cannot decide cases. A decision records reviewer identity, reason, evidence, lineage, and timestamp. Human approval cannot enable money movement, bypass tenant checks, or suppress mandatory numerical verification.

The Governance screen includes a synthetic guaranteed-return rejection. It exists only to demonstrate escalation and auditable resolution; it does not represent a live customer's recommendation.

