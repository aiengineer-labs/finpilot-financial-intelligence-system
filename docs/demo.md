# Demo runbook

1. Start Docker Compose and open `http://localhost:3000`. FinPilot provisions an empty isolated workspace; there is no login or password step and no ledger data is preloaded.
2. In **Live Demo**, upload a bank CSV or supported text-based PDF. FinPilot detects the content before selecting a parser and rejects renamed, encrypted, active-content, malformed, oversized, or over-budget files. For a safe repeatable demo, download `apps/web/public/samples/finpilot-demo-bank-statement.csv` and upload it, or explicitly select **Use fictional demo CSV**. Both choices call the real ingestion API.
3. Inspect exact rows, transfer exclusion, confidence, and provenance in Ledger.
4. In Forecast, keep the detected balance date, pick a horizon and a what-if preset, and choose **Run analysis** (deterministic, no model call). **Ask advisor** or **Run FinPilot** additionally runs the Mesh specialists; live inference requires approved Mesh egress.
5. Inspect Forecast, verified/withheld Advice, and deterministic-versus-Mesh Audit nodes.
6. Open How it works to inspect the backend-provided graph manifest, select real nodes, and replay persisted events.
7. Open Governance to show versions, risks, release blockers, and the synthetic review decision.
8. Open Digests, enable Monday 09:00 Asia/Kolkata, and show delivery audit.

Do not use real financial data in a public demo. Do not describe fake test transport as live Mesh, and do not claim Vercel success until production URLs, migrations, health, cron, and tenant isolation are observed.

PDF support is deliberately narrow and deterministic: the PDF must contain embedded text with the configured transaction column headers. Scanned-image PDFs return `PDF_OCR_REQUIRED`; FinPilot does not send financial documents to an external OCR service or silently guess authoritative amounts.

For a reproducible PDF-path demonstration, upload `evaluation/datasets/phase2_golden.pdf`. It is generated from the same synthetic seven-row truth fixture by `scripts/generate_pdf_statement_fixture.py` and intentionally retains the duplicate, malformed date, missing balance, transfer, refund, and inert prompt-injection text.

## Upload-ready demo CSV

`apps/web/public/samples/finpilot-demo-bank-statement.csv` is a 30-row fictional INR statement covering July–October 2026. It contains source balances, salary, rent, groceries, utilities, transport, a subscription, savings transfers, a refund and an unusual medical expense. It is never imported automatically: the reviewer must upload it or explicitly choose the demo-file action.

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

