"""Additional recovery, atomicity, and concurrent-writer behavior."""
from pathlib import Path
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from developer_harness import cli, config, engine, install, runner
from developer_harness.store import Store
from developer_harness.util import HarnessError, canonical, json_write


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        install.initialize(self.root)
        (self.root / "app.py").write_text("value = 1\n")
        cfg = config.load(self.root)
        cfg["commands"] = {"test": {"argv": ["{python}", "-c", "print('ok')"], "timeout_seconds": 3, "description": "test"}}
        json_write(self.root / ".harness/config.json", cfg)
        self.store = Store(self.root)
        task = engine.new_task(self.store, "Task", "Outcome", ["Behavior passes"], ["."], "builder")
        self.task = engine.transition(self.store, task["id"], "active", 1, "Work authorized")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_second_connection_rejects_stale_writer(self):
        with Store(self.root) as other:
            engine.transition(self.store, self.task["id"], "blocked", 2, "Blocking condition")
            with self.assertRaises(HarnessError):
                engine.transition(other, self.task["id"], "verifying", 2, "Stale session")
        self.assertEqual(self.store.get(self.task["id"])["state"], "blocked")

    def test_abandoned_running_record_requires_explicit_recovery(self):
        record = {"task_id": self.task["id"], "kind": "check", "command": "test", "criteria": ["c1"],
                  "created_at": "2026-10-24T00:00:00+00:00", "status": "running", "elapsed_seconds": 3,
                  "fingerprint": engine.fingerprint(self.root, self.task)}
        self.store.db.execute("INSERT INTO evidence VALUES(?,?,?,?,?)", ("abandoned", self.task["id"], "check", record["created_at"], canonical(record)))
        with self.assertRaises(HarnessError):
            runner.run_check(self.store, self.task["id"], 2, "test", ["c1"])
        result = runner.recover(self.store, self.task["id"], "Confirmed old process stopped")
        self.assertEqual(result["recovered"], ["abandoned"])
        self.assertEqual(self.store.records("evidence", self.task["id"])[0]["elapsed_seconds"], 3)
        self.assertEqual(runner.run_check(self.store, self.task["id"], 2, "test", ["c1"])["status"], "passed")

    def test_interruption_updates_receipt_and_retains_nonzero_time(self):
        def interrupted(*args):
            import time
            time.sleep(0.01)
            raise KeyboardInterrupt()
        with patch.object(runner, "execute", side_effect=interrupted), self.assertRaises(KeyboardInterrupt):
            runner.run_check(self.store, self.task["id"], 2, "test", ["c1"])
        record = self.store.records("evidence", self.task["id"])[0]
        self.assertEqual(record["status"], "interrupted")
        self.assertGreater(record["elapsed_seconds"], 0)
        self.assertFalse(engine.gate(self.store, self.task)["ok"])

    def test_failed_transition_leaves_no_partial_event(self):
        count = self.store.audit()["event_count"]
        with self.assertRaises(HarnessError):
            engine.transition(self.store, self.task["id"], "done", 2, "Unproven")
        self.assertEqual(self.store.audit()["event_count"], count)

    def test_later_failure_supersedes_earlier_pass_and_cache(self):
        candidate = config.load(self.root)
        candidate["commands"]["test"]["argv"] = ["{python}", "-c", "from pathlib import Path; raise SystemExit(1 if Path('.harness/fail-flag').exists() else 0)"]
        json_write(self.root / ".harness/config.json", candidate)
        first = runner.run_check(self.store, self.task["id"], 2, "test", ["c1"])
        self.assertEqual(first["status"], "passed")
        (self.root / ".harness/fail-flag").write_text("environmental failure")
        second = runner.run_check(self.store, self.task["id"], 2, "test", ["c1"], True)
        self.assertEqual(second["status"], "failed")
        self.assertFalse(engine.gate(self.store, self.task)["ok"])
        third = runner.run_check(self.store, self.task["id"], 2, "test", ["c1"])
        self.assertFalse(third["cached"])
        self.assertEqual(third["status"], "failed")

    def test_configure_dry_run_preserves_configuration(self):
        candidate = config.load(self.root)
        candidate["name"] = "Personalized"
        json_write(self.root / "candidate.json", candidate)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["--root", str(self.root), "configure", "candidate.json"]), 0)
        self.assertNotEqual(config.load(self.root)["name"], "Personalized")

    def test_cli_check_failure_has_failure_exit_code(self):
        candidate = config.load(self.root)
        candidate["commands"]["test"]["argv"] = ["{python}", "-c", "raise SystemExit(3)"]
        json_write(self.root / ".harness/config.json", candidate)
        with redirect_stdout(io.StringIO()):
            result = cli.main(["--root", str(self.root), "run", self.task["id"], "--check", "test", "--criterion", "c1", "--expect", "2"])
        self.assertEqual(result, 1)

    def test_init_rejects_symlinked_runtime(self):
        if os.name == "nt":
            self.skipTest("Symlink creation may require elevated Windows privileges")
        with tempfile.TemporaryDirectory() as folder:
            other = Path(folder)
            (other / ".harness").symlink_to(self.root / ".harness", target_is_directory=True)
            with self.assertRaises(HarnessError):
                install.initialize(other)


class InstallerAtomicityTests(unittest.TestCase):
    def test_upgrade_removes_only_unchanged_obsolete_owned_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            install.install(root, apply=True)
            sources = install._source_files()
            obsolete = ".developer-harness/developer_harness/__main__.py"
            sources.pop(obsolete)
            with patch.object(install, "_source_files", return_value=sources):
                plan = install.install(root)
                self.assertIn(obsolete, plan["changes"])
                self.assertTrue((root / obsolete).exists())
                install.install(root, apply=True)
            self.assertFalse((root / obsolete).exists())

    def test_corrupt_manifest_fails_with_actionable_error(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            install.install(root, apply=True)
            json_write(root / ".harness/install-manifest.json", {"files": []})
            with self.assertRaises(HarnessError):
                install.install(root, apply=True)

    def test_regular_write_failure_rolls_back_earlier_replacements(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "AGENTS.md").write_text("Owner policy\n")
            original_write = install.atomic_write
            count = 0

            def failing_write(path, value):
                nonlocal count
                count += 1
                if count == 3:
                    raise OSError("Simulated full disk")
                return original_write(path, value)

            with patch.object(install, "atomic_write", side_effect=failing_write), self.assertRaises(OSError):
                install.install(root, apply=True)
            self.assertEqual((root / "AGENTS.md").read_text(), "Owner policy\n")
            self.assertFalse((root / ".developer-harness/dh.py").exists())
            self.assertFalse((root / ".harness/config.json").exists())


if __name__ == "__main__":
    unittest.main()
