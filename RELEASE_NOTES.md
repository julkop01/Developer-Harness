# Developer Harness 1.1.0

Developer Harness 1.1 hardens the evidence and release path before the adapter and orchestration layers expand.

The runtime now uses high-resolution monotonic timing for bounded checks and interrupted receipts, avoiding the Windows/Python 3.11 timing flake found in hosted CI. Draft-release staging is tied to a successful full validation workflow for the exact source commit, and the staging environment regenerates `RELEASE_VALIDATION.json` from commands it actually executes.

The release remains dependency-free at runtime, local by default, model-neutral, and deliberately separate from host-owned model credentials, network permissions, sandboxes, scheduling, and independent reviewer identity.

Validation targets Python 3.11–3.13 on Linux, Windows, and macOS. The draft-release workflow never publishes a release; it only creates an explicit GitHub draft after current hosted evidence is green.

Begin with `START_HERE.md` or run `python examples/walkthrough.py`.
