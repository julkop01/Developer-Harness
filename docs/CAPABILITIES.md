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
| Night queue and operating playbook | Plan and instructions | No daemon, cron job, agent dispatch, or automatic merge |
| Codex/Claude/Gemini/Copilot entry files | Included text adapters | No claim that every host version auto-loads them identically |
| MCP/ACP/provider adapters | Extension contracts | No protocol server or live integration bundled |
| Cloud team collaboration | External host capability | No hosted control plane bundled |

Python 3.11–3.13, Linux/Windows/macOS are the CI target matrix. This distribution's local checks ran on the environment stated in VALIDATION.md; a configured matrix is not a passed hosted matrix.

No measured speedup, token-savings percentage, quality multiplier, or model-performance guarantee is claimed. Measure these on representative work before enabling an optimization.
