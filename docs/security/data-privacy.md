# Data privacy controls

FinPilot treats credentials, tenant membership, transaction records, uploaded statements, questions, model context and audit evidence as sensitive.

## Collection and use

- Transaction data is accepted only through authenticated, tenant-scoped routes and is used for categorization, deterministic analysis, forecasts and user-requested advice.
- The browser receives only records authorized by server-side membership checks.
- Mesh receives a minimized calculation context only during an explicitly requested agent run. It never receives database credentials, session secrets or tenant authorization data.
- When **Run FinPilot** starts, or a categorization run is requested, Mesh also receives the statement labels that the keyword rules could not place. Each label is the merchant and description, with no other row data:
  - The text is cut to 96 characters, and digit runs of six or more become `<REF>`.
  - The injection policy screens it, and a blocked label is never sent.
  - Presidio minimizes it.
  - Duplicates are sent once, with only a debit or credit direction.

  Amounts, balances, dates, account identifiers and row IDs are never sent. The label text itself is not stored in the categorization audit records; they keep only label IDs, categories and confidence.
- The original user question is retained with the tenant-scoped execution record for audit. The model receives the Presidio-minimized version.

## Minimization and logging

- Secrets stay in server-side environment variables and are excluded from source and application logs.
- Presidio removes configured PII from free-text model inputs and outputs; numeric calculation fields are preserved because deterministic financial verification requires them.
- Audit events store entity types and counts, never matched PII values.
- Uploaded source descriptions remain untrusted ledger data and cannot modify prompts, tools, policies or tenant scope.

## Current limitations

Production retention periods, user export/deletion workflows and jurisdiction-specific consent/notification obligations are not yet implemented. Public deployment is blocked until those policies are selected, implemented and reviewed. Presidio's current pattern-only recognizers do not identify every person name, address or multilingual identifier. No claim of regulatory compliance is made.
