# API guide

Local OpenAPI is available at `http://localhost:8000/docs`.

- `/health`, `/ready`: liveness and database readiness.
- `/api/v1/auth/*`: register, login, current memberships.
- Accounts and transaction routes: content-validated CSV/PDF uploads, parser/source provenance, listing, and corrections. Upload failures use stable codes such as `FILE_TYPE_MISMATCH`, `MALFORMED_PDF`, `PDF_ENCRYPTED`, and `PDF_OCR_REQUIRED`.
- `POST /api/v1/accounts/{account_id}/categorization-runs`: sends the account's `mesh_required` rows to the Mesh categorizer. Only rows the current categorizer prompt version has not yet answered are sent, as up to 40 bounded, screened payee labels per call. Code then applies the answers that pass its checks. The route returns `not_needed` without a model call when nothing is pending. It returns 503 when Mesh is not configured and 502 when the provider or a guardrail fails; both failures leave rows unchanged.
- `/api/v1/analytics/*`: immutable snapshots, forecasts, and scenarios.
- `/api/v1/agent-runs`: bounded Mesh workflow and persisted audit retrieval.
- `/api/v1/governance/*`: assets, risks, evaluations, reviews, and decisions.
- `/api/v1/digests/preference|jobs|notifications`: authenticated schedule and delivery state.
- `GET /api/v1/digests/dispatch`: Vercel Cron route authenticated with `CRON_SECRET`.

Tenant routes require a JWT and `X-Tenant-ID`; database membership is authoritative. Object queries include the resolved tenant predicate and return 404 for cross-tenant IDs. Responses carry `X-Request-ID`.

`POST /api/v1/accounts/{account_id}/transaction-uploads` accepts one `.csv` or `.pdf` file plus the existing explicit mapping. The server reads at most 5 MiB, detects the actual format, requires extension/MIME consistency, validates PDF structure and resource budgets, and then dispatches to a format adapter. PDF support accepts at most 25 pages and only embedded-text transaction tables; encrypted, active-content, attachment-bearing, malformed, scanned, or structurally excessive PDFs fail closed. Successful responses include detected content type, parser/version, extraction method, page count, duration, and warnings.

`GET /api/v1/transaction-uploads/{upload_id}` returns the same parser provenance for an authorized tenant and returns 404 across tenant boundaries. Transaction responses include the source CSV row or extracted PDF page/text-line locator.

