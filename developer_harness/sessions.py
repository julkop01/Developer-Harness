"""Persistent, validated host session/event ingestion.

Host observations are auditable input. They never grant authority, satisfy task
acceptance criteria, or bypass the existing evidence/review state machine.
"""
from __future__ import annotations

from datetime import datetime
import json

from . import adapters
from .store import Store
from .util import HarnessError, canonical, digest, now


SESSION_BOUND = {"dh.tool_event.v1", "dh.context.v1", "dh.permission.v1"}


def _timestamp(value: str, field: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise HarnessError(f"Protocol field {field} must be an ISO-8601 timestamp.") from exc


def _source_key(document: dict) -> str:
    schema = document["schema"]
    if schema == "dh.tool_event.v1":
        suffix = document["event_id"]
    elif schema == "dh.permission.v1":
        suffix = document["request_id"] + ":" + document["decision"]
    else:
        suffix = digest(document)
    return f"{schema}:{document['adapter']}:{document.get('session_id', '-') }:{suffix}"


def ingest(store: Store, document: dict) -> dict:
    record = adapters.validate(document)
    schema = record["schema"]
    if schema == "dh.mcp.v1":
        raise HarnessError("MCP inventory is validation-only in 1.3; persistent MCP inventory is a later adapter layer.")
    if schema == "dh.session.v1":
        _timestamp(record["updated_at"], "updated_at")
        if record.get("started_at"):
            _timestamp(record["started_at"], "started_at")
        with store.transaction():
            existing = store.db.execute("SELECT adapter,updated_at,data FROM host_sessions WHERE id=?",
                                        (record["session_id"],)).fetchone()
            if existing:
                if existing["adapter"] != record["adapter"]:
                    raise HarnessError("A session id cannot move between adapters.")
                if _timestamp(record["updated_at"], "updated_at") < _timestamp(existing["updated_at"], "updated_at"):
                    raise HarnessError("Refusing an older session snapshot.")
                duplicate = json.loads(existing["data"]) == record
                store.db.execute("UPDATE host_sessions SET updated_at=?,data=? WHERE id=?",
                                 (record["updated_at"], canonical(record), record["session_id"]))
            else:
                duplicate = False
                store.db.execute("INSERT INTO host_sessions(id,adapter,updated_at,data) VALUES(?,?,?,?)",
                                 (record["session_id"], record["adapter"], record["updated_at"], canonical(record)))
            store.event("host.session.ingested", record["session_id"],
                        {"adapter": record["adapter"], "status": record["status"], "duplicate": duplicate})
        return {"kind": "session", "duplicate": duplicate, **record}

    if schema not in SESSION_BOUND:
        raise HarnessError("Unsupported persistent host protocol.")
    _timestamp(record["timestamp"], "timestamp")
    source_key = _source_key(record)
    event_id = "host-" + digest(record)[:16]
    with store.transaction():
        session = store.db.execute("SELECT adapter FROM host_sessions WHERE id=?", (record["session_id"],)).fetchone()
        if not session:
            raise HarnessError("Session-bound host events require a prior dh.session.v1 snapshot.")
        if session["adapter"] != record["adapter"]:
            raise HarnessError("Host event adapter does not match the session adapter.")
        existing = store.db.execute("SELECT id,data FROM host_events WHERE source_key=?", (source_key,)).fetchone()
        if existing:
            if json.loads(existing["data"]) != record:
                raise HarnessError("Host event source key was reused with different content.")
            return {"kind": "event", "id": existing["id"], "duplicate": True, **record}
        store.db.execute(
            "INSERT INTO host_events(id,source_key,session_id,schema,created_at,data) VALUES(?,?,?,?,?,?)",
            (event_id, source_key, record["session_id"], schema, now(), canonical(record)),
        )
        store.event("host.event.ingested", record["session_id"], {"id": event_id, "schema": schema})
    return {"kind": "event", "id": event_id, "duplicate": False, **record}


def sessions(store: Store) -> list[dict]:
    rows = store.db.execute("SELECT id,data FROM host_sessions ORDER BY updated_at DESC,id")
    return [{"id": row["id"], **json.loads(row["data"])} for row in rows]


def session(store: Store, session_id: str) -> dict:
    row = store.db.execute("SELECT id,data FROM host_sessions WHERE id=?", (session_id,)).fetchone()
    if not row:
        raise HarnessError("Unknown host session.")
    return {"id": row["id"], **json.loads(row["data"])}


def events(store: Store, session_id: str | None = None, limit: int = 100) -> list[dict]:
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise HarnessError("Event limit must be 1..1000.")
    if session_id is not None:
        session(store, session_id)
        rows = store.db.execute(
            "SELECT id,data FROM host_events WHERE session_id=? ORDER BY rowid DESC LIMIT ?",
            (session_id, limit),
        )
    else:
        rows = store.db.execute("SELECT id,data FROM host_events ORDER BY rowid DESC LIMIT ?", (limit,))
    return [{"id": row["id"], **json.loads(row["data"])} for row in rows]
