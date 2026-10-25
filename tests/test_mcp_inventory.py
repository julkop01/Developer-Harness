"""Tests for persistent MCP inventory and cross-host drift detection."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from developer_harness import install, mcp_inventory
from developer_harness.store import Store
from developer_harness.util import HarnessError


def mcp(adapter="codex", command="server", args=None, name="shared"):
    return {
        "schema": "dh.mcp.v1",
        "adapter": adapter,
        "name": name,
        "transport": "stdio",
        "command": command,
        "args": args or [],
        "env_keys": ["API_KEY"],
        "scope": "workspace",
    }


class McpInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        install.initialize(self.root)
        self.store = Store(self.root)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_schema_migrates_to_version_three(self):
        self.assertEqual(self.store.db.execute("PRAGMA user_version").fetchone()[0], 3)

    def test_ingest_upserts_same_adapter_scope_and_name(self):
        first = mcp_inventory.ingest(self.store, mcp())
        second = mcp_inventory.ingest(self.store, mcp())
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(len(mcp_inventory.servers(self.store)), 1)

    def test_consistent_cross_host_configuration_is_fragmented_not_drifted(self):
        mcp_inventory.ingest(self.store, mcp("codex"))
        mcp_inventory.ingest(self.store, mcp("claude"))
        result = mcp_inventory.inventory(self.store)
        self.assertEqual(result["aggregates"]["fragmented_servers"], 1)
        self.assertEqual(result["aggregates"]["drifted_servers"], 0)
        self.assertTrue(result["fragmented"][0]["consistent"])

    def test_inconsistent_cross_host_configuration_is_drift(self):
        mcp_inventory.ingest(self.store, mcp("codex", "server-a"))
        mcp_inventory.ingest(self.store, mcp("claude", "server-b"))
        result = mcp_inventory.inventory(self.store)
        self.assertEqual(result["aggregates"]["drifted_servers"], 1)
        self.assertFalse(result["drift"][0]["consistent"])

    def test_secret_arg_is_rejected_before_persistence(self):
        with self.assertRaises(HarnessError):
            mcp_inventory.ingest(self.store, mcp(args=["--api-key", "sk-abcdefghijklmnopqrstuv"]))
        self.assertEqual(mcp_inventory.servers(self.store), [])

    def test_secret_query_parameter_is_rejected(self):
        record = {
            "schema": "dh.mcp.v1",
            "adapter": "claude",
            "name": "remote",
            "transport": "http",
            "url": "https://example.com/mcp?token=secret",
            "env_keys": [],
        }
        with self.assertRaises(HarnessError):
            mcp_inventory.ingest(self.store, record)

    def test_export_contains_mcp_inventory(self):
        mcp_inventory.ingest(self.store, mcp())
        exported = self.store.export()
        self.assertEqual(exported["schema_version"], 3)
        self.assertEqual(len(exported["mcp_servers"]), 1)


if __name__ == "__main__":
    unittest.main()
