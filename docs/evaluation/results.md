# Evaluation results

## Prompt-injection quick regression — 2026-10-16

- Dataset: `evaluation/security/prompt_injection_cases.csv`
- Runner: Promptfoo 0.124.1, pinned container digest recorded in the JSON report
- Cases: 168 adversarial, 16 benign, 184 total
- Result: 184 passed, 0 failed, 0 errors
- Measured attack success rate: 0/168 (0%) on this bounded dataset
- Measured benign false-positive rate: 0/16 (0%) on this bounded dataset
- Duration reported by Promptfoo: 2,125 ms
- Model calls and tokens: 0

The machine-readable evidence is in
`evaluation/reports/promptfoo-quick-2026-10-16.json`. The model-based red-team configuration was
schema-validated but not executed because external Mesh egress requires explicit authorization in
the controlled environment. No result is claimed for that lane.
