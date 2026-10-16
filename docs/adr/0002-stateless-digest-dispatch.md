# ADR 0002: persisted scheduling with stateless dispatch

Status: accepted.

Vercel request functions do not host an in-process APScheduler. A daily signed cron request queries persisted weekly eligibility, locks due rows with `SKIP LOCKED`, creates unique schedule jobs and notification keys, advances the next due time, and records delivery.

This tolerates retries and concurrent invocations without duplicates. A long-running or high-volume adapter must move to a persistent worker; bounded in-app delivery stays within the request.

