# What is implemented

| Feature | Status | Boundary |
| --- | --- | --- |
| Repository overlay and owner-rule preservation | Executable | Repository-local only; dry-run by default |
| Natural-language personalization | Included AI protocol | Executed by an AI host with file/terminal access |
| Profiles and strict configuration | Executable | No automatic stack-specific command authorization |
| Task ledger and gates | Executable | Local SQLite, current-version mutations |
| Proof receipts and stale detection | Executable | Explicit scoped fingerprint, not complete environment attestation |
| Check runner and exact successful reuse | Executable | Commands are trusted project code; no sandbox |
| Failure/attempt/time/output limits | Executable | Limits harness-mediated check runs; does not intercept host tools |
| Checkpoint and bounded context | Executable | Structured navigation; no LLM summarizer or tokenizer |
| Memory provenance, expiry, supersession | Executable | Local keyword retrieval; decisions remain reviewable claims |
| Advisory work leases | Executable | No filesystem locking against arbitrary editors |
| External-usage accounting | Executable | Manually supplied observations; no billing/spend interception |
| Canonical host contracts | Executable | Strict validation for session/tool/context/permission/MCP records; validation alone creates no authority |
| Host session/event ledger | Executable | Persistent normalized observations; tool/permission records are not acceptance evidence or authorization |
| MCP inventory and drift | Executable | Persistent local metadata; rejects secret-bearing values; does not launch/reconfigure servers |
| Git worktree lifecycle | Executable | Read-only status/conflict/cleanup planning; never merges, deletes, prunes, or checks out |
| Unified control plane | Executable | Read-only projection over authoritative stores; warnings only, no automatic corrective action |
| Night queue and operating playbook | Plan and instructions | No daemon, cron job, agent dispatch, or automatic merge |
| Codex/Claude/Gemini/Copilot entry files | Included text adapters | No claim that every host version auto-loads them identically |
| Native Codex/Claude/OpenCode/Gemini lifecycle bridges | Extension boundary | Canonical contracts exist; native event collectors are not yet bundled |
| Cloud team collaboration | External host capability | No hosted control plane bundled |

Python 3.11–3.13 on Linux, Windows, and macOS are the hosted CI target matrix. Release staging is gated on a successful hosted validation run for the exact source commit; packaged validation separately records commands executed in the staging environment.

No measured speedup, token-savings percentage, quality multiplier, or model-performance guarantee is claimed. Measure these on representative work before enabling an optimization.
