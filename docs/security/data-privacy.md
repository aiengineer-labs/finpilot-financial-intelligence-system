# Data privacy controls

FinPilot treats credentials, tenant membership, transaction records, uploaded statements, questions, model context and audit evidence as sensitive.

## Collection and use

- Transaction data is accepted only through authenticated, tenant-scoped routes and is used for categorization, deterministic analysis, forecasts and user-requested advice.
- The browser receives only records authorized by server-side membership checks.
- Mesh receives a minimized calculation context only during an explicitly requested agent run. It never receives database credentials, session secrets or tenant authorization data.
- The original user question is retained with the tenant-scoped execution record for audit. The model receives the Presidio-minimized version.

## Minimization and logging

- Secrets stay in server-side environment variables and are excluded from source and application logs.
- Presidio removes configured PII from free-text model inputs and outputs; numeric calculation fields are preserved because deterministic financial verification requires them.
- Audit events store entity types and counts, never matched PII values.
- Uploaded source descriptions remain untrusted ledger data and cannot modify prompts, tools, policies or tenant scope.

## Current limitations

Production retention periods, user export/deletion workflows and jurisdiction-specific consent/notification obligations are not yet implemented. Public deployment is blocked until those policies are selected, implemented and reviewed. Presidio's current pattern-only recognizers do not identify every person name, address or multilingual identifier. No claim of regulatory compliance is made.
