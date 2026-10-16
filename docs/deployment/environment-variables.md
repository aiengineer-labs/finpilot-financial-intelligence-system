# Environment variables

## API

- `ENVIRONMENT`: `development`, `test`, or `production`.
- `DATABASE_URL`: async SQLAlchemy PostgreSQL URL; required in production.
- `SESSION_SECRET`: at least 32 random characters; signs short-lived access tokens.
- `ACCESS_TOKEN_MINUTES`: token lifetime, 5–1440 minutes.
- `ALLOWED_ORIGINS`: JSON list containing only authorized web origins.
- `MESH_API_KEY`: Mesh credential; never expose to the browser.
- `MESH_BASE_URL`: fixed by validation to `https://api.meshapi.ai/v1`.
- `MESH_MODEL`: approved Mesh model identifier; current local selection is `openai/gpt-5.4-mini`.
- `MESH_TIMEOUT_SECONDS`: bounded model timeout.
- `CRON_SECRET`: separate random value of at least 32 characters; Vercel sends it as a Bearer token.
- `DIGEST_DISPATCH_LIMIT`: 1–100 due preferences per invocation; default 25.

## Web

- `NEXT_PUBLIC_API_BASE_URL`: public API origin. This value is embedded in the browser bundle and must never contain credentials.

`.env.example` contains placeholders. The ignored local `.env` is not a deployment source of truth and must never be committed.

