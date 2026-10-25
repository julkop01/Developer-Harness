"""Persistence and integrity tests for normalized host sessions/events."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from developer_harness import install, sessions
from developer_harness.store import Store
from developer_harness.util import HarnessError


def session_payload(updated="2026-10-25T12:00:00+00:00", adapter="codex"):
    return {
        "schema": "dh.session.v1",
        "adapter": adapter,
        "session_id": "session-1",
        "workspace": "/repo",
        "status": "active",
        "updated_at": updated,
        "capabilities": ["read", "edit"],
    }


def tool_payload(event_id="event-1", adapter="codex"):
    return {
        "schema": "dh.tool_event.v1",
        "adapter": adapter,
        "session_id": "session-1",
        "event_id": event_id,
        "phase": "after",
        "tool": "shell",
        "operation": "tests",
        "timestamp": "2026-10-25T12:00:01+00:00",
        "exit_code": 0,
    }


class HostSessionLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        install.initialize(self.root)
        self.store = Store(self.root)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_schema_migrates_to_current_version(self):
        version = self.store.db.execute("PRAGMA user_version").fetchone()[0]
        self.assertEqual(version, 3)

    def test_session_snapshot_upserts_idempotently(self):
        first = sessions.ingest(self.store, session_payload())
        second = sessions.ingest(self.store, session_payload())
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(len(sessions.sessions(self.store)), 1)

    def test_older_snapshot_is_rejected(self):
        sessions.ingest(self.store, session_payload("2026-10-25T12:00:02+00:00"))
        with self.assertRaises(HarnessError):
            sessions.ingest(self.store, session_payload("2026-10-25T12:00:01+00:00"))

    def test_session_id_cannot_change_adapter(self):
        sessions.ingest(self.store, session_payload())
        with self.assertRaises(HarnessError):
            sessions.ingest(self.store, session_payload(adapter="claude"))

    def test_session_bound_event_requires_session(self):
        with self.assertRaises(HarnessError):
            sessions.ingest(self.store, tool_payload())

    def test_event_adapter_must_match_session(self):
        sessions.ingest(self.store, session_payload())
        with self.assertRaises(HarnessError):
            sessions.ingest(self.store, tool_payload(adapter="claude"))

    def test_event_ingestion_is_idempotent(self):
        sessions.ingest(self.store, session_payload())
        first = sessions.ingest(self.store, tool_payload())
        second = sessions.ingest(self.store, tool_payload())
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(sessions.events(self.store, "session-1")), 1)

    def test_reused_event_source_key_with_changed_content_rejected(self):
        sessions.ingest(self.store, session_payload())
        sessions.ingest(self.store, tool_payload())
        changed = tool_payload()
        changed["exit_code"] = 1
        with self.assertRaises(HarnessError):
            sessions.ingest(self.store, changed)

    def test_mcp_inventory_is_not_silently_persisted(self):
        record = {
            "schema": "dh.mcp.v1",
            "adapter": "codex",
            "name": "example",
            "transport": "stdio",
            "command": "example-server",
            "args": [],
            "env_keys": [],
        }
        with self.assertRaises(HarnessError):
            sessions.ingest(self.store, record)

    def test_export_contains_normalized_host_state(self):
        sessions.ingest(self.store, session_payload())
        sessions.ingest(self.store, tool_payload())
        exported = self.store.export()
        self.assertEqual(exported["schema_version"], 3)
        self.assertEqual(len(exported["host_sessions"]), 1)
        self.assertEqual(len(exported["host_events"]), 1)

    def test_existing_v1_database_upgrades_non_destructively(self):
        self.store.close()
        state = self.root / ".harness/state.sqlite3"
        db = sqlite3.connect(state)
        try:
            db.execute("PRAGMA user_version=1")
            db.execute("DROP TABLE host_events")
            db.execute("DROP TABLE host_sessions")
            db.commit()
        finally:
            db.close()
        self.store = Store(self.root)
        self.assertEqual(self.store.db.execute("PRAGMA user_version").fetchone()[0], 3)
        names = {row[0] for row in self.store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("host_sessions", names)
        self.assertIn("host_events", names)

    def test_host_records_do_not_satisfy_task_evidence(self):
        sessions.ingest(self.store, session_payload())
        # Host observations are deliberately separate from evidence rows.
        self.assertEqual(self.store.records("evidence"), [])


if __name__ == "__main__":
    unittest.main()
