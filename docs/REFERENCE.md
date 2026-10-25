# CLI and configuration reference

All commands accept `--root PATH` before the command. `--json` forces JSON for restart packets too. With an installed overlay, replace `python dh.py` with `python .developer-harness/dh.py`.

Exit codes: **0** successful operation; **1** failed check or failing verification/audit; **2** invalid input, conflict, or unavailable operation; **130** interrupted session. JSON errors go to stderr. `--help` is the authoritative argument reference.

| Command | Purpose |
| --- | --- |
| `init --profile general` | Initialize a checkout workspace; preserve an existing config |
| `install [--apply] [--adapter claude]` | Plan or apply a repository-local overlay |
| `uninstall [--apply]` | Remove unchanged managed files/blocks; retain user data |
| `discover`, `profiles`, `capabilities` | Read the structure, starting profiles, and actual capability boundaries |
| `adapters` | List known AI coding hosts, instruction surfaces, supported canonical contracts, and whether a native bridge is actually implemented |
| `protocol list` | List the strict canonical host contracts and their fields |
| `protocol validate FILE` | Validate a repository-local JSON document against `dh.session.v1`, `dh.tool_event.v1`, `dh.context.v1`, `dh.permission.v1`, or `dh.mcp.v1` |
| `sessions ingest FILE` | Persist a validated session/tool/context/permission observation; session-bound records require a prior matching session |
| `sessions list`, `sessions show ID` | Inspect normalized host session snapshots |
| `host-events [--session ID] [--limit N]` | Inspect persisted normalized host events |
| `config` | Show validated configuration |
| `configure candidate.json [--apply]` | Validate a complete candidate; apply only when requested |
| `task new TITLE --objective TEXT --criterion TEXT --scope PATH --owner NAME` | Create a small acceptance contract; repeat criteria/scopes as needed |
| `task list`, `task show ID` | Read task state and version |
| `task move ID STATE --expect N --reason TEXT` | Guarded transition with optimistic concurrency |
| `run ID --check NAME --criterion c1 --expect N [--no-cache]` | Run a configured check; map it to acceptance criteria |
| `verify ID` | Evaluate the evidence gate without changing state |
| `evidence list ID` | List actual receipts and manual observations |
| `evidence add ID --expect N --artifact PATH --criterion c1 --statement TEXT --by NAME` | Attach a labeled manual attestation |
| `review ID --expect N --reviewer NAME --verdict pass --notes TEXT [--independent]` | Record a review, with explicit independence attestation |
| `checkpoint ID --expect N --summary TEXT --next TEXT [--blockers TEXT]` | Persist a restart point |
| `resume ID`, `context ID` | Bounded restart packet; optional `--include PATH`, `--output PATH`, `--max-chars N` |
| `recover ID --process-stopped --reason TEXT` | Mark abandoned running check records interrupted; never kill an unknown process |
| `lease acquire ID --owner NAME [--ttl 900]` | Advisory overlapping-scope detection |
| `lease release ID --owner NAME`, `lease list` | Release or inspect work reservations |
| `memory add CLAIM --source PATH --scope workspace [--ttl-days 30]` | Store a candidate with pinned provenance |
| `memory promote ID --reviewer NAME --uncertainty TEXT [--supersedes ID]` | Promote a current candidate; retain superseded history |
| `memory search QUERY [--scope NAME]`, `memory list` | Retrieve scoped decisions with freshness labels |
| `usage record --key ID --micros N --note TEXT`, `usage show` | Idempotent external-usage accounting; overages remain visible |
| `night-plan [--max-tasks 2]` | Plan a bounded low/normal-risk queue; no execution or scheduling |
| `backup --output PATH`, `export --output PATH` | Consistent SQLite backup or readable JSON export |
| `doctor`, `audit`, `status` | Integrity/configuration, current proof freshness, or operational summary |

## Configuration

The complete object lives in `.harness/config.json`. Unknown top-level fields are rejected. Version 1 uses these groups:

| Group | Defaults and meaning |
| --- | --- |
| `schema_version` | `1` |
| `name`, `purpose`, `profile` | Workspace identity, intended result, domain slug |
| `communication` | `language: en`, `detail: concise`, `experience: mixed`; instructions for the AI host |
| `workflow` | `mode: standard`, `max_active_tasks: 2`, `independent_review: false` |
| `limits.context_chars` | 16,000 characters, not tokens; 2,000–200,000 supported |
| `limits.max_checks_per_task` | 20 attempted checks; cached hits do not consume another attempt |
| `limits.max_task_seconds` | 1,800 cumulative runner seconds per task |
| `limits.max_log_bytes` | 131,072 retained output bytes; exceeding the limit fails the check |
| `limits.repeat_failure_limit` | 3 repeated failures for an unchanged check fingerprint |
| `limits.receipt_max_age_hours` | 24; current-proof audits can expire historical completion evidence |
| `budget` | Currency `EUR`, lifetime workspace `limit_micros: 0`; 1,000,000 micros = one unit |
| `commands` | Named argv arrays with timeout and description; empty until personalized |
| `required_checks` | Named checks that every task needs in addition to criterion coverage |
| `integrations` | Opt-in inventory: name, pinned version, purpose, owner, data boundary, rollback |

