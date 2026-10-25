"""Read-only operator control-plane projection and unified observation ingress."""
from __future__ import annotations

import json
from pathlib import Path

from . import adapters, config, engine, mcp_inventory, sessions, worktrees
from .store import Store
from .util import HarnessError, now


def ingest(store: Store, document: dict) -> dict:
    """Route one validated canonical host document to its authoritative local store."""
    record = adapters.validate(document)
    if record["schema"] == "dh.mcp.v1":
        return mcp_inventory.ingest(store, record)
    return sessions.ingest(store, record)


def _latest_context_pressure(store: Store) -> list[dict]:
    latest: dict[str, dict] = {}
    rows = store.db.execute(
        "SELECT data FROM host_events WHERE schema='dh.context.v1' ORDER BY rowid"
    )
    for row in rows:
        record = json.loads(row["data"])
        latest[record["session_id"]] = record
    return [
        {
            "session_id": session_id,
            "adapter": record["adapter"],
            "pressure": record["pressure"],
            "compacting": record["compacting"],
            "used": record.get("used"),
            "limit": record.get("limit"),
            "unit": record["unit"],
            "timestamp": record["timestamp"],
        }
        for session_id, record in sorted(latest.items())
    ]


def snapshot(store: Store, base: str = "main", stale_days: int = 7) -> dict:
    root = store.root
    cfg = config.load(root)
    tasks = store.tasks()
    task_rows = []
    for task in tasks:
        proof = engine.gate(store, task)
        task_rows.append({
            "id": task["id"],
            "title": task["title"],
            "state": task["state"],
            "version": task["version"],
            "owner": task["owner"],
            "risk": task["risk"],
            "proof_ok": proof["ok"],
            "missing_proof": proof["missing"],
        })

    mcp = mcp_inventory.inventory(store)
    host_sessions = sessions.sessions(store)
    context_pressure = _latest_context_pressure(store)
    try:
        worktree_state = worktrees.report(root, base, stale_days, store)
        worktree_error = None
    except HarnessError as exc:
        worktree_state = None
        worktree_error = str(exc)

    leases = [
        {
            "task_id": row["task_id"],
            "owner": row["owner"],
            "expires": row["expires"],
            "scopes": json.loads(row["scopes"]),
        }
        for row in store.db.execute("SELECT * FROM leases ORDER BY task_id")
    ]

    warnings = []
    stale_done = [item["id"] for item in task_rows if item["state"] == "done" and not item["proof_ok"]]
    if stale_done:
        warnings.append({"kind": "stale-completion-proof", "tasks": stale_done})
    if mcp["aggregates"]["drifted_servers"]:
        warnings.append({"kind": "mcp-drift", "count": mcp["aggregates"]["drifted_servers"]})
    pressured = [item["session_id"] for item in context_pressure
                 if item["pressure"] in {"high", "critical"} or item["compacting"]]
    if pressured:
        warnings.append({"kind": "context-pressure", "sessions": pressured})
    if worktree_state and worktree_state["aggregates"]["conflicts"]:
        warnings.append({"kind": "worktree-conflicts", "count": worktree_state["aggregates"]["conflicts"]})
    if worktree_state and worktree_state["aggregates"]["dirty"]:
        warnings.append({"kind": "dirty-worktrees", "count": worktree_state["aggregates"]["dirty"]})
    if worktree_error:
        warnings.append({"kind": "worktree-unavailable", "detail": worktree_error})

    integrity = store.audit()
    if not integrity["ok"]:
        warnings.append({"kind": "ledger-integrity", "errors": integrity["errors"]})

    return {
        "schema": "dh.control-plane.v1",
        "generated_at": now(),
        "workspace": {
            "name": cfg["name"],
            "profile": cfg["profile"],
            "workflow_mode": cfg["workflow"]["mode"],
            "integrity": integrity["ok"],
        },
        "summary": {
            "tasks": len(task_rows),
            "active_tasks": sum(item["state"] in {"active", "verifying", "review"} for item in task_rows),
            "blocked_tasks": sum(item["state"] == "blocked" for item in task_rows),
            "host_sessions": len(host_sessions),
            "host_events": store.db.execute("SELECT count(*) FROM host_events").fetchone()[0],
            "mcp_sources": mcp["aggregates"]["source_records"],
            "mcp_drift": mcp["aggregates"]["drifted_servers"],
            "leases": len(leases),
            "warnings": len(warnings),
        },
        "tasks": task_rows,
        "sessions": host_sessions,
        "context_pressure": context_pressure,
        "mcp": mcp,
        "worktrees": worktree_state,
        "leases": leases,
        "budget": engine.budget(store),
        "warnings": warnings,
        "authority": {
            "read_only_projection": True,
            "host_observations_are_evidence": False,
            "permission_records_grant_authority": False,
            "automatic_actions": False,
        },
    }
