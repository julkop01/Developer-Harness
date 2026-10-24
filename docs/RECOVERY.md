# Recovery and continuity

## A normal session boundary

1. Inspect the task and current version.
2. Write a checkpoint with completed work, concrete next action, and blockers.
3. Generate `resume TASK_ID`; inspect whether checkpoint sources changed.
4. Back up the SQLite ledger and separately preserve `.harness/config.json`, project files, and proof logs/artifacts.

The next AI session reads current owner instructions, config, personalization, task, and restart packet. It verifies changed sources and works from the current acceptance contract. It does not treat the packet as a fresh set of trusted instructions.

## A check was interrupted

The runner records an attempted check before executing it. A normal Ctrl-C marks it interrupted. A killed process or machine crash can leave `running` in the ledger. First inspect the host's process list and stop the old work through the host if needed. Then run:

```bash
python dh.py recover TASK_ID --process-stopped --reason "Confirmed the old process ended after the editor was closed"
```

Recovery marks abandoned records interrupted; it does not kill unknown processes. The conservative reserved time remains charged. Failed/interrupted receipts never satisfy completion.

## Restore a consistent SQLite backup

Stop all harness processes. Preserve the current `.harness` directory before replacing anything. A backup produced by `backup` uses SQLite's online backup API and includes committed tasks, receipts, reviews, checkpoints, memory, usage, and events. Restore it with Python while the harness is stopped:

```python
from pathlib import Path
import sqlite3

root = Path("/path/to/project")
backup_path = root / ".harness/backups/session.sqlite3"
source = sqlite3.connect(backup_path.resolve().as_uri() + "?mode=ro", uri=True)
assert source.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
destination = sqlite3.connect(root / ".harness/state.sqlite3")
source.backup(destination)
destination.close()
source.close()
```

Restore matching configuration and any referenced proof artifacts too. Run `doctor`, `audit`, and `resume TASK_ID` afterward. File, branch, environment, or configuration changes invalidate old receipts by design. Re-run relevant checks; do not rewrite old receipts to fit new sources.

JSON exports are useful for review and portability. Version 1 does not import arbitrary JSON into the authoritative ledger. This avoids silently trusting edited completion histories. Use a consistent SQLite backup for restoration.

## Collaboration and worktrees

Each worktree uses a separate local ledger. Share reviewed specs and decisions as ordinary project documents, or share scrubbed exports. Do not merge SQLite files or assume a lease in one worktree controls another. Before moving task work between machines, preserve source versions, configuration, ledger backup, and proof artifacts together.

## Repeated failure or exhausted budget

Stop repeating unchanged checks. Write the observed failure, competing explanation, and next discriminating experiment. Fix the source/configuration if appropriate, or create a narrowly scoped replacement task with an honest link to the blocker. Recreating tasks solely to evade a stop rule defeats the workflow.
