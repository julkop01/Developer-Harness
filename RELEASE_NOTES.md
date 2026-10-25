# Developer Harness 1.5.0

Developer Harness 1.5 adds read-only Git worktree lifecycle analysis and session-to-worktree visibility.

The harness can enumerate repository worktrees, classify base/dirty/merged/merge-ready/conflict/stale/idle states, report ahead/behind counts, use `git merge-tree` for non-mutating conflict prediction, and associate normalized host sessions with their declared worktree path.

`worktrees --cleanup-plan` produces a conservative plan only. It never removes a worktree, deletes a branch, merges code, or launches an agent. Dirty, locked, conflicting, active-session, and otherwise unproven worktrees remain in the keep set.

This release builds on the 1.4 MCP inventory and the 1.3 host session ledger while keeping the deterministic task/evidence kernel authoritative.
