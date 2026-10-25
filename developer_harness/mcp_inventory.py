"""Persistent normalized MCP inventory and cross-host drift detection."""
from __future__ import annotations

import json

from . import adapters
from .store import Store
from .util import HarnessError, canonical, digest, now


def signature(record: dict) -> str:
    if record["transport"] == "stdio":
        value = {
            "transport": "stdio",
            "command": record.get("command"),
            "args": record.get("args", []),
        }
    else:
        value = {"transport": record["transport"], "url": record.get("url")}
    return digest(value)


def ingest(store: Store, document: dict) -> dict:
    record = adapters.validate(document)
    if record["schema"] != "dh.mcp.v1":
        raise HarnessError("MCP inventory accepts dh.mcp.v1 documents only.")
    scope = record.get("scope", "workspace")
    identity = f"{record['adapter']}:{scope}:{record['name']}"
    sig = signature(record)
    with store.transaction():
        existing = store.db.execute(
            "SELECT signature,data FROM mcp_servers WHERE id=?", (identity,)
        ).fetchone()
        duplicate = bool(existing and json.loads(existing["data"]) == record)
        if existing:
            store.db.execute(
                "UPDATE mcp_servers SET signature=?,updated_at=?,data=? WHERE id=?",
                (sig, now(), canonical(record), identity),
            )
        else:
            store.db.execute(
                "INSERT INTO mcp_servers(id,adapter,name,scope,signature,updated_at,data) VALUES(?,?,?,?,?,?,?)",
                (identity, record["adapter"], record["name"], scope, sig, now(), canonical(record)),
            )
        store.event("mcp.inventory.ingested", identity, {"signature": sig, "duplicate": duplicate})
    return {"id": identity, "signature": sig, "duplicate": duplicate, **record}


def servers(store: Store) -> list[dict]:
    rows = store.db.execute(
        "SELECT id,signature,data FROM mcp_servers ORDER BY name,adapter,scope"
    )
    return [{"id": row["id"], "signature": row["signature"], **json.loads(row["data"])} for row in rows]


def inventory(store: Store) -> dict:
    grouped: dict[str, list[dict]] = {}
    for item in servers(store):
        grouped.setdefault(item["name"], []).append(item)
    logical = []
    for name, entries in sorted(grouped.items()):
        signatures = sorted({entry["signature"] for entry in entries})
        logical.append({
            "name": name,
            "source_count": len(entries),
            "adapters": sorted({entry["adapter"] for entry in entries}),
            "scopes": sorted({entry.get("scope", "workspace") for entry in entries}),
            "consistent": len(signatures) <= 1,
            "signatures": signatures,
            "sources": entries,
        })
    fragmented = [item for item in logical if item["source_count"] > 1]
    drift = [item for item in fragmented if not item["consistent"]]
    return {
        "schema": "dh.mcp.inventory.v1",
        "servers": logical,
        "fragmented": fragmented,
        "drift": drift,
        "aggregates": {
            "logical_servers": len(logical),
            "source_records": sum(item["source_count"] for item in logical),
            "fragmented_servers": len(fragmented),
            "drifted_servers": len(drift),
            "adapters": len({entry["adapter"] for entries in grouped.values() for entry in entries}),
        },
    }


def drift(store: Store) -> list[dict]:
    return inventory(store)["drift"]
