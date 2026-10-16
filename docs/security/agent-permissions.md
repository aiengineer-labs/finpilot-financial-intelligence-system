# Agent permissions

| Component | Permitted | Forbidden |
|---|---|---|
| Supervisor | Route within the bounded graph | Database, network, credentials, tool expansion |
| Behavior analyst | Read minimized deterministic context; call Mesh adapter | Arithmetic authority, writes, arbitrary tools |
| Financial advisor | Draft typed recommendations from supplied evidence | Money movement, invented evidence, policy changes |
| Critic | Review a draft and request one bounded revision | Infinite loops, direct release |
| Verifier | Read calculated values and accept/revise/reject in code | Model calls, bypass by human/model |
| Digest dispatcher | Claim due persisted rows and create in-app notifications | Model calls, tenant IDs from request, external messaging |

The static policy explicitly sets money movement to false. No current feature can transfer funds, trade, purchase, alter bank data, execute shell commands, or browse arbitrary destinations. Governance drafts do not affect runtime until independently approved and all release gates pass.

