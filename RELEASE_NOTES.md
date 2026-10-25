# Developer Harness 2.0.0

Developer Harness 2.0 introduces the first unified operator control-plane foundation while preserving the local, deterministic, model-neutral kernel.

The new `observe FILE` command routes any validated canonical host document to its authoritative local store: session/tool/context/permission observations enter the host ledger, while MCP records enter the MCP inventory. The `control-plane` command renders one read-only snapshot across task proof health, host sessions, latest context pressure, MCP fragmentation/drift, Git worktrees, advisory leases, budget state, and ledger integrity.

The projection is deliberately non-authoritative. It does not mutate task state, grant permissions, turn host observations into acceptance evidence, merge or delete worktrees, start MCP servers, schedule agents, or enforce provider spend.

Warnings surface stale completion proof, MCP drift, context pressure or compaction, worktree conflicts/dirty state, worktree unavailability, and ledger-integrity failures. Non-Git workspaces degrade safely instead of failing the entire operator view.

The 2.0 foundation remains standard-library-only at runtime and retains the fully validated 1.1–1.5 substrate underneath it.
