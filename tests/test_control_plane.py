"""Tests for the deterministic 2.0 control-plane foundation."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from developer_harness import control_plane, engine, install
from developer_harness.store import Store


@unittest.skipUnless(shutil.which("git"), "Git unavailable")
class ControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        (self.root / "app.py").write_text("value = 1\n")
        subprocess.run(["git", "add", "app.py"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=self.root, check=True)
        install.initialize(self.root)
        self.store = Store(self.root)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def session(self, session_id="s1"):
        return {
            "schema": "dh.session.v1",
            "adapter": "codex",
            "session_id": session_id,
            "workspace": str(self.root),
            "worktree": str(self.root),
            "status": "active",
            "updated_at": "2026-10-25T12:00:00+00:00",
            "capabilities": ["read", "edit"],
        }

    def test_unified_ingress_routes_session_and_mcp(self):
        session = control_plane.ingest(self.store, self.session())
        self.assertEqual(session["kind"], "session")
        mcp = control_plane.ingest(self.store, {
            "schema": "dh.mcp.v1",
            "adapter": "codex",
            "name": "example",
            "transport": "stdio",
            "command": "server",
            "args": [],
            "env_keys": [],
        })
        self.assertEqual(mcp["name"], "example")
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM host_sessions").fetchone()[0], 1)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM mcp_servers").fetchone()[0], 1)

    def test_snapshot_is_read_only_and_reports_authority_boundary(self):
        before = self.store.audit()["event_count"]
        snapshot = control_plane.snapshot(self.store)
        after = self.store.audit()["event_count"]
        self.assertEqual(before, after)
        self.assertTrue(snapshot["authority"]["read_only_projection"])
        self.assertFalse(snapshot["authority"]["host_observations_are_evidence"])
        self.assertFalse(snapshot["authority"]["permission_records_grant_authority"])
        self.assertFalse(snapshot["authority"]["automatic_actions"])

    def test_snapshot_combines_task_session_mcp_and_worktree_state(self):
        engine.new_task(self.store, "Task", "Outcome", ["Behavior passes"], ["app.py"], "builder")
        control_plane.ingest(self.store, self.session())
        control_plane.ingest(self.store, {
            "schema": "dh.mcp.v1",
            "adapter": "codex",
            "name": "shared",
            "transport": "stdio",
            "command": "server-a",
            "args": [],
            "env_keys": [],
        })
        control_plane.ingest(self.store, {
            "schema": "dh.mcp.v1",
            "adapter": "claude",
            "name": "shared",
            "transport": "stdio",
            "command": "server-b",
            "args": [],
            "env_keys": [],
        })
        snapshot = control_plane.snapshot(self.store)
        self.assertEqual(snapshot["summary"]["tasks"], 1)
        self.assertEqual(snapshot["summary"]["host_sessions"], 1)
        self.assertEqual(snapshot["summary"]["mcp_drift"], 1)
        self.assertEqual(snapshot["worktrees"]["aggregates"]["linked_sessions"], 1)
        self.assertIn("mcp-drift", [warning["kind"] for warning in snapshot["warnings"]])

    def test_context_pressure_surfaces_as_warning(self):
        control_plane.ingest(self.store, self.session())
        control_plane.ingest(self.store, {
            "schema": "dh.context.v1",
            "adapter": "codex",
            "session_id": "s1",
            "pressure": "critical",
            "unit": "tokens",
            "compacting": True,
            "timestamp": "2026-10-25T12:01:00+00:00",
            "used": 900,
            "limit": 1000,
        })
        snapshot = control_plane.snapshot(self.store)
        self.assertIn("context-pressure", [warning["kind"] for warning in snapshot["warnings"]])

    def test_non_git_workspace_degrades_with_warning(self):
        self.store.close()
        other = Path(self.temp.name) / "plain"
        other.mkdir()
        install.initialize(other)
        self.store = Store(other)
        snapshot = control_plane.snapshot(self.store)
        self.assertIsNone(snapshot["worktrees"])
        self.assertIn("worktree-unavailable", [warning["kind"] for warning in snapshot["warnings"]])


if __name__ == "__main__":
    unittest.main()
