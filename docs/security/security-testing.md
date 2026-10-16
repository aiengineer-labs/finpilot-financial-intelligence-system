# Security testing

Automated coverage includes authentication/tenant isolation, cross-tenant object access, input normalization, NeMo input/output blocking, Presidio minimization, tool allowlists, deterministic verifier fallback, governance authorization, historical lineage, schedule authentication/deduplication, and browser CORS preflight.

Recorded gates on 2026-10-16:

- Promptfoo 0.124.1 offline policy run: 184/184 passed, 0 model calls.
- Bandit: no findings across application code after remediation.
- Gitleaks 8.29.1: no committed-history leaks.
- pip-audit: no known Python dependency vulnerabilities after upgrading `cryptography`.
- Docker Scout: no application-introduced critical/high findings; one unresolved upstream Debian zlib high finding.
- Full backend: 219 tests, 81% line coverage; Ruff and strict mypy pass.
- Frontend: ESLint, strict TypeScript, and Next production build pass.

See `docs/IMPLEMENTATION_STATUS.md` for exact commands and qualifications. Hosted CI, the model-based Mesh red team, and Vercel production checks are not yet evidenced.

