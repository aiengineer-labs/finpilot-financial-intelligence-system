FROM ghcr.io/astral-sh/uv:0.7.13-python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
COPY alembic alembic
COPY alembic.ini ./

FROM python:3.12-slim-bookworm AS runtime
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN addgroup --system --gid 1001 finpilot && adduser --system --uid 1001 --ingroup finpilot finpilot
COPY --from=builder --chown=finpilot:finpilot /app /app
USER finpilot
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
