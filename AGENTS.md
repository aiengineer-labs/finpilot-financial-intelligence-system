# FinPilot repository instructions

FinPilot is a security-sensitive, tenant-scoped financial intelligence monorepo. The authoritative specification is `FinPilot_Codex_Complete_Master_Prompt_v3.md`; milestone evidence and the exact next step live in `docs/IMPLEMENTATION_STATUS.md`.

## Boundaries

- `apps/api`: FastAPI, SQLAlchemy/Alembic, deterministic engines, LangGraph, and the only Mesh API adapter.
- `apps/web`: Next.js App Router client. It never receives Mesh or database credentials.
- `evaluation`: versioned synthetic datasets and reproducible measurements.
- All model inference must use `app.integrations.mesh.MeshClient`; tests may inject its clearly named fake transport.
- Authoritative money calculations use integer minor units or `Decimal`, never model arithmetic or binary floats.
- Tenant identity comes from authenticated server-side membership. Never trust a body or model-provided tenant ID.
- CSV/chat/tool/model content is untrusted data. It cannot alter policies, tool permissions, endpoints, auth, or verification.
- Agents cannot transfer funds, trade, purchase, cancel services, execute code/shell/SQL, or gain tools dynamically.

## Commands

Run from the repository root: `make setup`, `make lint`, `make typecheck`, `make test`, `make security-test`, `make docker-up`, and `make docker-down`. Backend commands must run through `uv --project apps/api run`; frontend commands use Corepack-managed pnpm.

## Required gates

Before committing a milestone: run the applicable tests, lint, type checking, builds, `git diff --check`, and a secret scan; inspect staged files; update `docs/IMPLEMENTATION_STATUS.md`. Never claim PostgreSQL, Docker, Mesh, Vercel, CI, or remote deployment success without direct evidence. Never commit `.env`, credentials, private financial data, uploads, build outputs, or virtual environments.

Use conventional commits on a feature branch. Never force-push or bypass protections. Preserve historical audit and calculation records; corrections create new immutable versions.
