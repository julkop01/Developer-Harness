# Load the playbook you need

The AI should read one relevant workflow at a time. The canonical, installed copies live with the runtime:

| Workflow | Use it for |
| --- | --- |
| [Deliver](../developer_harness/resources/workflows/deliver.md) | A meaningful feature, fix, or refactor |
| [Discover](../developer_harness/resources/workflows/discover.md) | Importing or understanding an existing codebase |
| [Debug](../developer_harness/resources/workflows/debug.md) | A failing check or unexpected behavior |
| [Research](../developer_harness/resources/workflows/research.md) | A consequential technical choice |
| [Review](../developer_harness/resources/workflows/review.md) | Acceptance, maintainability, and risk challenge |
| [Release](../developer_harness/resources/workflows/release.md) | Preparing a reviewable release |
| [Night shift](../developer_harness/resources/workflows/night-shift.md) | Bounded work in a host that supports unattended agents |

Installation/personalization is covered by [the onboarding protocol](../developer_harness/resources/START_HERE.md). Recovery is covered by [RECOVERY.md](../docs/RECOVERY.md).


## 2.0 operator surfaces

The playbooks remain intentionally small; 2.0 adds runtime visibility rather than hundreds of mandatory workflow files. Useful operator commands alongside any playbook are:

```bash
python dh.py control-plane
python dh.py adapters
python dh.py protocol list
python dh.py sessions list
python dh.py mcp inventory
python dh.py mcp drift
python dh.py worktrees
python dh.py worktrees --cleanup-plan
```

`control-plane` is a read-only composition of authoritative local state. Host observations remain telemetry, permission observations remain observations, and cleanup plans remain plans until an authorized operator or host explicitly acts.