`light` encourages a shorter specification; it keeps evidence/review gates. `assured`, high-risk tasks, or `independent_review: true` require an independent review attestation. Profiles guide the AI's reasoning; they do not inspect compliance or certify a domain.

Example commands fragment to merge into the complete config:

```json
{
  "commands": {
    "test": {
      "argv": ["{python}", "-m", "unittest", "discover", "-s", "tests", "-v"],
      "timeout_seconds": 120,
      "description": "Run the actual Python regression suite"
    }
  },
  "required_checks": ["test"]
}
```

This fragment is documentation, not a complete candidate config. `{python}` is replaced only when it is a complete argument. No shell interpolation occurs. Commands run from the repository root with a small inherited environment. A Python/Node script can still execute arbitrary code, read disk, or use the network: configuration is trusted code and must be reviewed. Use the host sandbox for isolation.

## Scopes and exclusions

Scopes are repository-relative file paths or directory prefixes, not globs. `.` covers visible project files. Future files under a declared prefix are included. Private/generated paths, symlinks, and oversized source files have explicit handling. `.harnessignore` supports simple fnmatch patterns; `.gitignore` rules are evaluated by Git when available. Exclusions can hide dependencies; keep them narrow.

## Task transitions

`planned → active/blocked/cancelled`; `active → verifying/blocked/cancelled`; `verifying → active/review/blocked/cancelled`; `review → active/done/blocked/cancelled`; `blocked → planned/active/cancelled`; `done → active`; `cancelled → planned`.

Every transition takes a reason and current version. Evidence, review, and checkpoint operations require the current task version too. Attaching proof does not increment the task version. The acceptance contract is immutable in version 1: create a replacement task and cancel the old one when scope or criteria must change.


## Host adapter contracts

Version 1.2 separates host-specific event collection from the deterministic kernel. A native bridge must normalize host data into one of these contracts before later runtime layers may consume it:

- `dh.session.v1`: session identity, state, workspace, task/worktree association, and reported capabilities.
- `dh.tool_event.v1`: before/after/failure tool lifecycle observations.
- `dh.context.v1`: host-reported context usage, pressure, and compaction state.
- `dh.permission.v1`: permission requests and decisions as observations; a record never grants authority by itself.
- `dh.mcp.v1`: normalized MCP configuration metadata with environment key names only, never inline secret values.

The `adapters` command currently reports known host surfaces as `contract-ready` with `native_bridge: false`. This is intentional: instruction-file compatibility is not the same thing as a tested event bridge. Future native adapters must change that flag only with implementation and contract tests.


## Persistent host observations

Version 1.3 stores normalized host observations in the local SQLite authority. The database migration is additive: existing task, evidence, review, checkpoint, memory, usage, and event-chain data are retained while `host_sessions` and `host_events` are added.

Session snapshots are keyed by host session id. An id cannot change adapters, and an older `updated_at` snapshot cannot overwrite newer state. Session-bound events require the session to exist and must report the same adapter. Exact duplicate events are returned idempotently. Conflicting reuse of a source event identity is rejected.

These tables are observability state, not authority. They do not satisfy task criteria, approve permissions, authorize external actions, or establish reviewer independence. `dh.mcp.v1` remains validation-only until a separate persistent inventory/drift contract is implemented.


## MCP inventory and drift

Version 1.4 can persist validated `dh.mcp.v1` records with `mcp ingest FILE`. Each source is identified by adapter, scope, and server name. `mcp inventory` groups sources by logical server name and reports whether repeated configurations are consistent. `mcp drift` returns only multi-source servers whose effective signatures differ.

The signature covers transport plus command/arguments for stdio, or transport plus URL for remote MCP. Environment key names are metadata and are not part of the effective endpoint signature. Secret values are rejected before persistence: do not put credentials in args, URLs, or `env_keys` values.

This inventory is diagnostic only. It does not install, launch, enable, disable, or authorize MCP servers, and it does not read global host configuration automatically in 1.4.
