"""Local transactional ledger. Not an authentication or hostile-user boundary."""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import uuid

from .util import HarnessError, canonical, digest, now, safe_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks (
 id TEXT PRIMARY KEY, version INTEGER NOT NULL, state TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence (
 id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id), kind TEXT NOT NULL,
 created_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reviews (
 id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id), data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS checkpoints (
 id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id), created_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS memory (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS leases (task_id TEXT PRIMARY KEY REFERENCES tasks(id), owner TEXT NOT NULL, expires REAL NOT NULL, scopes TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS usage (id TEXT PRIMARY KEY, amount INTEGER NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS host_sessions (
 id TEXT PRIMARY KEY, adapter TEXT NOT NULL, updated_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS host_events (
 id TEXT PRIMARY KEY, source_key TEXT NOT NULL UNIQUE, session_id TEXT,
 schema TEXT NOT NULL, created_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, kind TEXT NOT NULL,
 entity TEXT NOT NULL, payload TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL);
"""


def new_id(prefix: str) -> str:
    return prefix + "-" + uuid.uuid4().hex[:12]


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        safe_path(self.root, ".harness/config.json")
        self.path = safe_path(self.root, ".harness/state.sqlite3")
        if not self.path.parent.is_dir():
            raise HarnessError("Workspace is not initialized. Run init or install first.")
        self.db = sqlite3.connect(str(self.path), timeout=20, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=20000")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2):
            self.db.close()
            raise HarnessError(f"Unsupported ledger schema {version}; use a matching harness version.")
        self.db.executescript(SCHEMA)
        self.db.execute("PRAGMA user_version=2")

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")

    def event(self, kind: str, entity: str, payload: dict):
        last = self.db.execute("SELECT hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        previous = last[0] if last else "0" * 64
        created = now()
        h = digest({"created_at": created, "kind": kind, "entity": entity, "payload": payload, "previous": previous})
        self.db.execute("INSERT INTO events(created_at,kind,entity,payload,previous,hash) VALUES(?,?,?,?,?,?)",
                        (created, kind, entity, canonical(payload), previous, h))

    def get(self, task_id: str) -> dict:
        row = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            raise HarnessError(f"Unknown task: {task_id}")
        return {**json.loads(row["data"]), "id": row["id"], "version": row["version"], "state": row["state"]}

    def tasks(self) -> list[dict]:
        return [self.get(r[0]) for r in self.db.execute("SELECT id FROM tasks ORDER BY rowid")]

    def update(self, task: dict, expected: int):
        data = {k: v for k, v in task.items() if k not in ("id", "version", "state")}
        r = self.db.execute("UPDATE tasks SET version=version+1,state=?,data=? WHERE id=? AND version=?",
                            (task["state"], canonical(data), task["id"], expected))
        if r.rowcount != 1:
            raise HarnessError("Task changed in another session. Reload it and retry with the new version.")

    def records(self, table: str, task_id: str | None = None) -> list[dict]:
        if table not in {"evidence", "reviews", "checkpoints", "memory", "usage"}:
            raise HarnessError("Unsupported record table")
        rows = self.db.execute(f"SELECT id,data FROM {table}" + (" WHERE task_id=?" if task_id else "") + " ORDER BY rowid",
                               (task_id,) if task_id else ())
        return [{"id": r["id"], **json.loads(r["data"])} for r in rows]

    def audit(self) -> dict:
        errors = []
        previous = "0" * 64
        for row in self.db.execute("SELECT * FROM events ORDER BY seq"):
            expected = digest({"created_at": row["created_at"], "kind": row["kind"], "entity": row["entity"],
                               "payload": json.loads(row["payload"]), "previous": previous})
            if row["previous"] != previous or row["hash"] != expected:
                errors.append(f"Event chain mismatch at {row['seq']}")
            previous = row["hash"]
        integrity = self.db.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            errors.append(integrity)
        return {"ok": not errors, "errors": errors, "event_count": self.db.execute("SELECT count(*) FROM events").fetchone()[0],
                "note": "Hash chaining detects accidental event edits; it is not a signature or protection against a malicious local writer."}

    def export(self) -> dict:
        with self.transaction():
            return {"schema_version": 2, "exported_at": now(), "tasks": self.tasks(),
                    **{name: self.records(name) for name in ("evidence", "reviews", "checkpoints", "memory", "usage")},
                    "host_sessions": [{"id": r["id"], **json.loads(r["data"])}
                                      for r in self.db.execute("SELECT id,data FROM host_sessions ORDER BY rowid")],
                    "host_events": [{"id": r["id"], **json.loads(r["data"])}
                                    for r in self.db.execute("SELECT id,data FROM host_events ORDER BY rowid")],
                    "events": [dict(r) for r in self.db.execute("SELECT * FROM events ORDER BY seq")]}

    def backup(self, destination: Path):
        if destination.exists():
            raise HarnessError("Backup destination already exists.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        backup = sqlite3.connect(str(destination))
        try:
            self.db.backup(backup)
        finally:
            backup.close()
