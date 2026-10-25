# Changelog

## 1.4.0 — 2026-10-25

Added persistent MCP inventory and cross-host drift detection.

- Added SQLite schema v3 MCP source inventory.
- Added stable logical configuration signatures.
- Distinguished duplicated/fragmented configuration from inconsistent drift.
- Added MCP inventory and drift CLI surfaces.
- Rejected secret-looking command arguments, secret flag values, URL userinfo, and credential query parameters before persistence.
- Kept MCP inventory observational: it does not start servers or grant capabilities.

## 1.3.0 — 2026-10-25

Added persistent normalized host session and event observations.

- Added non-destructive SQLite schema v2 migration with host session/event tables.
- Added validated session snapshot upsert with adapter identity and monotonic timestamp checks.
- Added idempotent tool/context/permission event ingestion with source-key conflict detection.
- Added session/event CLI inspection and host counts in status.
- Included normalized host state in exports.
- Kept host observations strictly separate from acceptance evidence and authorization.
- Kept MCP persistence deferred rather than silently overclaiming inventory support.

## 1.2.0 — 2026-10-25

Introduced the canonical host-adapter substrate.

- Added strict versioned session, tool-event, context, permission, and MCP contracts.
- Added a truthful host capability registry for Codex, Claude Code, OpenCode, Gemini CLI, Cursor, and Copilot.
- Added CLI surfaces for adapter discovery and protocol validation.
- Reject unknown fields, unknown adapters, invalid enumerations, and MCP environment values containing secrets.
- Added dedicated adapter contract tests.
- Native bridges remain explicitly unimplemented until separately integrated and tested.

## 1.1.0 — 2026-10-25

Hardening release focused on trustworthy release evidence and cross-platform determinism.

- Use high-resolution monotonic timing for check and interruption receipts.
- Remove the Windows/Python 3.11 timing-flake assumption from interruption regression testing.
- Stage draft releases only after a successful full hosted validation workflow for the exact source commit.
- Regenerate packaged release validation from commands actually executed during staging.
- Bind release notes to the package version during deterministic release checks.

## 1.0.0 — 2026-10-24

Initial release of Developer Harness: a universal local workflow layer for an existing AI coding tool.

- Conversation-led installation and six starting profiles.
- Repository-local overlay with dry-run, managed-block preservation, conflict detection, and uninstall.
- Transactional task ledger, current-version mutations, dependency and completion gates.
- Source/configuration-bound check receipts, exact-success reuse, bounded execution, and repeated-failure circuit.
- Current review requirements, manual observation labels, checkpoints, bounded restart packets, and consistent backups.
- Scoped memory candidates/decisions with provenance, expiry, uncertainty, and supersession.
- Advisory work leases, idempotent external-usage accounting, and bounded unattended-work planning.
- Seven focused workflows, reusable templates, primary-source design research, CI, and release artwork.

No bundled LLM client, provider gateway, crawler, scheduler daemon, protocol server, or security sandbox. These remain explicit host/integration responsibilities.
