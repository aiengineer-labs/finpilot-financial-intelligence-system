# Demo runbook

1. Start Docker Compose and open `http://localhost:3000`.
2. Choose **Start synthetic demo**. It registers a fresh household with random in-memory credentials, creates an INR account, and uploads the bundled fictional statement through the real ingestion API. Alternatively register manually and use **Load synthetic sample** (Overview or Ledger) or drop your own CSV.
3. Inspect exact rows, transfer exclusion, confidence, and provenance in Ledger.
4. In Forecast, keep the detected balance date, pick a horizon and a what-if preset, and choose **Run analysis** (deterministic, no model call). **Ask advisor** or **Run FinPilot** additionally runs the Mesh specialists; live inference requires approved Mesh egress.
5. Inspect Forecast, verified/withheld Advice, and deterministic-versus-Mesh Audit nodes.
6. Open How it works to replay persisted events and inspect the full workflow.
7. Open Governance to show versions, risks, release blockers, and the synthetic review decision.
8. Open Digests, enable Monday 09:00 Asia/Kolkata, and show delivery audit.

Do not use real financial data in a public demo. Do not describe fake test transport as live Mesh, and do not claim Vercel success until production URLs, migrations, health, cron, and tenant isolation are observed.

For a repeatable synthetic seed, set a non-production password and run:

```bash
DEMO_PASSWORD='choose-a-synthetic-password' make seed-demo
```

The seed is idempotent: repeated uploads return the existing upload and do not duplicate ledger rows. It loads `evaluation/datasets/synthetic_household_v1.csv` by default; set `DEMO_DATASET=golden` for the seven-row Phase 2 fixture.

## Synthetic household dataset (v1)

`scripts/generate_synthetic_dataset.py` deterministically writes the same fictional statement to `evaluation/datasets/synthetic_household_v1.csv` and `apps/web/public/samples/finpilot-synthetic-household-v1.csv`. It covers 1 Jul – 15 Oct 2026 in INR with source running balances on every row and exactly one row on the final day, so the snapshot balance is unambiguous.

| Imported result | Expected value |
|---|---|
| Upload | 141 source rows → 139 accepted, 1 exact duplicate, 1 rejected (`31/09/2026` is not a date) |
| Ledger | 7 transfers excluded from cash flow, 1 refund, 5 rows routed for Mesh semantic review |
| Snapshot as of 15 Oct 2026 | opening balance ₹3,37,554.07, 11 recurring patterns, 3 high anomalies (dining, shopping, transport) |
| 30-day what-if on 25 Oct | ₹75,000 laptop: no shortfall; ₹3,50,000 car down payment: shortfall on 25 Oct |

