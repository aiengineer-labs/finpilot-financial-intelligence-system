# FinPilot — Neuro-Symbolic Financial Decision Intelligence

FinPilot is a production-oriented, tenant-isolated financial intelligence application for Agent Arena 2026 Track 02. Deterministic Python engines own financial truth; specialized LangGraph agents use the sponsor Mesh API only for bounded semantic reasoning. Independent code verifies every recommendation before release.

[Implementation status](docs/IMPLEMENTATION_STATUS.md) is the source of truth for verified results and blockers. No hosted deployment, live Mesh run, or regulatory certification is implied.

## Working features

- Authentication, household membership authorization, and server-derived tenant isolation.
- Idempotent CSV ingestion with explicit mappings, row errors, exact minor units, transfers/refunds, and correction lineage.
- Recurrence, robust anomaly detection, immutable snapshots, chronological backtests, 30/60/90-day forecasts, and what-if branches.
- Typed LangGraph analyst, advisor, critic, and verifier flow. All model inference uses Mesh; no provider fallback exists.
- Deterministic input/tool policy, NeMo Guardrails, Presidio minimization, fail-closed output verification, and persisted audit events.
- Versioned governance assets, risk/evaluation gates, human-review queue, exact recommendation lineage, and governance UI.
- Durable timezone-aware weekly digests with signed Vercel Cron dispatch, SQL locking, dedupe keys, and in-app delivery audit.
- Responsive glass-material console (light/dark, ⌘K command palette, interactive SVG charts) with Overview, Ledger, Forecast, Advisor, Audit, Governance, Digests, and How it works views.
- One-click synthetic demo and a versioned fictional household statement (`evaluation/datasets/synthetic_household_v1.csv`) that exercises the real ingestion, analytics, and validation paths.

## Local quickstart

Prerequisites: Docker with Compose, or Python 3.12 plus uv 0.7.13 and Node 22 plus pnpm 10.18.3.

```bash
cp .env.example .env
# Replace SESSION_SECRET and CRON_SECRET with separate random 32+ character values.
make setup
make lint typecheck test security-test
make docker-up
curl http://localhost:8000/ready
```

Open `http://localhost:3000`. Interactive API documentation is at `http://localhost:8000/docs`.

`MESH_API_KEY` is needed only for live agent inference. Tests inject an explicitly fake Mesh transport; production code refuses direct provider endpoints. Use synthetic data for public demonstrations.

## Architecture

```mermaid
flowchart LR
  UI[Next.js operations console] -->|JWT + authorized tenant selector| API[FastAPI]
  API --> AUTH[Membership boundary]
  AUTH --> DB[(PostgreSQL)]
  API --> INGEST[CSV normalization]
  INGEST --> ENGINE[Deterministic engines]
  ENGINE --> GRAPH[Bounded LangGraph]
  GRAPH --> RAILS[NeMo + Presidio]
  RAILS --> MESH[Mesh API only]
  GRAPH --> VERIFY[Independent financial verifier]
  VERIFY --> AUDIT[Recommendation + lineage]
  CRON[Vercel Cron] -->|Bearer CRON_SECRET| DISPATCH[Idempotent dispatcher]
  DISPATCH --> DB
  DB --> UI
```

See [system design](docs/architecture/system-design.md), [agent workflow](docs/architecture/agent-workflow.md), and [financial engines](docs/architecture/financial-engines.md).

## API surface

All product endpoints are under `/api/v1`; tenant endpoints require `Authorization: Bearer …` and `X-Tenant-ID`. Major groups are authentication, accounts/uploads/transactions, analytics snapshots/forecasts/scenarios, agent runs, governance, and digests/notifications. The digest dispatcher is authenticated separately with `CRON_SECRET`.

See [API guide](docs/api/README.md) and generated OpenAPI for the exact contract.

## Verification

```bash
cd apps/api
.venv/bin/ruff check app tests
.venv/bin/mypy app
.venv/bin/pytest -q --cov=app

cd ../web
node_modules/.bin/eslint src --max-warnings=0
node_modules/.bin/tsc --noEmit
node_modules/.bin/next build

cd ../..
docker compose config --quiet
git diff --check
```

The latest recorded local run passed 219 tests at 81% line coverage, strict typing, linting, Next production build, PostgreSQL migrations through `20261016_0006`, and browser smoke tests. The bounded offline Promptfoo corpus passed 184/184 cases (168 attacks and 16 legitimate controls). Detailed evidence is in [implementation status](docs/IMPLEMENTATION_STATUS.md) and [evaluation results](docs/evaluation/results.md).

## Deployment and limitations

Two Vercel project roots are prepared: `apps/api` and `apps/web`. Deployment needs managed PostgreSQL, project environment variables, Vercel authentication, migrations, and observed production checks. See [Vercel runbook](docs/deployment/vercel.md) and [environment variables](docs/deployment/environment-variables.md).

Known blockers include the not-yet-run Mesh model-based red team, unverified Vercel bundle/runtime size, missing hosted deployment evidence, and one upstream Debian zlib high-severity image finding without a fixed package. See [known limitations](docs/security/known-limitations.md).

## Documentation map

- [Demo runbook](docs/demo.md)
- [Security architecture](docs/security/guardrail-architecture.md) and [testing](docs/security/security-testing.md)
- [Governance charter](docs/governance/governance-charter.md) and [risk register](docs/governance/risk-register.md)
- [Local Docker](docs/deployment/local-docker.md) and [Vercel](docs/deployment/vercel.md)
- [Evaluation methodology](docs/evaluation/methodology.md) and [results](docs/evaluation/results.md)
