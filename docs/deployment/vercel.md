# Vercel deployment readiness

Status: configuration prepared and local builds verified; no Vercel deployment has been executed or claimed.

## Projects

Create two projects from this repository:

- API root directory: `apps/api`. Vercel can detect the exported FastAPI `app` in `app/main.py`; `vercel.json` registers a daily UTC cron request to `GET /api/v1/digests/dispatch`.
- Web root directory: `apps/web`. Set `NEXT_PUBLIC_API_BASE_URL` to the deployed API origin before building.

Portal sequence:

1. In Vercel, choose **Add New → Project**, import the authorized GitHub repository, and create the API project with Root Directory `apps/api` and framework preset FastAPI.
2. Add the API variables from `environment-variables.md` for Production and the intended Preview environments. Use a managed PostgreSQL URL and a unique production `CRON_SECRET`.
3. Deploy the API, apply Alembic migrations through `20261016_0006` using an authorized one-shot process, then verify `/ready`. The committed cron appears only for production deployments.
4. Import the same repository again as a second project with Root Directory `apps/web` and the Next.js preset.
5. Set `NEXT_PUBLIC_API_BASE_URL` to the observed API origin, add that web origin to the API `ALLOWED_ORIGINS`, redeploy both projects, and verify browser preflight/authentication.
6. In the API project, open **Settings → Cron Jobs** and confirm the daily `/api/v1/digests/dispatch` job. Observe one due delivery and a zero-claim replay before treating scheduling as verified.

The daily cron is intentional: persisted preferences hold each user's weekly local eligibility, while the dispatcher claims only due rows. The API verifies Vercel's `Authorization: Bearer <CRON_SECRET>` header with a constant-time comparison. PostgreSQL row locks with `SKIP LOCKED`, unique job keys, and unique notification dedupe keys prevent concurrent duplicate delivery.

## Required evidence before claiming success

1. Configure the production variables from `environment-variables.md` in the correct projects.
2. Apply Alembic migrations to the managed PostgreSQL database through `20261016_0006`.
3. Run a Vercel production build for both roots and record bundle size/runtime output. The API contains NeMo/Presidio dependencies and must remain below the platform function bundle limit.
4. Verify `/ready`, CORS from the deployed web origin, authenticated tenant isolation, one scheduled delivery, and a zero-claim replay.
5. Record production URLs and observed Vercel Cron execution evidence. Preview deployments do not execute production cron schedules.

Do not place secrets in `vercel.json`, build arguments, or `NEXT_PUBLIC_*` values.

References: [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi), [Cron quickstart](https://vercel.com/docs/cron-jobs/quickstart), and [secure Cron management](https://vercel.com/docs/cron-jobs/manage-cron-jobs).

