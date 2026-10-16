# Guardrail architecture

Last verified: 2026-10-16.

## Enforced request path

The advice route applies independent controls in this order:

1. `assess_untrusted_text` normalizes Unicode, control characters, HTML entities, URL encoding and standalone base64 before deterministic injection checks.
2. NeMo Guardrails 0.24.1 executes the configured input rail. A block stops before any Mesh call.
3. Presidio 2.2.x pattern recognizers replace supported PII in the user question and free-text context. Integer financial values and structured calculation fields are unchanged.
4. The typed LangGraph specialists call only `MeshClient`.
5. `MeshClient` applies the NeMo output rail and Presidio masking to every textual completion before Pydantic parses it.
6. The deterministic financial verifier independently checks evidence IDs, exact allowed amounts, currency and prohibited certainty before release.

The trace records policy versions, PII entity types and counts, but never the detected values. A rail exception fails the run closed.

## NeMo configuration

The active configuration is `apps/api/app/guardrails/nemo/config.yml`. It imports NVIDIA's built-in regex rails and enables input, output and retrieval definitions. The current application has no retrieval or model-callable tools, so retrieval remains configured for future grounded retrieval while the static `tool_policy` allowlist controls every declared agent role today.

NeMo has no model entry in the active configuration and therefore makes no inference call. This is deliberate: common rails are deterministic and low latency. Any later model-powered NeMo rail must use its built-in OpenAI-compatible client with `https://api.meshapi.ai/v1`, the server-side Mesh key and an approved Mesh model. A direct provider or NVIDIA-hosted model would violate the application boundary.

## Presidio minimization

The production path uses Presidio's recognizer and anonymizer APIs without downloading an NLP model. Recognizers cover email addresses, Indian phone numbers, PAN, Aadhaar when explicitly labelled, and bank account numbers when explicitly labelled. Context requirements reduce accidental masking of legitimate monetary values.

This is data minimization, not authoritative identity validation. Aadhaar checksum validation, names, postal addresses and multilingual free text are known gaps. Original authorized records remain tenant-scoped in PostgreSQL; only minimized copies enter model context.

## Measured evidence and limits

- 212 backend tests pass with 82% line coverage.
- The versioned deterministic matrix blocks 168/168 declared attacks and allows 16/16 declared legitimate controls.
- `pip-audit` reports no known vulnerabilities after pinning `cryptography` 50.0.2.
- Local cold guardrail initialization measured 2.22 seconds on the development machine.
- The Trixie-based local API image is 1,060,542,032 logical bytes (Docker Scout artifact size 226 MB); no Vercel deployment has been attempted or claimed. Current deployment work must measure the produced Python function bundle and use Vercel's Large Functions/Fluid compute path if the standard Python limit is exceeded.
- Bandit reports zero findings after explicit error handling replaced runtime assertions. Gitleaks found no secret in committed history. Docker Scout reports no high/critical application-package CVE, but one unfixed high zlib CVE remains in the Debian Trixie base and blocks an unconditional clean-image claim.

The matrix is not proof against unknown attacks. Model paraphrases, multilingual PII, split payloads across turns and novel encodings remain residual risks and require ongoing evaluation and human review.
