# Demo runbook

1. Start Docker Compose and open `http://localhost:3000`.
2. Register a synthetic household, create the primary account, and upload a synthetic statement.
3. Inspect exact rows, transfer exclusion, confidence, and provenance in Ledger.
4. Select a known balance date, horizon, optional purchase, and run FinPilot. Live inference requires approved Mesh egress.
5. Inspect Forecast, verified/withheld Advice, and deterministic-versus-Mesh Audit nodes.
6. Open How it works to replay persisted events and inspect the full workflow.
7. Open Governance to show versions, risks, release blockers, and the synthetic review decision.
8. Open Digests, enable Monday 09:00 Asia/Kolkata, and show delivery audit.

Do not use real financial data in a public demo. Do not describe fake test transport as live Mesh, and do not claim Vercel success until production URLs, migrations, health, cron, and tenant isolation are observed.

