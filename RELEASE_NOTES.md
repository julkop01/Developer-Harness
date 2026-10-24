# Developer Harness 1.0.0

A universal local workflow layer for the AI coding tools developers already use. Describe your work to your AI, then let it inspect, install, and personalize the harness inside your repository.

This release includes a dependency-free Python runtime, safe repository overlay, six profiles, acceptance contracts, transactional task history, source-bound verification receipts, current review gates, bounded check execution, failure-loop stops, exact-success reuse, checkpoints, governed memory, backups, and focused engineering playbooks.

Release artwork includes a GitHub banner and an X flyer. Original research notes cite primary harness/framework documentation; private source inputs and project identifiers are excluded.

Validation details and actual local results are included in `RELEASE_VALIDATION.json` and `docs/VALIDATION.md`. Hosted CI status is reported by GitHub after a push. The runtime does not bundle an LLM client, autonomous scheduler, sandbox, hosted service, or provider-budget enforcement.

Requirements: Python 3.11+. Git optional. License: MIT.

An opt-in GitHub Actions workflow can validate, package, and stage a draft release from an explicit release/stage-* branch or manual dispatch. It never publishes the release.

Begin with `START_HERE.md` or run `python examples/walkthrough.py`.
