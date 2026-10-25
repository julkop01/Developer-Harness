# Developer Harness 1.2.0

Developer Harness 1.2 introduces the model-neutral host adapter substrate without pretending that native bridges already exist.

Five strict canonical contracts are now defined: `dh.session.v1`, `dh.tool_event.v1`, `dh.context.v1`, `dh.permission.v1`, and `dh.mcp.v1`. The CLI can list the supported contracts, list known host capability surfaces, and validate repository-local JSON documents against the contracts.

The initial host catalog covers Codex, Claude Code, OpenCode, Gemini CLI, Cursor, and GitHub Copilot. Every entry truthfully reports `native_bridge: false` until a real host integration with contract tests is implemented.

MCP records preserve environment variable names only and reject inline secret values. The adapter layer remains metadata and validation only; it grants no tool permissions, launches no agents, and does not bypass the existing deterministic task/evidence kernel.

Developer Harness 1.2 retains the 1.1 release-hardening guarantees and the Python 3.11–3.13 Linux/Windows/macOS validation target.
