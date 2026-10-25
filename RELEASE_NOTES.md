# Developer Harness 1.4.0

Developer Harness 1.4 adds persistent normalized MCP inventory and cross-host drift detection.

Validated `dh.mcp.v1` records can now be stored in the local SQLite authority, keyed by adapter, scope, and logical server name. The harness computes a stable configuration signature and distinguishes ordinary fragmentation (the same server configured in multiple hosts) from actual drift (different effective transports/commands/URLs).

Secret-bearing MCP values are rejected before persistence. Environment variable names are allowed, but inline values, secret-looking command arguments, credential userinfo, and credential query parameters are not accepted.

New `mcp ingest`, `mcp list`, `mcp inventory`, and `mcp drift` commands expose the inventory without granting the MCP servers any authority. Ledger schema version 3 adds the inventory table and exports normalized MCP state.

This remains local metadata and drift detection. Developer Harness still does not start MCP servers, install them, copy credentials, or modify host configuration automatically.
