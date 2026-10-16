UV := uv --project apps/api
PNPM := corepack pnpm --dir apps/web

.PHONY: setup dev-api dev-web lint typecheck test security-test migrate docker-up docker-down eval seed-demo smoke requirements

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
	docker run --rm -v "$(CURDIR):/workspace" -w /workspace/evaluation/promptfoo \
		-e PROMPTFOO_PYTHON=python3 -e PROMPTFOO_DISABLE_TELEMETRY=true \
		ghcr.io/promptfoo/promptfoo:0.124.1 \
		promptfoo eval -c promptfooconfig.quick.yaml --no-cache

seed-demo:
	cd apps/api && .venv/bin/python ../../scripts/seed_demo.py

# End-to-end check of a running stack (deterministic path, no Mesh calls).
smoke:
	cd apps/api && .venv/bin/python ../../scripts/smoke_test.py

# Root requirements.txt (pinned runtime set for the organizer checks) is generated from apps/api/uv.lock.
requirements:
	uv export --project apps/api --frozen --no-dev --no-hashes --no-emit-project --no-annotate --no-header --format requirements-txt -o requirements.txt
