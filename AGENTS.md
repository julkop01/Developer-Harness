# Developer Harness contributor contract

Read the task and relevant source before editing. For personalization, follow `START_HERE.md`. For implementation, load only the relevant playbook under `developer_harness/resources/workflows/`.

- Preserve owner instructions and unrelated work. Keep explicit authorization attached to external actions.
- Write a small acceptance contract for substantial changes. Use proportional ceremony for tiny edits.
- Keep runtime dependencies in the Python standard library. No provider SDK, daemon, telemetry, or network service is required.
- Keep model reasoning separate from the deterministic ledger and check runner.
- Never call this runner a sandbox. Commands run with the current user's permissions.
- Never describe advisory leases, hash chaining, or reviewer name strings as security boundaries.
- Do not run parallel agents unless the user requests them. Single-agent use is fully supported.
- Match receipts to current source/configuration. Preserve failure exit codes. Label manual attestations and estimates.
- Update behavior docs with code. Run `python -m unittest discover -s tests -v` and `python scripts/release_check.py` for meaningful changes.
- Checkpoint and leave a concrete next step before a session boundary.

## Code review rules

Flag stale evidence acceptance, secret inclusion in context, broad overwrite/delete behavior in installation, shell execution added to the runner, unbounded output/retries, hidden network calls, and unsupported product claims. A passing command is insufficient if its acceptance mapping is wrong.
