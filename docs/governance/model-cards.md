# FinPilot AI component cards

## Mesh advice model

- Identifier: configured `MESH_MODEL`; current local default is `openai/gpt-5.4-mini`.
- Purpose: bounded semantic analysis and recommendation drafting after deterministic forecasting.
- Gateway: Mesh API only; direct provider fallback is forbidden.
- Inputs: minimized, tenant-authorized snapshot/scenario evidence and a user question.
- Outputs: typed findings and draft recommendations; these are not released before deterministic verification.
- Limitations: may hallucinate, misread sparse histories, or produce unsafe certainty. It does not perform financial arithmetic or move money.

## Deterministic financial stack

- Purpose: transaction normalization, recurrence/anomaly analysis, forecasts, scenarios, and independent advice verification.
- Numeric representation: integer minor units.
- Controls: immutable snapshots, chronological tests, evidence allowlists, and fail-closed verification.
- Limitations: forecasts reflect recorded history and explicit assumptions, not unknown future events.

## Guardrail stack

- Components: deterministic input/tool policy, NeMo Guardrails, Presidio minimization, output policy, and static tool allowlists.
- Evaluation: offline Promptfoo corpus passed 184/184; this bounded result is not an immunity claim.
- Open gate: model-based Mesh red-team evaluation is `NOT_RUN` pending explicit egress approval.

