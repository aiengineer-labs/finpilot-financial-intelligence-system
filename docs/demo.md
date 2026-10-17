# Demo runbook

1. Start Docker Compose and open `http://localhost:3000`. FinPilot provisions an empty isolated workspace; there is no login or password step and no ledger data is preloaded.
2. In **Live Demo**, upload a bank or credit-card statement as CSV or text-based PDF. FinPilot detects the content before selecting a parser and rejects renamed, encrypted, active-content, malformed, oversized, or over-budget files. For a safe repeatable demo, download `apps/web/public/samples/finpilot-demo-bank-statement.csv` and upload it, or explicitly select **Use fictional demo CSV**. Both choices call the real ingestion API.
3. Inspect exact rows, transfer exclusion, confidence, and provenance in Ledger.
4. In Forecast, keep the detected balance date, pick a horizon and a what-if preset, and choose **Run analysis** (deterministic, no model call). **Run FinPilot** runs the whole pipeline for every statement kind. A credit-card or balance-free statement gets a deterministic spending projection instead of a cash forecast, because FinPilot never invents a balance. The advisor then recommends where to cut card spending. A bank statement gets the cash forecast plus advice on reducing spending and saving each month. Spending advice may cite only precomputed amounts: category and merchant totals, monthly pace, the saving from a 20% cut, and recurring charges. The verifier rejects any other amount, and the critic challenges a rejected draft once. **Ask advisor** or **Run FinPilot** additionally runs the Mesh specialists; live inference requires approved Mesh egress.
5. Inspect Forecast, verified/withheld Advice, and deterministic-versus-Mesh Audit nodes.
6. Open How it works to inspect the backend-provided graph manifest, select real nodes, and replay persisted events.
7. Open Governance to show versions, risks, release blockers, and the synthetic review decision.
8. Open Digests, enable Monday 09:00 Asia/Kolkata, and show delivery audit.

Do not use real financial data in a public demo. Do not describe fake test transport as live Mesh, and do not claim Vercel success until production URLs, migrations, health, cron, and tenant isolation are observed.

Statement support is deliberately bounded and deterministic.

- **CSV:** the configured mapping is used when its headers are present. Otherwise FinPilot locates the transaction header row (skipping bank preamble lines), maps common labels (Narration, Particulars, Withdrawal/Deposit, Debit/Credit, Dr/Cr, Amount, Closing Balance), and infers the date format from the data. Day-first wins when a column is ambiguous, and the upload records a warning. Amounts may carry `₹`/`Rs.`/`INR`, `Cr`/`Dr` suffixes, or `0.00` placeholders. Decimal-comma amounts are rejected per row rather than guessed.
- **PDF:** FinPilot accepts embedded-text tables that are delimiter-separated with the configured mapping, visually aligned with per-row debit/credit markers (typical card statements), or column-aligned with withdrawal/deposit/balance columns in either order (typical bank statements). Rows may be top-aligned or vertically centered, with the date and amounts mid-row between wrapped particulars. `B/F` opening rows and totals are not imported. Split multi-line dates and wrapped narration are read in page order, including PDFs whose generator flips the coordinate system and continuation pages without a header. Some generators draw text as many small glyph pieces, so pypdf's text visitor returns a whole line (header included) as one run. For tables, FinPilot rebuilds cells from pypdf's per-operator positions in the same layout pass that produces the page text. That uses pypdf internals pinned by `uv.lock`, with a fallback to the public extractors and a test that keeps the derived text identical to pypdf's layout output. When rows carry a running balance the statement is a bank statement, even if offers on the page mention credit cards. No adapter depends on a bank name.
- **Accounts:** card statements and bank statements are kept in separate accounts. Uploading one kind into an account of the other kind returns `409 ACCOUNT_TYPE_MISMATCH`, and the console then imports it into a matching account. The sidebar switches between accounts.

Scanned-image PDFs return `PDF_OCR_REQUIRED`; FinPilot does not send financial documents to an external OCR service or silently guess authoritative amounts.

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

