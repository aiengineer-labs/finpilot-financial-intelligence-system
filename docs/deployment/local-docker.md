# Local Docker deployment

Docker Compose provides PostgreSQL 17, a one-shot Alembic migration, FastAPI, and the standalone Next.js server. The API never runs migrations during a serverless cold start.

1. Start Docker Desktop or another compatible Docker daemon.
2. Optionally export `MESH_API_KEY` and `MESH_MODEL` for later live inference. They are not required for Phase 1 health/auth.
3. Run `docker compose config`, then `docker compose up --build -d`.
4. Check `docker compose ps` and `docker compose logs migrate api web`.
5. Verify `http://localhost:8000/ready`, `http://localhost:8000/docs`, and `http://localhost:3000`.
6. Stop services with `docker compose down`. Add `--volumes` only when deliberately deleting local database state.

## Clean rebuild

Delete the containers and the locally built `api`, `migrate`, and `web` images, then rebuild from scratch. The PostgreSQL volume is kept:

```bash
docker compose down --rmi local --remove-orphans
docker compose build --no-cache
docker compose up -d
docker compose ps        # api healthy, migrate exited 0, web running
```

For a completely empty database as well, use `docker compose down --rmi local --volumes` instead. This permanently deletes local households and imports.

## Testing the running stack

Run `make smoke` for an automated end-to-end check of the running stack. It covers health, the web sample, duplicate registration, import and replay, snapshot and forecast figures, both what-if outcomes, and tenant isolation. It makes no Mesh calls and creates fresh synthetic households on each run. To check by hand:

1. `curl http://localhost:8000/health` returns `{"status":"ok"}` and `curl http://localhost:8000/ready` reports the database as ready.
2. Open `http://localhost:3000` and choose **Start synthetic demo**. Overview should show a latest known balance of ₹3,37,554, and Ledger should show 139 accepted, 1 duplicate, and 1 rejected row.
3. In Forecast, choose the **Car down payment** preset and **Run analysis**. The chart and stat tiles should report a shortfall on 25 Oct; the **Laptop** preset should report none.
4. Optionally, `DEMO_PASSWORD='a-synthetic-password' make seed-demo` seeds a fixed demo login from the terminal (run it twice to see the idempotent replay).
5. Run the automated suites from the repository root: `make lint typecheck test security-test`.

**Ask advisor** and **Run FinPilot** call the Mesh API and need `MESH_API_KEY` plus approval to send the synthetic forecast context.

The Compose password and session secret are local-only examples. Replace them for any shared environment. Do not expose PostgreSQL publicly.
