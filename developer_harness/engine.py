"""Contracts, guarded state changes, evidence freshness, leases, and learning."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import platform
import time

from . import config as configuration
from .store import Store, new_id
from .util import HarnessError, canonical, digest, file_hash, now, relative_path, safe_path, sensitive, snapshot

TRANSITIONS = {
    "planned": {"active", "blocked", "cancelled"},
    "active": {"verifying", "blocked", "cancelled"},
    "verifying": {"active", "review", "blocked", "cancelled"},
    "review": {"active", "done", "blocked", "cancelled"},
    "blocked": {"planned", "active", "cancelled"},
    "done": {"active"},
    "cancelled": {"planned"},
}


def nonempty(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HarnessError(f"{name} cannot be empty.")
    return value.strip()


def expect(task: dict, version: int):
    if task["version"] != version:
        raise HarnessError(f"Version conflict: expected {version}, current {task['version']}. Reload the task.")


def new_task(store: Store, title: str, objective: str, criteria: list[str], scopes: list[str],
             owner: str, risk: str = "normal", dependencies: list[str] | None = None) -> dict:
    config = configuration.load(store.root)
    if risk not in {"low", "normal", "high"}:
        raise HarnessError("Risk must be low, normal, or high.")
    if not criteria or not scopes:
        raise HarnessError("At least one acceptance criterion and explicit path scope are required.")
    scopes = sorted(set(relative_path(s, True) for s in scopes))
    for scope in scopes:
        safe_path(store.root, scope, True)
        if sensitive(scope):
            raise HarnessError(f"Sensitive/generated scope is excluded: {scope}")
    dependencies = sorted(set(dependencies or []))
    task_id = new_id("task")
    task = {"title": nonempty(title, "Title"), "objective": nonempty(objective, "Objective"),
            "owner": nonempty(owner, "Owner"), "risk": risk, "created_at": now(),
            "criteria": [{"id": f"c{i + 1}", "text": nonempty(c, "Criterion")} for i, c in enumerate(criteria)],
            "scopes": scopes, "dependencies": dependencies, "profile": config["profile"]}
    with store.transaction():
        for dependency in dependencies:
            store.get(dependency)
        # Dependencies must preexist, so new-task insertion cannot introduce a cycle.
        store.db.execute("INSERT INTO tasks VALUES(?,?,?,?)", (task_id, 1, "planned", canonical(task)))
        store.event("task.created", task_id, task)
    return store.get(task_id)


def contract(task: dict) -> dict:
    return {key: task[key] for key in ("id", "title", "objective", "criteria", "scopes", "dependencies", "risk", "profile")}


def fingerprint(root: Path, task: dict, config: dict | None = None) -> dict:
    config = config or configuration.load(root)
    source = snapshot(root, task["scopes"])
    value = {"contract": digest(contract(task)), "sources": source["sha256"],
             "config": configuration.config_hash(config),
             "environment": {"python": platform.python_version(), "system": platform.system(), "machine": platform.machine()}}
    return {**value, "sha256": digest(value), "files": source["files"], "git": source["git"]}


def fresh(record: dict, current: dict, config: dict, root: Path) -> bool:
    if record.get("status") != "passed" or record.get("fingerprint", {}).get("sha256") != current["sha256"]:
        return False
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(record["created_at"])
        if age.total_seconds() < -60 or age > timedelta(hours=config["limits"]["receipt_max_age_hours"]):
            return False
        artifact = record.get("artifact")
        if artifact and file_hash(safe_path(root, artifact)) != record.get("artifact_sha256"):
            return False
    except (ValueError, OSError, HarnessError, TypeError):
        return False
    return True


def gate(store: Store, task: dict) -> dict:
    config = configuration.load(store.root)
    current = fingerprint(store.root, task, config)
    records = store.records("evidence", task["id"])
    latest_checks = {}
    for record in records:
        if record.get("kind") == "check" and record.get("fingerprint", {}).get("sha256") == current["sha256"]:
            latest_checks[record["command"]] = record
    valid = [e for e in records if fresh(e, current, config, store.root)
             and (e.get("kind") != "check" or latest_checks.get(e["command"], {}).get("id") == e["id"])]
    missing = []
    for command, record in latest_checks.items():
        if record.get("status") != "passed":
            missing.append(f"Unresolved check {command}: {record.get('status')}")
    for criterion in task["criteria"]:
        if not any(criterion["id"] in e.get("criteria", []) for e in valid):
            missing.append("Evidence for " + criterion["id"] + ": " + criterion["text"])
    for command in config["required_checks"]:
        if not any(e.get("kind") == "check" and e.get("command") == command for e in valid):
            missing.append("Required check: " + command)
    for dependency in task["dependencies"]:
        if store.get(dependency)["state"] != "done":
            missing.append("Unfinished dependency: " + dependency)
    return {"ok": not missing, "missing": missing, "valid_evidence": [e["id"] for e in valid], "fingerprint": current["sha256"]}


def transition(store: Store, task_id: str, state: str, version: int, reason: str) -> dict:
    reason = nonempty(reason, "Transition reason")
    with store.transaction():
        task = store.get(task_id)
        expect(task, version)
        if state not in TRANSITIONS[task["state"]]:
            raise HarnessError(f"Invalid transition: {task['state']} -> {state}")
        config = configuration.load(store.root)
        if state == "active":
            unfinished = [d for d in task["dependencies"] if store.get(d)["state"] != "done"]
            if unfinished:
                raise HarnessError("Finish dependencies before starting: " + ", ".join(unfinished))
            others = [t for t in store.tasks() if t["state"] in {"active", "verifying", "review"} and t["id"] != task_id]
            if len(others) >= config["workflow"]["max_active_tasks"]:
                raise HarnessError("Active task limit reached. Finish, block, or cancel an existing task.")
        if state in {"review", "done"}:
            result = gate(store, task)
            if not result["ok"]:
                raise HarnessError("Evidence gate blocked: " + "; ".join(result["missing"]))
        if state == "done":
            reviews = store.records("reviews", task_id)
            current = fingerprint(store.root, task, config)["sha256"]
            required_independent = config["workflow"]["independent_review"] or config["workflow"]["mode"] == "assured" or task["risk"] == "high"
            # The latest review for this fingerprint supersedes earlier reviews.
            matching = [r for r in reviews if r["fingerprint"] == current]
            latest = matching[-1] if matching else None
            if not latest or latest["verdict"] != "pass" or (required_independent and not latest["independent"]):
                raise HarnessError("A current passing review is required; high risk/assured tasks require an independent reviewer.")
        before = task["state"]
        task["state"] = state
        store.update(task, version)
        store.event("task.transition", task_id, {"from": before, "to": state, "reason": reason, "version": version + 1})
    return store.get(task_id)


def selected_criteria(task: dict, criteria: list[str]) -> list[str]:
    known = {c["id"] for c in task["criteria"]}
    if not criteria or not set(criteria) <= known:
        raise HarnessError("Evidence must name existing criterion IDs, e.g. --criterion c1.")
    return sorted(set(criteria))


def add_evidence(store: Store, task_id: str, version: int, artifact: str, criteria: list[str],
                 statement: str, attested_by: str) -> dict:
    with store.transaction():
        task = store.get(task_id)
        expect(task, version)
        if task["state"] not in {"active", "verifying"}:
            raise HarnessError("Attach evidence while active or verifying.")
        path = relative_path(artifact)
        if sensitive(path):
            raise HarnessError("Do not attach private/generated files as manual evidence; use a scrubbed project proof file.")
        record = {"task_id": task_id, "kind": "manual", "status": "passed", "created_at": now(),
                  "artifact": path, "artifact_sha256": file_hash(safe_path(store.root, path)),
                  "criteria": selected_criteria(task, criteria), "statement": nonempty(statement, "Statement"),
                  "attested_by": nonempty(attested_by, "Attestor"), "fingerprint": fingerprint(store.root, task)}
        record_id = new_id("proof")
        store.db.execute("INSERT INTO evidence VALUES(?,?,?,?,?)", (record_id, task_id, "manual", record["created_at"], canonical(record)))
        store.event("evidence.manual_attestation", task_id, {"id": record_id, "attested_by": attested_by, "artifact": path})
    return {"id": record_id, **record, "note": "Human/agent attestation, not an automatically verified semantic claim."}


def review(store: Store, task_id: str, version: int, reviewer: str, verdict: str, notes: str, independent: bool = False) -> dict:
    with store.transaction():
        task = store.get(task_id)
        expect(task, version)
        if task["state"] != "review":
            raise HarnessError("Move the task to review after verification first.")
        reviewer = nonempty(reviewer, "Reviewer")
        if verdict not in {"pass", "fail"}:
            raise HarnessError("Review verdict must be pass or fail.")
        if independent and reviewer.casefold() == task["owner"].casefold():
            raise HarnessError("An independent review cannot use the builder's identity.")
        record = {"task_id": task_id, "reviewer": reviewer, "verdict": verdict,
                  "notes": nonempty(notes, "Review notes"), "independent": bool(independent),
                  "created_at": now(), "fingerprint": fingerprint(store.root, task)["sha256"]}
        record_id = new_id("review")
        store.db.execute("INSERT INTO reviews VALUES(?,?,?)", (record_id, task_id, canonical(record)))
        store.event("task.reviewed", task_id, {"id": record_id, "verdict": verdict, "independent_attestation": independent})
    return {"id": record_id, **record}


def checkpoint(store: Store, task_id: str, version: int, summary: str, next_step: str, blockers: str = "none") -> dict:
    with store.transaction():
        task = store.get(task_id)
        expect(task, version)
        record = {"task_id": task_id, "task_version": version, "created_at": now(),
                  "summary": nonempty(summary, "Summary"), "next_step": nonempty(next_step, "Next step"),
                  "blockers": nonempty(blockers, "Blockers"), "fingerprint": fingerprint(store.root, task)}
        record_id = new_id("checkpoint")
        store.db.execute("INSERT INTO checkpoints VALUES(?,?,?,?)", (record_id, task_id, record["created_at"], canonical(record)))
        store.event("task.checkpoint", task_id, {"id": record_id, "task_version": version})
    return {"id": record_id, **record}


def overlap(a: list[str], b: list[str]) -> bool:
    return any(x == "." or y == "." or x == y or x.startswith(y + "/") or y.startswith(x + "/") for x in a for y in b)


def lease(store: Store, task_id: str, owner: str, ttl: int = 900) -> dict:
    if type(ttl) is not int or not 1 <= ttl <= 86400:
        raise HarnessError("Lease TTL must be 1..86400 seconds.")
    owner = nonempty(owner, "Lease owner")
    with store.transaction():
        task = store.get(task_id)
        for row in store.db.execute("SELECT * FROM leases WHERE expires>?", (time.time(),)):
            if row["task_id"] == task_id and row["owner"] == owner:
                continue
            if overlap(task["scopes"], json.loads(row["scopes"])):
                raise HarnessError(f"Scope leased by {row['owner']} for {row['task_id']}; use isolated worktrees or wait for release.")
        expires = time.time() + ttl
        store.db.execute("INSERT OR REPLACE INTO leases VALUES(?,?,?,?)", (task_id, owner, expires, canonical(task["scopes"])))
        store.event("lease.acquired", task_id, {"owner": owner, "expires": expires})
    return {"task_id": task_id, "owner": owner, "expires": expires, "advisory": True}


def release(store: Store, task_id: str, owner: str):
    with store.transaction():
        result = store.db.execute("DELETE FROM leases WHERE task_id=? AND owner=?", (task_id, owner))
        if result.rowcount != 1:
            raise HarnessError("No matching lease owned by this worker.")
        store.event("lease.released", task_id, {"owner": owner})
    return {"released": task_id}


def remember(store: Store, claim: str, source: str, scope: str, ttl_days: int = 30) -> dict:
    if type(ttl_days) is not int or not 1 <= ttl_days <= 3650:
        raise HarnessError("Memory TTL must be 1..3650 days.")
    source = relative_path(source)
    if sensitive(source):
        raise HarnessError("Memory source must be a nonprivate project artifact.")
    source_hash = file_hash(safe_path(store.root, source))
    record = {"claim": nonempty(claim, "Claim"), "source": source, "source_sha256": source_hash,
              "scope": nonempty(scope, "Memory scope"), "classification": "candidate", "created_at": now(),
              "expires_at": (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat(),
              "reviewer": None, "uncertainty": None, "supersedes": None}
    record_id = new_id("memory")
    with store.transaction():
        store.db.execute("INSERT INTO memory VALUES(?,?)", (record_id, canonical(record)))
        store.event("memory.candidate", record_id, {"source": source, "scope": scope})
    return {"id": record_id, **record}


def memory_health(root: Path, record: dict) -> str:
    try:
        if datetime.fromisoformat(record["expires_at"]) <= datetime.now(timezone.utc):
            return "expired"
        if file_hash(safe_path(root, record["source"])) != record["source_sha256"]:
            return "stale"
    except (OSError, ValueError, HarnessError):
        return "stale"
    return "current"


def promote(store: Store, memory_id: str, reviewer: str, uncertainty: str, supersedes: str | None = None) -> dict:
    with store.transaction():
        records = {m["id"]: m for m in store.records("memory")}
        if memory_id not in records:
            raise HarnessError("Unknown memory entry.")
        record = records[memory_id]
        if record["classification"] != "candidate" or memory_health(store.root, record) != "current":
            raise HarnessError("Only a current, unchanged candidate may be promoted.")
        if supersedes:
            if supersedes == memory_id or supersedes not in records or records[supersedes]["classification"] != "decision":
                raise HarnessError("Supersedes must name an existing decision.")
            old = records[supersedes]
            if old["scope"] != record["scope"]:
                raise HarnessError("A decision may supersede another decision only in the same scope.")
            old["classification"] = "superseded"
            store.db.execute("UPDATE memory SET data=? WHERE id=?", (canonical({k: v for k, v in old.items() if k != "id"}), supersedes))
        record.update(classification="decision", reviewer=nonempty(reviewer, "Reviewer"),
                      uncertainty=nonempty(uncertainty, "Uncertainty"), supersedes=supersedes)
        store.db.execute("UPDATE memory SET data=? WHERE id=?", (canonical({k: v for k, v in record.items() if k != "id"}), memory_id))
        store.event("memory.promoted", memory_id, {"reviewer": reviewer, "supersedes": supersedes})
    return record


def memory_search(store: Store, query: str, scope: str | None = None) -> list[dict]:
    terms = nonempty(query, "Query").casefold().split()
    result = []
    for record in store.records("memory"):
        if scope is not None and record["scope"] != scope:
            continue
        score = sum(word in (record["claim"] + " " + record["scope"]).casefold() for word in terms)
        if score:
            result.append({**record, "health": memory_health(store.root, record), "score": score})
    return sorted(result, key=lambda m: (-m["score"], m["id"]))[:20]


def usage(store: Store, key: str, amount: int, note: str) -> dict:
    if type(amount) is not int or amount < 0:
        raise HarnessError("Usage amount must be a nonnegative integer in currency millionths.")
    nonempty(key, "Idempotency key")
    nonempty(note, "Usage note")
    config = configuration.load(store.root)
    record = {"amount_micros": amount, "currency": config["budget"]["currency"], "note": note, "created_at": now()}
    with store.transaction():
        existing = store.db.execute("SELECT amount,data FROM usage WHERE id=?", (key,)).fetchone()
        if existing:
            prior = json.loads(existing["data"])
            if existing["amount"] != amount or prior["note"] != note or prior["currency"] != record["currency"]:
                raise HarnessError("Idempotency key already used with different usage data.")
            return {"id": key, **prior, "duplicate": True}
        total = store.db.execute("SELECT coalesce(sum(amount),0) FROM usage").fetchone()[0]
        # Usage is observed reality: record overages rather than hiding them.
        store.db.execute("INSERT INTO usage VALUES(?,?,?)", (key, amount, canonical(record)))
        store.event("usage.recorded", key, {"amount_micros": amount, "over_budget": total + amount > config["budget"]["limit_micros"]})
    return {"id": key, **record, "duplicate": False, "over_budget": total + amount > config["budget"]["limit_micros"]}


def budget(store: Store) -> dict:
    config = configuration.load(store.root)
    records = store.records("usage")
    currencies = sorted({r["currency"] for r in records})
    if currencies and currencies != [config["budget"]["currency"]]:
        raise HarnessError("Usage currency differs from configuration; use a fresh workspace for a new currency.")
    used = sum(r["amount_micros"] for r in records)
    limit = config["budget"]["limit_micros"]
    return {"currency": config["budget"]["currency"], "used_micros": used, "limit_micros": limit,
            "remaining_micros": max(0, limit - used), "over_budget": used > limit,
            "scope": "Manually reported external usage. No provider traffic is intercepted or billed by this CLI."}
