"""Tests for read-only worktree lifecycle analysis."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from developer_harness import worktrees
from developer_harness.util import HarnessError


@unittest.skipUnless(shutil.which("git"), "Git unavailable")
class WorktreeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test User")
        (self.root / "file.txt").write_text("base\n")
        self.git("add", "file.txt")
        self.git("commit", "-qm", "base")

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd or self.root, check=True, capture_output=True, text=True)

    def add_worktree(self, name="feature"):
        path = self.root.parent / name
        self.git("worktree", "add", "-qb", name, str(path))
        return path

    def test_base_worktree_is_reported(self):
        report = worktrees.report(self.root)
        self.assertEqual(report["aggregates"]["worktrees"], 1)
        self.assertEqual(report["worktrees"][0]["state"], "base")

    def test_dirty_worktree_is_never_cleanup_candidate(self):
        path = self.add_worktree()
        (path / "file.txt").write_text("dirty\n")
        report = worktrees.report(self.root)
        item = next(x for x in report["worktrees"] if x["branch"] == "feature")
        self.assertEqual(item["state"], "dirty")
        plan = worktrees.cleanup_plan(report)
        self.assertNotIn("feature", [x["branch"] for x in plan["remove_candidates"]])

    def test_merge_ready_branch_is_detected_without_touching_base(self):
        path = self.add_worktree()
        (path / "feature.txt").write_text("feature\n")
        self.git("add", "feature.txt", cwd=path)
        self.git("commit", "-qm", "feature", cwd=path)
        report = worktrees.report(self.root)
        item = next(x for x in report["worktrees"] if x["branch"] == "feature")
        self.assertEqual(item["state"], "merge-ready")
        self.assertEqual(item["ahead"], 1)
        self.assertFalse(item["dirty"])

    def test_merged_clean_worktree_is_cleanup_candidate(self):
        path = self.add_worktree()
        (path / "feature.txt").write_text("feature\n")
        self.git("add", "feature.txt", cwd=path)
        self.git("commit", "-qm", "feature", cwd=path)
        self.git("merge", "--ff-only", "feature")
        report = worktrees.report(self.root)
        item = next(x for x in report["worktrees"] if x["branch"] == "feature")
        self.assertEqual(item["state"], "merged")
        plan = worktrees.cleanup_plan(report)
        self.assertIn("feature", [x["branch"] for x in plan["remove_candidates"]])

    def test_conflicting_branch_is_detected(self):
        path = self.add_worktree()
        (path / "file.txt").write_text("feature\n")
        self.git("add", "file.txt", cwd=path)
        self.git("commit", "-qm", "feature edit", cwd=path)
        (self.root / "file.txt").write_text("main\n")
        self.git("add", "file.txt")
        self.git("commit", "-qm", "main edit")
        report = worktrees.report(self.root)
        item = next(x for x in report["worktrees"] if x["branch"] == "feature")
        self.assertEqual(item["state"], "conflict")
        self.assertTrue(item["conflict"])

    def test_unknown_base_rejected(self):
        with self.assertRaises(HarnessError):
            worktrees.report(self.root, base="missing")


if __name__ == "__main__":
    unittest.main()
