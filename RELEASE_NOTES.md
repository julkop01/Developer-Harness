# Developer Harness 1.3.0

Developer Harness 1.3 turns the 1.2 host contracts into persistent, auditable local observations.

Validated `dh.session.v1` snapshots can now be ingested into the authoritative SQLite ledger. Session-bound `dh.tool_event.v1`, `dh.context.v1`, and `dh.permission.v1` records are accepted only after a matching session snapshot exists and only when the adapter identity matches. Exact duplicate events are idempotent; reused source identities with different content are rejected.

The ledger migrates non-destructively from schema version 1 to 2 by adding `host_sessions` and `host_events`. Exports include the normalized host state, and `status` reports host session/event counts. New CLI commands provide session ingest/list/show and normalized event inspection.

Host observations remain separate from task evidence. A tool event, permission observation, or session status can never satisfy an acceptance criterion or grant authority merely by being present in the ledger.

Persistent MCP inventory remains deliberately deferred; `dh.mcp.v1` is validation-only in this release.
