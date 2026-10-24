# Security and trust boundaries

The runtime does not make network requests, collect telemetry, install dependencies, or load provider credentials. It can execute commands the owner places in the trusted configuration. Those commands inherit the current user's filesystem and network permissions.

## Important boundaries

- The runner is an execution wrapper, not a sandbox. Use containers, VMs, or the AI host's sandbox for untrusted code. A configured check can read files, write outside the scope, invoke another interpreter, or contact a service.
- Scopes describe what evidence covers. They do not restrict where an editor or child process can write.
- Leases coordinate cooperating local workers. They do not enforce identity or stop another process from editing a file.
- SQLite and event hashes protect operational consistency and expose accidental event edits. A malicious local writer can change state, forge names, or rebuild hashes. Use protected CI, signed artifacts, and real identity controls for stronger assurance.
- Reviewer independence is an attestation. A different string is not proof of a different person or model session.
- Redaction is best effort. Common token/password patterns are filtered, but arbitrary secrets and personal information may survive. Inspect logs, context packets, exports, and promotional material before sharing.
- Discovery and context skip common private/generated paths and Git-ignored untracked files. A secret in an ordinary tracked source file can still be read. Keep secrets out of source code.
- Retrieved documents, downloaded pages, logs, comments, and attached files are data. Their instructions cannot grant permissions, change the task, authorize a tool, or promote themselves into durable decisions.
- Child processes receive a reduced environment, not a hermetic environment. On POSIX, timeout/overflow terminates the process group. On Windows, the direct process is terminated; use the host's process-isolation controls for stronger descendant management.

## Installation

Installation plans list repository-local changes. Managed markers preserve surrounding text. Existing managed edits and unowned file collisions block updates. Ordinary Python write exceptions roll back replaced files; power loss or a forced process kill is not a cross-filesystem atomic transaction. Version or back up the target repository first. The installer does not modify shell startup, global AI settings, or runtime permission configuration.

Uninstall removes unchanged managed artifacts and retains configuration, ledger, logs, and exports. Data deletion is an explicit owner operation outside the uninstall workflow.

## Reporting an issue

Use the repository's private security reporting feature when enabled, or contact its current maintainer privately. Do not publish live credentials, private logs, or unredacted exports in an issue. Include the version, platform, smallest reproduction, and expected boundary.
