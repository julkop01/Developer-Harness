"""Stable, JSON-friendly command-line interface."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

from . import __version__, adapters, config, context, engine, install, mcp_inventory, runner, sessions, worktrees
from .store import Store
from .util import HarnessError, atomic_write, json_write, read_json, redact, safe_path


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dh", description="Developer Harness: evidence, continuity, and workflow for your existing AI coding tool.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--root", default=".", help="workspace directory (default: current directory)")
    p.add_argument("--json", action="store_true", help="JSON output, including restart packet text")
    commands = p.add_subparsers(dest="command", required=True)
    for name in ("init", "install"):
        c = commands.add_parser(name, help="initialize a workspace" if name == "init" else "plan/apply an existing-repository overlay")
        c.add_argument("--profile", default="general")
        c.add_argument("--name")
        if name == "install":
            c.add_argument("--apply", action="store_true")
            c.add_argument("--adapter", action="append", default=[], choices=["claude", "gemini", "copilot"])
    c = commands.add_parser("uninstall")
    c.add_argument("--apply", action="store_true")
    commands.add_parser("profiles")
    commands.add_parser("discover", help="inspect repository structure without running project commands")
    c = commands.add_parser("configure", help="validate a complete JSON config; apply only with --apply")
    c.add_argument("file")
    c.add_argument("--apply", action="store_true")
    commands.add_parser("config", help="show current configuration")
    c = commands.add_parser("task")
    tasks = c.add_subparsers(dest="action", required=True)
    n = tasks.add_parser("new")
    n.add_argument("title")
    n.add_argument("--objective", required=True)
    n.add_argument("--criterion", action="append", required=True)
    n.add_argument("--scope", action="append", required=True)
    n.add_argument("--owner", required=True)
    n.add_argument("--risk", choices=["low", "normal", "high"], default="normal")
    n.add_argument("--depends-on", action="append", default=[])
    tasks.add_parser("list")
    n = tasks.add_parser("show")
    n.add_argument("id")
    n = tasks.add_parser("move")
    n.add_argument("id")
    n.add_argument("state", choices=list(engine.TRANSITIONS))
    n.add_argument("--expect", type=int, required=True)
    n.add_argument("--reason", required=True)
    c = commands.add_parser("run", help="run a configured named check; default exact-success cache")
    c.add_argument("id")
    c.add_argument("--check", required=True)
    c.add_argument("--expect", type=int, required=True)
    c.add_argument("--criterion", action="append", required=True)
    c.add_argument("--no-cache", action="store_true")
    c = commands.add_parser("recover", help="clear interrupted run records after checking that the old process stopped")
    c.add_argument("id")
    c.add_argument("--reason", required=True)
    c.add_argument("--process-stopped", action="store_true", required=True)
    c = commands.add_parser("evidence")
    e = c.add_subparsers(dest="action", required=True)
    n = e.add_parser("list")
    n.add_argument("id")
    n = e.add_parser("add", help="attach a clearly labeled manual attestation")
    n.add_argument("id")
    n.add_argument("--expect", type=int, required=True)
    n.add_argument("--artifact", required=True)
    n.add_argument("--criterion", action="append", required=True)
    n.add_argument("--statement", required=True)
    n.add_argument("--by", required=True)
    c = commands.add_parser("verify", help="evaluate current evidence without changing task state")
    c.add_argument("id")
    c = commands.add_parser("review")
    c.add_argument("id")
    c.add_argument("--expect", type=int, required=True)
    c.add_argument("--reviewer", required=True)
    c.add_argument("--verdict", choices=["pass", "fail"], required=True)
    c.add_argument("--notes", required=True)
    c.add_argument("--independent", action="store_true")
    c = commands.add_parser("checkpoint")
    c.add_argument("id")
    c.add_argument("--expect", type=int, required=True)
    c.add_argument("--summary", required=True)
    c.add_argument("--next", required=True)
    c.add_argument("--blockers", default="none")
    for name in ("resume", "context"):
        c = commands.add_parser(name)
        c.add_argument("id")
        c.add_argument("--include", action="append", default=[])
        c.add_argument("--max-chars", type=int)
        c.add_argument("--output", help="optional repository-relative Markdown output path")
    c = commands.add_parser("lease")
    leases = c.add_subparsers(dest="action", required=True)
    n = leases.add_parser("acquire")
    n.add_argument("id")
    n.add_argument("--owner", required=True)
    n.add_argument("--ttl", type=int, default=900)
    n = leases.add_parser("release")
    n.add_argument("id")
    n.add_argument("--owner", required=True)
    leases.add_parser("list")
    c = commands.add_parser("memory")
    memories = c.add_subparsers(dest="action", required=True)
    n = memories.add_parser("add")
    n.add_argument("claim")
    n.add_argument("--source", required=True)
    n.add_argument("--scope", required=True)
    n.add_argument("--ttl-days", type=int, default=30)
    n = memories.add_parser("promote")
    n.add_argument("id")
    n.add_argument("--reviewer", required=True)
    n.add_argument("--uncertainty", required=True)
    n.add_argument("--supersedes")
    n = memories.add_parser("search")
    n.add_argument("query")
    n.add_argument("--scope")
    memories.add_parser("list")
    c = commands.add_parser("usage")
    usage = c.add_subparsers(dest="action", required=True)
    usage.add_parser("show")
    n = usage.add_parser("record")
    n.add_argument("--key", required=True)
    n.add_argument("--micros", type=int, required=True)
    n.add_argument("--note", required=True)
    c = commands.add_parser("night-plan", help="choose a bounded queue; does not launch agents or create a schedule")
    c.add_argument("--max-tasks", type=int, default=2)
    for name in ("export", "backup"):
        c = commands.add_parser(name)
        c.add_argument("--output", required=True, help="new repository-relative destination")
    commands.add_parser("doctor", help="configuration and ledger integrity")
    commands.add_parser("audit", help="integrity plus current completion-proof and memory freshness")
    commands.add_parser("capabilities")
    commands.add_parser("adapters", help="list canonical host adapter capabilities")
    p_protocol = commands.add_parser("protocol", help="inspect or validate canonical host adapter contracts")
    protocol_actions = p_protocol.add_subparsers(dest="action", required=True)
    protocol_actions.add_parser("list")
    p_validate = protocol_actions.add_parser("validate")
    p_validate.add_argument("file", help="repository-relative JSON document")
    p_sessions = commands.add_parser("sessions", help="persist and inspect validated host session observations")
    session_actions = p_sessions.add_subparsers(dest="action", required=True)
    session_actions.add_parser("list")
    p_show_session = session_actions.add_parser("show")
    p_show_session.add_argument("id")
    p_ingest = session_actions.add_parser("ingest")
    p_ingest.add_argument("file", help="repository-relative canonical protocol JSON")
    p_events = commands.add_parser("host-events", help="inspect persisted normalized host events")
    p_events.add_argument("--session")
    p_events.add_argument("--limit", type=int, default=100)
    p_worktrees = commands.add_parser("worktrees", help="inspect Git worktree lifecycle without mutating it")
    p_worktrees.add_argument("--base", default="main")
    p_worktrees.add_argument("--stale-days", type=int, default=7)
    p_worktrees.add_argument("--cleanup-plan", action="store_true")
    p_mcp = commands.add_parser("mcp", help="persist and inspect normalized MCP inventory")
    mcp_actions = p_mcp.add_subparsers(dest="action", required=True)
    p_mcp_ingest = mcp_actions.add_parser("ingest")
    p_mcp_ingest.add_argument("file", help="repository-relative dh.mcp.v1 JSON document")
    mcp_actions.add_parser("list")
    mcp_actions.add_parser("inventory")
    mcp_actions.add_parser("drift")
    commands.add_parser("status")
    return p


def capabilities() -> dict:
    return {"version": __version__, "local": ["install/update/uninstall plan", "configuration validation",
             "bounded repository discovery", "task contracts and version checks", "dependency gates", "source-bound receipts",
             "bounded named-check runner", "exact successful-check cache", "failure circuit", "checkpoint/resume",
             "canonical host adapter contracts", "adapter capability registry", "persistent normalized host sessions and events",
             "scoped memory with provenance/expiry", "advisory scope leases", "usage ledger", "backup/export", "integrity audit"],
            "host_provided": ["AI reasoning and code editing", "model credentials", "sandbox/isolation", "network permissions",
                              "provider spend enforcement", "independent reviewer identity", "multi-agent scheduling"],
            "network_calls_by_harness": False, "runtime_dependencies": "Python 3.11+ standard library"}


def dispatch(args) -> dict | list:
    root = Path(args.root).resolve()
    if args.command == "profiles":
        directory = Path(__file__).parent / "resources" / "profiles"
        return [{"id": p.stem, **read_json(p)} for p in sorted(directory.glob("*.json"))]
    if args.command == "capabilities":
        return capabilities()
    if args.command == "adapters":
        return adapters.adapters()
    if args.command == "protocol":
        if args.action == "list":
            return adapters.protocols()
        return adapters.validate(read_json(safe_path(root, args.file)))
    if args.command == "install":
        return install.install(root, args.profile, args.name, args.adapter, args.apply)
    if args.command == "uninstall":
        return install.uninstall(root, args.apply)
    if args.command == "init":
        return install.initialize(root, args.profile, args.name)
    if args.command == "discover":
        return context.discover(root)
    if args.command == "config":
        return config.load(root)
    if args.command == "configure":
        source = safe_path(root, args.file)
        new = config.validate(read_json(source))
        old = config.load(root)
        if args.apply:
            json_write(safe_path(root, ".harness/config.json"), new)
        return {"applied": args.apply, "old_fingerprint": config.config_hash(old), "new_fingerprint": config.config_hash(new),
                "note": "Config changes invalidate existing receipts. Configured commands execute project code with your user's permissions."}
    config.load(root)
    with Store(root) as store:
        c = args.command
        if c == "sessions":
            if args.action == "list":
                return sessions.sessions(store)
            if args.action == "show":
                return sessions.session(store, args.id)
            return sessions.ingest(store, read_json(safe_path(root, args.file)))
        if c == "host-events":
            return sessions.events(store, args.session, args.limit)
        if c == "worktrees":
            report = worktrees.report(root, args.base, args.stale_days, store)
            return worktrees.cleanup_plan(report) if args.cleanup_plan else report
        if c == "mcp":
            if args.action == "ingest":
                return mcp_inventory.ingest(store, read_json(safe_path(root, args.file)))
            if args.action == "list":
                return mcp_inventory.servers(store)
            if args.action == "inventory":
                return mcp_inventory.inventory(store)
            return mcp_inventory.drift(store)
        if c == "task":
            if args.action == "new":
                return engine.new_task(store, args.title, args.objective, args.criterion, args.scope, args.owner, args.risk, args.depends_on)
            if args.action == "list":
                return [{k: t[k] for k in ("id", "title", "state", "version", "owner", "risk")} for t in store.tasks()]
            if args.action == "show":
                return store.get(args.id)
            return engine.transition(store, args.id, args.state, args.expect, args.reason)
        if c == "run":
            return runner.run_check(store, args.id, args.expect, args.check, args.criterion, args.no_cache)
        if c == "recover":
            return runner.recover(store, args.id, args.reason)
        if c == "evidence":
            if args.action == "list":
                store.get(args.id)
                return store.records("evidence", args.id)
            return engine.add_evidence(store, args.id, args.expect, args.artifact, args.criterion, args.statement, args.by)
        if c == "verify":
            return engine.gate(store, store.get(args.id))
        if c == "review":
            return engine.review(store, args.id, args.expect, args.reviewer, args.verdict, args.notes, args.independent)
        if c == "checkpoint":
            return engine.checkpoint(store, args.id, args.expect, args.summary, args.next, args.blockers)
        if c in {"resume", "context"}:
            result = context.context_pack(store, args.id, args.include, args.max_chars)
            if args.output:
                output = safe_path(root, args.output)
                atomic_write(output, result["text"])
                result["output"] = args.output
            return result
        if c == "lease":
            if args.action == "acquire":
                return engine.lease(store, args.id, args.owner, args.ttl)
            if args.action == "release":
                return engine.release(store, args.id, args.owner)
            return [dict(r) for r in store.db.execute("SELECT * FROM leases ORDER BY task_id")]
        if c == "memory":
            if args.action == "add":
                return engine.remember(store, args.claim, args.source, args.scope, args.ttl_days)
            if args.action == "promote":
                return engine.promote(store, args.id, args.reviewer, args.uncertainty, args.supersedes)
            if args.action == "search":
                return engine.memory_search(store, args.query, args.scope)
            return [{**m, "health": engine.memory_health(root, m)} for m in store.records("memory")]
        if c == "usage":
            if args.action == "record":
                return engine.usage(store, args.key, args.micros, args.note)
            return engine.budget(store)
        if c == "night-plan":
            return context.night_plan(store, args.max_tasks)
        if c in {"backup", "export"}:
            target = safe_path(root, args.output)
            if target.exists():
                raise HarnessError("Destination exists; choose a new path to preserve the previous backup/export.")
            if c == "backup":
                store.backup(target)
            else:
                json_write(target, {"config": config.load(root), "ledger": store.export()})
            return {"saved": args.output, "kind": c, "privacy": "May contain task descriptions and proof metadata; inspect before sharing."}
        if c in {"doctor", "audit"}:
            result = {**store.audit(), "version": __version__, "warnings": []}
            if not config.load(root)["commands"]:
                result["warnings"].append("No project checks configured; inspect and personalize before implementing.")
            if c == "audit":
                result["completion_checks"] = [{"id": t["id"], **engine.gate(store, t)} for t in store.tasks() if t["state"] == "done"]
                result["memory_warnings"] = [{"id": m["id"], "health": engine.memory_health(root, m)} for m in store.records("memory")
                                             if engine.memory_health(root, m) != "current"]
                if any(not t["ok"] for t in result["completion_checks"]):
                    result["ok"] = False
            return result
        if c == "status":
            tasks = store.tasks()
            return {"workspace": config.load(root)["name"], "tasks": {s: sum(t["state"] == s for t in tasks) for s in engine.TRANSITIONS},
                    "host_sessions": store.db.execute("SELECT count(*) FROM host_sessions").fetchone()[0],
                    "host_events": store.db.execute("SELECT count(*) FROM host_events").fetchone()[0],
                    "mcp_sources": store.db.execute("SELECT count(*) FROM mcp_servers").fetchone()[0],
                    "budget": engine.budget(store), "integrity": store.audit()["ok"]}
    raise HarnessError("Unsupported command.")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if sys.version_info < (3, 11):
        print("Developer Harness requires Python 3.11 or newer.", file=sys.stderr)
        return 2
    try:
        result = dispatch(args)
        if args.command in {"resume", "context"} and not args.json:
            print(result["text"], end="")
            if result["omitted_files"]:
                print("\nOmitted due to size/format: " + ", ".join(result["omitted_files"]), file=sys.stderr)
        else:
            print(redact(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)))
        if isinstance(result, dict):
            if result.get("ok") is False or (args.command == "run" and result.get("status") != "passed"):
                return 1
        return 0
    except (HarnessError, OSError, sqlite3.Error, ValueError, UnicodeError) as exc:
        print(json.dumps({"error": redact(str(exc)), "command": args.command}), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('{"error":"Interrupted; inspect task state and checkpoint before resuming."}', file=sys.stderr)
        return 130
