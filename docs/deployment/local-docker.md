# Local Docker deployment

Docker Compose provides PostgreSQL 17, a one-shot Alembic migration, FastAPI, and the standalone Next.js server. The API never runs migrations during a serverless cold start.

1. Start Docker Desktop or another compatible Docker daemon.
2. Optionally export `MESH_API_KEY` and `MESH_MODEL` for later live inference. They are not required for Phase 1 health/auth.
3. Run `docker compose config`, then `docker compose up --build -d`.
4. Check `docker compose ps` and `docker compose logs migrate api web`.
5. Verify `http://localhost:8000/ready`, `http://localhost:8000/docs`, and `http://localhost:3000`.
6. Stop services with `docker compose down`. Add `--volumes` only when deliberately deleting local database state.

The Compose password and session secret are local-only examples. Replace them for any shared environment. Do not expose PostgreSQL publicly.
