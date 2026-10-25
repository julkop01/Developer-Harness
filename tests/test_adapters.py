"""Contract tests for the model-neutral adapter substrate."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from developer_harness import adapters, cli, install
from developer_harness.util import HarnessError


class AdapterProtocolTests(unittest.TestCase):
    def test_catalog_marks_bridges_truthfully_unimplemented(self):
        catalog = {item["id"]: item for item in adapters.adapters()}
        self.assertIn("codex", catalog)
        self.assertIn("claude", catalog)
        self.assertFalse(catalog["codex"]["native_bridge"])
        self.assertEqual(catalog["claude"]["status"], "contract-ready")

    def test_session_contract_accepts_known_adapter(self):
        record = {
            "schema": "dh.session.v1",
            "adapter": "codex",
            "session_id": "session-1",
            "workspace": "/repo",
            "status": "active",
            "updated_at": "2026-10-25T12:00:00+00:00",
            "capabilities": ["read", "edit"],
            "task_id": None,
            "worktree": None,
        }
        self.assertEqual(adapters.validate(record), record)

    def test_unknown_protocol_field_rejected(self):
        record = {
            "schema": "dh.session.v1",
            "adapter": "codex",
            "session_id": "session-1",
            "workspace": "/repo",
            "status": "active",
            "updated_at": "2026-10-25T12:00:00+00:00",
            "capabilities": [],
            "secret": "should not be accepted",
        }
        with self.assertRaises(HarnessError):
            adapters.validate(record)

    def test_unknown_adapter_rejected(self):
        record = {
            "schema": "dh.tool_event.v1",
            "adapter": "invented-host",
            "session_id": "session-1",
            "event_id": "event-1",
            "phase": "after",
            "tool": "shell",
            "operation": "test",
            "timestamp": "2026-10-25T12:00:00+00:00",
        }
        with self.assertRaises(HarnessError):
            adapters.validate(record)

    def test_mcp_contract_never_accepts_env_values(self):
        record = {
            "schema": "dh.mcp.v1",
            "adapter": "claude",
            "name": "example",
            "transport": "stdio",
            "command": "example-server",
            "args": [],
            "env_keys": ["API_KEY=secret"],
        }
        with self.assertRaises(HarnessError):
            adapters.validate(record)

    def test_stdio_mcp_requires_command(self):
        record = {
            "schema": "dh.mcp.v1",
            "adapter": "claude",
            "name": "example",
            "transport": "stdio",
            "env_keys": [],
        }
        with self.assertRaises(HarnessError):
            adapters.validate(record)

    def test_context_values_are_bounded_semantically(self):
        record = {
            "schema": "dh.context.v1",
            "adapter": "opencode",
            "session_id": "session-1",
            "pressure": "normal",
            "unit": "tokens",
            "compacting": False,
            "timestamp": "2026-10-25T12:00:00+00:00",
            "used": -1,
            "limit": 1000,
        }
        with self.assertRaises(HarnessError):
            adapters.validate(record)

    def test_protocol_cli_validates_repository_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            install.initialize(root)
            payload = {
                "schema": "dh.permission.v1",
                "adapter": "codex",
                "session_id": "s1",
                "request_id": "p1",
                "capability": "network",
                "decision": "requested",
                "scope": "example.com",
                "timestamp": "2026-10-25T12:00:00+00:00",
            }
            (root / "permission.json").write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(cli.main(["--root", str(root), "protocol", "validate", "permission.json"]), 0)

    def test_protocol_catalog_contains_all_canonical_contracts(self):
        names = {item["schema"] for item in adapters.protocols()}
        self.assertEqual(names, {
            "dh.session.v1",
            "dh.tool_event.v1",
            "dh.context.v1",
            "dh.permission.v1",
            "dh.mcp.v1",
        })


if __name__ == "__main__":
    unittest.main()
