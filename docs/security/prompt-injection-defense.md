# Prompt-injection defense

FinPilot treats CSV text, questions, model output, and tool results as untrusted data. The deterministic input policy normalizes Unicode/full-width confusables, zero-width controls, HTML entities, repeated URL encoding, and Base64-like wrappers before matching instruction-override, secret-exfiltration, or tool-abuse patterns.

NeMo input/output rails provide an additional model-boundary policy; Presidio minimizes supported PII before Mesh transmission. Agents receive a fixed typed context and a static tool allowlist. Model output cannot choose credentials, tenant IDs, arbitrary URLs, database operations, or money movement. The independent verifier rejects ungrounded evidence, invented amounts, and prohibited certainty.

The versioned offline corpus currently measures 168 attack variants and 16 legitimate financial controls. All 184 passed in the recorded run, but this is a bounded regression result rather than a claim of universal immunity. The Mesh-powered attacker/grader evaluation remains `NOT_RUN` pending explicit egress approval.

