# Contribute

Read [AGENTS.md](AGENTS.md). Keep proposals small, explain the user problem, and provide evidence for behavioral or boundary changes. Preserve the dependency-free runtime unless a separately reviewed decision demonstrates the benefit.

Run the unit/integration tests, complete example, and release structure check. Add regression coverage for real failure modes. Avoid tests that merely duplicate code or count documents. Mark platform-specific checks and untested external integrations honestly.

Configuration/schema changes need compatibility notes. Installer changes need existing-repository, conflict, rollback, and uninstall checks. Runner changes need failure, timeout, output, and stale-evidence cases. Memory changes need provenance and supersession checks.

Use semantic versioning for public CLI/configuration contracts. Avoid force-pushing shared branches and retain owner changes. Never commit runtime state, proof logs, private input repositories, credentials, or personal task exports.
