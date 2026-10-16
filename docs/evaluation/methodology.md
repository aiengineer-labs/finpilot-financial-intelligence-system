# Evaluation methodology

FinPilot separates deterministic correctness tests from probabilistic model evaluations. This
prevents model variance from hiding failures in authorization, tenant isolation, financial math,
or input safety.

## Security lanes

The pull-request lane runs `evaluation/promptfoo/promptfooconfig.quick.yaml`. Its versioned CSV
contains direct and wrapped attacks transformed with zero-width characters, full-width Unicode,
HTML entities, URL encoding, and Base64, plus legitimate financial phrases used to measure false
positives. The provider imports the same `assess_untrusted_text` function used by the application.
It performs no model requests.

The scheduled/manual lane uses `promptfooconfig.redteam.yaml`. The target remains FinPilot's local
input boundary; model-based probe generation and grading are both configured as
`openai:chat:openai/gpt-5.4-mini` with `apiBaseUrl=https://api.meshapi.ai/v1` and
`apiKeyEnvar=MESH_API_KEY`. Direct provider fallbacks are disabled. Promptfoo result sharing and
remote generation must remain disabled. Only authorized synthetic data may be used.

## Interpretation

Attack success rate is `successful attacks / attempted attacks`; for the deterministic matrix a
missed block is a successful attack. False-positive rate is `blocked benign cases / benign cases`.
Results apply only to the named dataset, code revision, tool version, and configured policy. A zero
rate is not evidence of universal immunity.
