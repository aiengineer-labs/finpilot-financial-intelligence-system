# Vercel deployment readiness

Status: configuration prepared and local builds verified; no Vercel deployment has been executed or claimed.

## Projects

Create two projects from this repository:

- API root directory: `apps/api`. Vercel can detect the exported FastAPI `app` in `app/main.py`; `vercel.json` registers a daily UTC cron request to `GET /api/v1/digests/dispatch`.
- Web root directory: `apps/web`. Set `NEXT_PUBLIC_API_BASE_URL` to the deployed API origin before building.

The daily cron is intentional: persisted preferences hold each user's weekly local eligibility, while the dispatcher claims only due rows. The API verifies Vercel's `Authorization: Bearer <CRON_SECRET>` header with a constant-time comparison. PostgreSQL row locks with `SKIP LOCKED`, unique job keys, and unique notification dedupe keys prevent concurrent duplicate delivery.

## Required evidence before claiming success

1. Configure the production variables from `environment-variables.md` in the correct projects.
2. Apply Alembic migrations to the managed PostgreSQL database through `20261016_0006`.
3. Run a Vercel production build for both roots and record bundle size/runtime output. The API contains NeMo/Presidio dependencies and must remain below the platform function bundle limit.
4. Verify `/ready`, CORS from the deployed web origin, authenticated tenant isolation, one scheduled delivery, and a zero-claim replay.
5. Record production URLs and observed Vercel Cron execution evidence. Preview deployments do not execute production cron schedules.

Do not place secrets in `vercel.json`, build arguments, or `NEXT_PUBLIC_*` values.

