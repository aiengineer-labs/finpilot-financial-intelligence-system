# API guide

Local OpenAPI is available at `http://localhost:8000/docs`.

- `/health`, `/ready`: liveness and database readiness.
- `/api/v1/auth/*`: register, login, current memberships.
- Accounts and transaction routes: source data, uploads, listing, and corrections.
- `/api/v1/analytics/*`: immutable snapshots, forecasts, and scenarios.
- `/api/v1/agent-runs`: bounded Mesh workflow and persisted audit retrieval.
- `/api/v1/governance/*`: assets, risks, evaluations, reviews, and decisions.
- `/api/v1/digests/preference|jobs|notifications`: authenticated schedule and delivery state.
- `GET /api/v1/digests/dispatch`: Vercel Cron route authenticated with `CRON_SECRET`.

Tenant routes require a JWT and `X-Tenant-ID`; database membership is authoritative. Object queries include the resolved tenant predicate and return 404 for cross-tenant IDs. Responses carry `X-Request-ID`.

