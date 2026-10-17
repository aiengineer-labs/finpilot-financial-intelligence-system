# Known limitations

- Live Mesh specialist execution and the model-based Promptfoo red team require explicit approval to transmit synthetic context; neither is reported as completed.
- No Vercel deployment has been executed. Function bundle size, cold start, managed-database connectivity, CORS, and production Cron remain unverified on the target account.
- The current API container includes one upstream Debian zlib high-severity finding without a fixed package; application-added packages have no high/critical findings in the recorded scan.
- Dedicated incident records, durable drift observations, user export/delete workflows, and jurisdiction-specific privacy/legal review are not implemented.
- In-app digest delivery is implemented; email and Telegram adapters are not.
- Sparse or non-stationary transaction history limits forecast usefulness. Forecasts are estimates based on recorded data and assumptions, not guaranteed outcomes.
- Access tokens are short-lived but refresh-token/session revocation infrastructure is not implemented.
- The governance UI exposes current/historic records but not a visual configuration diff or automatic rollback button.
- PDF ingestion supports bounded embedded-text tables through delimiter-separated and visually aligned column adapters. The aligned adapter requires recognizable date, transaction-details, amount, and debit/credit columns; other bank layouts may still need a new deterministic adapter. Image-only statements fail closed with `PDF_OCR_REQUIRED`; OCR is not enabled because no isolated, privacy-reviewed worker exists.
- PDF validation is defense in depth, not malware immunity. The current application uses strict structural parsing, claim matching, active-content rejection, and resource budgets, but does not yet have a deployed antivirus/CDR service or process/container isolation for the parser. Public production intake remains blocked on those controls and load testing.

