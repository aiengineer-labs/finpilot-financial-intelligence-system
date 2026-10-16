UV := uv --project apps/api
PNPM := corepack pnpm --dir apps/web

.PHONY: setup dev-api dev-web lint typecheck test security-test migrate docker-up docker-down eval seed-demo

setup:
	UV_CACHE_DIR=.cache/uv uv sync --project apps/api --python 3.12
	corepack pnpm --dir apps/web install --frozen-lockfile

dev-api:
	$(UV) run uvicorn app.main:app --app-dir apps/api --reload --port 8000

dev-web:
	$(PNPM) dev

lint:
	$(UV) run ruff check apps/api/app apps/api/tests
	$(PNPM) lint

typecheck:
	cd apps/api && uv run mypy app
	$(PNPM) typecheck

test:
	cd apps/api && uv run pytest -q --cov=app --cov-report=term-missing

security-test:
	cd apps/api && uv run pytest -q tests/security

migrate:
	cd apps/api && uv run alembic upgrade head

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

eval:
	@echo "Evaluation runner becomes available with the first numerical engine slice."

seed-demo:
	@echo "Synthetic demo seeding becomes available with the transaction slice."
