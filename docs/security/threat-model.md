# FinPilot threat model

## Scope and trust boundaries

The protected assets are credentials, tenant membership, financial records, model context, prompts/policies, audit evidence, and infrastructure secrets. Entry points currently include the public FastAPI routes, HTTP headers, JSON request bodies, environment configuration, database responses, and the future Mesh response boundary.

The browser and every submitted value are untrusted. Authentication establishes a user identity; a database membership lookup separately authorizes each selected tenant. Model output never crosses that boundary. PostgreSQL, server-only settings, deterministic engines, and immutable audit records are trusted only through constrained interfaces and verification.

## Principal threats and controls

- **BOLA/IDOR and cross-tenant disclosure (critical):** every tenant-scoped repository query must include the membership-authorized tenant ID. Unauthorized tenants return 404. Integration tests exercise two unrelated users.
- **Credential theft/session forgery (critical):** Argon2 password hashing, short-lived signed tokens, required claims, no token in frontend source, strong-secret validation, TLS required in production. Token revocation and rotation remain Phase 1 follow-up work before public deployment.
- **Prompt/indirect injection (high):** untrusted text is never concatenated into policies or tool definitions. Deterministic detection normalizes Unicode/full-width confusables, zero-width controls, HTML entities, URL encoding and standalone base64 payloads before applying policy. Static role/tool allowlists reject unknown tools and security-context arguments. The current 168-case adversarial matrix has zero observed misses and the 16-case legitimate control set has zero observed false positives; those bounded results do not cover every paraphrase or future encoding.
- **Model-provider bypass (critical):** all application inference is centralized in `MeshClient`; its configurable URL is constrained to HTTPS `api.meshapi.ai`. A key/model is required, with no provider fallback.
- **Financial hallucination or arithmetic error (critical):** no recommendation endpoint exists until deterministic engines and the independent verification gate are integrated. Model output will never be authoritative arithmetic.
- **SQL injection (high):** SQLAlchemy parameterized statements; arbitrary SQL is absent from agent tools.
- **Malicious statement upload (high):** filenames and client MIME values are never sufficient. The API caps reads at 5 MiB, detects CSV/PDF bytes, requires extension and MIME consistency, parses PDFs strictly, rejects encryption and active-content markers, and bounds pages, objects, and extracted text. Parsers still process hostile bytes, so process-level sandboxing, malware scanning/CDR, and OCR isolation remain deployment follow-ups.
- **CSV formula injection (medium):** original ledger text remains inert data; any future export must neutralize formula-leading cells.
- **XSS/clickjacking/content sniffing (high):** React escaping plus API and web security headers. Rich model Markdown/HTML rendering is not allowed until sanitization is implemented.
- **CSRF (medium):** current APIs use explicit bearer headers and no credentialed CORS. A future cookie session design must add SameSite and CSRF controls.
- **SSRF/tool abuse (critical):** agents receive no generic network, filesystem, shell, SQL, transfer, trade, or purchase tool. Mesh is the sole model network destination.
- **Denial of service/cost exhaustion (high):** request/model size and timeout bounds begin in Phase 1; rate limiting, upload limits, execution budgets, and durable cost telemetry must land before public exposure.
- **Secret or PII leakage (critical):** secrets remain server-side and are excluded from logs/source; transaction data is not yet sent to Mesh. Presidio minimization and structured log redaction are Phase 6 gates.
- **Dependency/supply-chain compromise (high):** lockfiles, CI lint/test/build, least-privilege workflow permissions, and later dependency/container/secret scanners. The organizer workflow must be downloaded and inspected before enabling.

## Residual risk and release blockers

Public deployment remains blocked until token lifecycle/rate limits, Presidio minimization, compatible NeMo live rails, broader benign controls, dependency/secret/container scans, and production database/TLS validation pass. Audit persistence, deterministic financial verification, and the first 100+ deterministic adversarial regression gate are implemented. No claim of immunity or regulatory compliance is made.
