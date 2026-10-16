# Drift and quality monitoring

The evaluation registry records dataset/version, sampling method, metrics, thresholds, duration, code/model versions, failures, and reviewer disposition. The current reproducible baseline is the exhaustive 184-case prompt-injection corpus; the separate Mesh model red team is intentionally not reported as passed.

Planned production observations are categorization correction/error rate, category-distribution shift, chronological forecast MAE and interval coverage, verifier rejection and human-intervention rates, guardrail attack-success and benign false-positive rates, model cost, token use, and p50/p95 latency. Alerts must use minimum sample sizes and distinguish input distribution shift from proven quality regression.

Until durable observations are implemented, the UI reports no drift alerts rather than inventing telemetry. A failed required evaluation blocks artifact promotion; a critical runtime control failure withholds AI advice.

