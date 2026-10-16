# Promptfoo security evaluation

FinPilot has two intentionally separate Promptfoo lanes.

- `promptfooconfig.quick.yaml` executes the versioned 184-case deterministic input-policy
  matrix without network or model inference. It is safe for pull requests.
- `promptfooconfig.redteam.yaml` performs authorized model-based attack generation and grading.
  Both model roles use the OpenAI-compatible Mesh endpoint and the `MESH_API_KEY` environment
  variable. The configuration disables result sharing. Do not run it against data or systems
  outside your authorization.

Use the pinned Promptfoo container so the host Node version does not affect reproducibility:

```bash
docker run --rm \
  -v "$PWD:/workspace" \
  -w /workspace/evaluation/promptfoo \
  ghcr.io/promptfoo/promptfoo:0.124.1 \
  promptfoo validate config -c promptfooconfig.quick.yaml -c promptfooconfig.redteam.yaml
```

Run the offline PR lane:

```bash
docker run --rm \
  -v "$PWD:/workspace" \
  -w /workspace/evaluation/promptfoo \
  -e PROMPTFOO_PYTHON=/workspace/apps/api/.venv/bin/python \
  -e PROMPTFOO_DISABLE_TELEMETRY=true \
  ghcr.io/promptfoo/promptfoo:0.124.1 \
  promptfoo eval -c promptfooconfig.quick.yaml --no-cache
```

The model-based lane additionally requires explicit data-egress authorization and a scoped
`MESH_API_KEY`. Set both `PROMPTFOO_DISABLE_REMOTE_GENERATION=true` and
`PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION=true` when invoking it so Promptfoo-hosted
generation cannot be selected. Its plugins use the configured attacker/grader and its strategies
are local deterministic transforms; remote-only plugins and strategies are intentionally absent.
Never pass an OpenAI, Anthropic, or other direct-provider key.
