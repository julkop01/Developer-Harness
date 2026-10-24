"""Behavioral and adversarial checks against real temporary repositories."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from developer_harness import cli, config, context, engine, install, runner
from developer_harness.store import Store
from developer_harness.util import HarnessError, canonical, files, json_write, read_json, redact, safe_path, snapshot


class Workspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="developer harness ")
        self.root = Path(self.temp.name)
        (self.root / "app.py").write_text("VALUE = 1\n")
        (self.root / "proof.md").write_text("Observed the user journey in a local environment.\n")
        install.initialize(self.root)
        self.cfg = config.load(self.root)
        self.cfg["commands"] = {
            "pass": {"argv": ["{python}", "-c", "print('verified')"], "timeout_seconds": 5, "description": "deterministic smoke"},
            "fail": {"argv": ["{python}", "-c", "raise SystemExit(7)"], "timeout_seconds": 5, "description": "deliberate failure"},
        }
        self.save()
        self.store = Store(self.root)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def save(self):
        json_write(self.root / ".harness/config.json", self.cfg)

    def task(self, scopes=None, risk="normal", depends=None, owner="builder"):
        return engine.new_task(self.store, "A useful change", "The user can complete the core journey",
                               ["The core journey succeeds"], scopes or ["."], owner, risk, depends)

    def active(self, **kwargs):
        task = self.task(**kwargs)
        return engine.transition(self.store, task["id"], "active", 1, "Implementation authorized")

    def proof(self, task):
        return runner.run_check(self.store, task["id"], task["version"], "pass", ["c1"])

    def in_review(self, task):
        self.proof(task)
        task = engine.transition(self.store, task["id"], "verifying", task["version"], "Ready to verify")
        return engine.transition(self.store, task["id"], "review", task["version"], "Current proof exists")


class ConfigurationTests(Workspace):
    def test_all_bundled_profiles_validate(self):
        for p in (Path(config.__file__).parent / "resources/profiles").glob("*.json"):
            self.assertEqual(config.make(p.stem)["profile"], p.stem)

    def test_unknown_field_rejected(self):
        self.cfg["surprise"] = True
        with self.assertRaises(HarnessError):
            config.validate(self.cfg)

    def test_shell_string_rejected(self):
        self.cfg["commands"]["pass"]["argv"] = "echo unsafe"
        with self.assertRaises(HarnessError):
            config.validate(self.cfg)

    def test_negative_budget_rejected(self):
        self.cfg["budget"]["limit_micros"] = -1
        with self.assertRaises(HarnessError):
            config.validate(self.cfg)

    def test_unknown_required_check_rejected(self):
        self.cfg["required_checks"] = ["unknown"]
        with self.assertRaises(HarnessError):
            config.validate(self.cfg)

    def test_unknown_profile_rejected(self):
        with self.assertRaises(HarnessError):
            config.make("../../escape")

    def test_init_is_non_destructive(self):
        self.cfg["name"] = "An existing owner preference"
        self.save()
        self.assertFalse(install.initialize(self.root)["initialized"])
        self.assertEqual(config.load(self.root)["name"], self.cfg["name"])

    def test_boolean_count_is_rejected(self):
        self.cfg["limits"]["max_checks_per_task"] = True
        with self.assertRaises(HarnessError):
            config.validate(self.cfg)


class TaskTests(Workspace):
    def test_lifecycle_requires_evidence_and_review(self):
        task = self.active()
        with self.assertRaises(HarnessError):
            engine.transition(self.store, task["id"], "done", task["version"], "Skipping gates")
        task = self.in_review(task)
        with self.assertRaises(HarnessError):
            engine.transition(self.store, task["id"], "done", task["version"], "No review")
        engine.review(self.store, task["id"], task["version"], "builder", "pass", "Inspected current proof")
        done = engine.transition(self.store, task["id"], "done", task["version"], "Acceptance satisfied")
        self.assertEqual(done["state"], "done")

    def test_version_conflict_does_not_change_state(self):
        task = self.active()
        with self.assertRaises(HarnessError):
            engine.transition(self.store, task["id"], "blocked", 1, "Stale writer")
        self.assertEqual(self.store.get(task["id"])["state"], "active")

    def test_missing_scope_rejected(self):
        with self.assertRaises(HarnessError):
            engine.new_task(self.store, "T", "O", ["C"], [], "builder")

    def test_missing_criteria_rejected(self):
        with self.assertRaises(HarnessError):
            engine.new_task(self.store, "T", "O", [], ["."], "builder")

    def test_dependency_gates_activation(self):
        first = self.task()
        second = self.task(depends=[first["id"]])
        with self.assertRaises(HarnessError):
            engine.transition(self.store, second["id"], "active", 1, "Dependency missing")

    def test_nonexistent_dependency_rejected(self):
        with self.assertRaises(HarnessError):
            self.task(depends=["task-missing"])
        self.assertEqual(self.store.tasks(), [])

    def test_work_in_progress_limit(self):
        self.cfg["workflow"]["max_active_tasks"] = 1
        self.save()
        self.active()
        second = self.task()
        with self.assertRaises(HarnessError):
            engine.transition(self.store, second["id"], "active", 1, "Too much work")

    def test_high_risk_needs_independent_review(self):
        task = self.in_review(self.active(risk="high"))
        engine.review(self.store, task["id"], task["version"], "builder", "pass", "Self review")
        with self.assertRaises(HarnessError):
            engine.transition(self.store, task["id"], "done", task["version"], "Self approval")
        engine.review(self.store, task["id"], task["version"], "separate-reviewer", "pass", "Challenge and proof inspected", True)
        self.assertEqual(engine.transition(self.store, task["id"], "done", task["version"], "Independent review")['state'], "done")

    def test_builder_cannot_attest_to_independence(self):
        task = self.in_review(self.active())
        with self.assertRaises(HarnessError):
            engine.review(self.store, task["id"], task["version"], "BUILDER", "pass", "Not independent", True)

    def test_latest_failing_review_blocks_done(self):
        task = self.in_review(self.active())
        engine.review(self.store, task["id"], task["version"], "builder", "pass", "Initially accepted")
        engine.review(self.store, task["id"], task["version"], "reviewer", "fail", "A new defect found")
        with self.assertRaises(HarnessError):
            engine.transition(self.store, task["id"], "done", task["version"], "Old pass is insufficient")

    def test_manual_evidence_is_labeled(self):
        task = self.active()
        record = engine.add_evidence(self.store, task["id"], task["version"], "proof.md", ["c1"], "Observed in browser", "operator")
        self.assertEqual(record["kind"], "manual")
        self.assertTrue(engine.gate(self.store, task)["ok"])

    def test_unknown_criterion_rejected(self):
        task = self.active()
        with self.assertRaises(HarnessError):
            runner.run_check(self.store, task["id"], task["version"], "pass", ["invented"])

    def test_required_check_cannot_be_replaced_by_manual_note(self):
        self.cfg["required_checks"] = ["pass"]
        self.save()
        task = self.active()
        engine.add_evidence(self.store, task["id"], task["version"], "proof.md", ["c1"], "Manual claim", "operator")
        self.assertFalse(engine.gate(self.store, task)["ok"])


class RunnerTests(Workspace):
    def test_successful_check_cached_exactly(self):
        task = self.active()
        first = self.proof(task)
        second = self.proof(task)
        self.assertEqual(first["id"], second["id"])
        self.assertTrue(second["cached"])
        self.assertTrue(engine.gate(self.store, task)["ok"])

    def test_source_change_invalidates_receipt_and_cache(self):
        task = self.active()
        first = self.proof(task)
        (self.root / "app.py").write_text("VALUE = 2\n")
        self.assertFalse(engine.gate(self.store, task)["ok"])
        second = self.proof(task)
        self.assertNotEqual(first["id"], second["id"])

    def test_new_file_invalidates_receipt(self):
        task = self.active()
        self.proof(task)
        (self.root / "new.py").write_text("new source\n")
        self.assertFalse(engine.gate(self.store, task)["ok"])

    def test_deleted_file_invalidates_receipt(self):
        task = self.active()
        self.proof(task)
        (self.root / "app.py").unlink()
        self.assertFalse(engine.gate(self.store, task)["ok"])

    def test_config_change_invalidates_receipt(self):
        task = self.active()
        self.proof(task)
        self.cfg["commands"]["pass"]["argv"][-1] = "print('different behavior')"
        self.save()
        self.assertFalse(engine.gate(self.store, task)["ok"])

    def test_scope_excludes_unrelated_change(self):
        task = self.active(scopes=["app.py"])
        self.proof(task)
        (self.root / "proof.md").write_text("Unrelated doc edit\n")
        self.assertTrue(engine.gate(self.store, task)["ok"])

    def test_failed_checks_are_not_cached(self):
        task = self.active()
        a = runner.run_check(self.store, task["id"], task["version"], "fail", ["c1"])
        b = runner.run_check(self.store, task["id"], task["version"], "fail", ["c1"])
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(a["exit_code"], 7)
        self.assertFalse(engine.gate(self.store, task)["ok"])

    def test_repeated_failure_circuit(self):
        task = self.active()
        for _ in range(3):
            runner.run_check(self.store, task["id"], task["version"], "fail", ["c1"])
        with self.assertRaises(HarnessError):
            runner.run_check(self.store, task["id"], task["version"], "fail", ["c1"])

    def test_check_count_budget(self):
        self.cfg["limits"]["max_checks_per_task"] = 1
        self.save()
        task = self.active()
        self.proof(task)
        with self.assertRaises(HarnessError):
            runner.run_check(self.store, task["id"], task["version"], "pass", ["c1"], True)

    def test_timeout_fails_and_bounds_runtime(self):
        result = runner.execute([sys.executable, "-c", "import time; time.sleep(10)"], self.root, 0.1, 1024)
        self.assertEqual(result["status"], "timeout")
        self.assertLess(result["elapsed_seconds"], 3)

    def test_output_limit_is_a_failure(self):
        result = runner.execute([sys.executable, "-c", "print('x' * 100000)"], self.root, 5, 1024)
        self.assertEqual(result["status"], "output_limit")
        self.assertLessEqual(len(result["output"]), 1024)

    def test_command_missing_fails_without_crash(self):
        result = runner.execute(["surely-not-an-installed-command-8123"], self.root, 1, 1024)
        self.assertEqual(result["status"], "failed")

    def test_unknown_check_rejected(self):
        task = self.active()
        with self.assertRaises(HarnessError):
            runner.run_check(self.store, task["id"], task["version"], "not-authorized", ["c1"])

    def test_project_source_changed_during_check_fails(self):
        self.cfg["commands"]["mutate"] = {"argv": ["{python}", "-c", "from pathlib import Path; Path('app.py').write_text('changed')"],
                                           "timeout_seconds": 5, "description": "Deliberate mutation"}
        self.save()
        task = self.active()
        result = runner.run_check(self.store, task["id"], task["version"], "mutate", ["c1"])
        self.assertEqual(result["status"], "inputs_changed")
        self.assertFalse(engine.gate(self.store, task)["ok"])

    def test_log_tamper_invalidates_proof(self):
        task = self.active()
        proof = self.proof(task)
        (self.root / proof["artifact"]).write_text("Replaced output")
        self.assertFalse(engine.gate(self.store, task)["ok"])

    def test_expired_receipt_invalidates_proof(self):
        task = self.active()
        proof = self.proof(task)
        proof["created_at"] = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        self.store.db.execute("UPDATE evidence SET data=? WHERE id=?", (canonical({k: v for k, v in proof.items() if k != "id"}), proof["id"]))
        self.assertFalse(engine.gate(self.store, task)["ok"])

    def test_sensitive_environment_not_inherited(self):
        with patch.dict(os.environ, {"PRIVATE_TEST_TOKEN": "a-very-private-value"}):
            result = runner.execute([sys.executable, "-c", "import os; print(os.getenv('PRIVATE_TEST_TOKEN', 'absent'))"], self.root, 5, 1024)
        self.assertEqual(result["output"].strip(), "absent")

    def test_shell_metacharacters_are_literal(self):
        result = runner.execute([sys.executable, "-c", "import sys; print(sys.argv[1])", "$(touch surprise)"], self.root, 5, 1024)
        self.assertIn("$(touch surprise)", result["output"])
        self.assertFalse((self.root / "surprise").exists())


class ContinuityTests(Workspace):
    def test_checkpoint_survives_reopen(self):
        task = self.active()
        engine.checkpoint(self.store, task["id"], task["version"], "Implemented parser", "Add malformed input cases")
        self.store.close()
        self.store = Store(self.root)
        packet = context.context_pack(self.store, task["id"])
        self.assertIn("Add malformed input cases", packet["text"])
        self.assertLessEqual(packet["chars"], packet["limit_chars"])

    def test_checkpoint_detects_source_drift(self):
        task = self.active()
        engine.checkpoint(self.store, task["id"], task["version"], "Partial", "Continue")
        (self.root / "app.py").write_text("different\n")
        self.assertIn("Checkpoint sources changed: True", context.context_pack(self.store, task["id"])["text"])

    def test_oversized_context_file_is_omitted(self):
        task = self.active()
        (self.root / "large.md").write_text("x" * 200000)
        packet = context.context_pack(self.store, task["id"], ["large.md"])
        self.assertEqual(packet["omitted_files"], ["large.md"])
        self.assertLessEqual(packet["chars"], 16000)

    def test_context_rejects_private_file(self):
        task = self.active()
        (self.root / ".env").write_text("password=hidden")
        with self.assertRaises(HarnessError):
            context.context_pack(self.store, task["id"], [".env"])

    def test_context_does_not_promote_source_instructions(self):
        task = self.active()
        packet = context.context_pack(self.store, task["id"], ["app.py"])
        self.assertIn("Untrusted source excerpt", packet["text"])

    def test_plan_has_no_execution_side_effects(self):
        task = self.task()
        plan = context.night_plan(self.store)
        self.assertEqual(plan["eligible"][0]["id"], task["id"])
        self.assertEqual(self.store.get(task["id"])["state"], "planned")

    def test_night_plan_excludes_high_risk(self):
        self.task(risk="high")
        plan = context.night_plan(self.store)
        self.assertEqual(plan["eligible"], [])
        self.assertEqual(len(plan["blocked"]), 1)


class MemoryAndLeaseTests(Workspace):
    def test_memory_requires_provenance_and_promotion(self):
        record = engine.remember(self.store, "This parser accepts UTF-8", "proof.md", "workspace")
        self.assertEqual(record["classification"], "candidate")
        promoted = engine.promote(self.store, record["id"], "reviewer", "Applies to the tested sample")
        self.assertEqual(promoted["classification"], "decision")
        self.assertEqual(engine.memory_search(self.store, "UTF-8")[0]["health"], "current")

    def test_changed_memory_source_cannot_promote(self):
        record = engine.remember(self.store, "Claim", "proof.md", "workspace")
        (self.root / "proof.md").write_text("changed")
        with self.assertRaises(HarnessError):
            engine.promote(self.store, record["id"], "reviewer", "Unknown")

    def test_supersession_keeps_old_decision(self):
        a = engine.remember(self.store, "Old rule", "proof.md", "workspace")
        engine.promote(self.store, a["id"], "reviewer", "Initial evidence")
        b = engine.remember(self.store, "Improved rule", "proof.md", "workspace")
        engine.promote(self.store, b["id"], "reviewer", "New evidence", a["id"])
        old = next(m for m in self.store.records("memory") if m["id"] == a["id"])
        self.assertEqual(old["classification"], "superseded")

    def test_scope_filter_avoids_cross_project_memory(self):
        engine.remember(self.store, "Parser rule", "proof.md", "project-a")
        self.assertEqual(engine.memory_search(self.store, "Parser", "project-b"), [])

    def test_expired_memory_marked(self):
        record = engine.remember(self.store, "Expiring claim", "proof.md", "workspace")
        record["expires_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        self.assertEqual(engine.memory_health(self.root, record), "expired")

    def test_overlapping_scope_lease_rejected(self):
        a = self.task(scopes=["app.py"])
        b = self.task()
        engine.lease(self.store, a["id"], "worker-a")
        with self.assertRaises(HarnessError):
            engine.lease(self.store, b["id"], "worker-b")

    def test_disjoint_scope_leases(self):
        a = self.task(scopes=["app.py"])
        b = self.task(scopes=["proof.md"])
        engine.lease(self.store, a["id"], "worker-a")
        engine.lease(self.store, b["id"], "worker-b")

    def test_lease_cannot_be_released_by_different_worker(self):
        a = self.task()
        engine.lease(self.store, a["id"], "worker-a")
        with self.assertRaises(HarnessError):
            engine.release(self.store, a["id"], "worker-b")

    def test_usage_deduplication_and_overage_truth(self):
        a = engine.usage(self.store, "request-1", 200, "Observed external provider usage")
        b = engine.usage(self.store, "request-1", 200, "Observed external provider usage")
        self.assertTrue(a["over_budget"])
        self.assertTrue(b["duplicate"])
        self.assertEqual(engine.budget(self.store)["used_micros"], 200)

    def test_conflicting_usage_key_rejected(self):
        engine.usage(self.store, "request-1", 200, "Observed usage")
        with self.assertRaises(HarnessError):
            engine.usage(self.store, "request-1", 201, "Observed usage")


class BoundaryAndIntegrityTests(Workspace):
    def test_path_traversal_rejected(self):
        for value in ("../secret", "/etc/passwd", "C:/Windows/system.ini", "x/../../secret", "x\\..\\secret"):
            with self.subTest(value=value), self.assertRaises(HarnessError):
                safe_path(self.root, value)

    @unittest.skipIf(os.name == "nt", "Symlink creation may require special Windows privileges")
    def test_symlink_escape_rejected(self):
        (self.root / "outside").symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(HarnessError):
            safe_path(self.root, "outside/file")
        with self.assertRaises(HarnessError):
            snapshot(self.root, ["."])

    def test_private_and_generated_files_excluded(self):
        (self.root / ".env").write_text("secret")
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules/package.js").write_text("generated")
        names = files(self.root)
        self.assertNotIn(".env", names)
        self.assertNotIn("node_modules/package.js", names)

    @unittest.skipUnless(__import__("shutil").which("git"), "Git unavailable")
    def test_gitignored_files_excluded(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        with (self.root / ".gitignore").open("a") as stream:
            stream.write("\nignored.txt\n")
        (self.root / "ignored.txt").write_text("not for context")
        self.assertNotIn("ignored.txt", files(self.root))

    def test_redacts_common_tokens(self):
        text = "password=private\nAuthorization: Bearer abc.def\nsk-abcdefghijklmnopqrstuv"
        clean = redact(text)
        self.assertNotIn("private", clean)
        self.assertNotIn("abc.def", clean)
        self.assertNotIn("sk-", clean)

    def test_event_chain_detects_tampering(self):
        self.task()
        self.assertTrue(self.store.audit()["ok"])
        self.store.db.execute("UPDATE events SET kind='tampered' WHERE seq=1")
        self.assertFalse(self.store.audit()["ok"])

    def test_transaction_rolls_back(self):
        with self.assertRaises(RuntimeError):
            with self.store.transaction():
                self.store.event("test", "entity", {})
                raise RuntimeError("intentional")
        self.assertEqual(self.store.audit()["event_count"], 0)

    def test_consistent_backup_restores_task(self):
        task = self.task()
        backup = self.root / ".harness/backups/test.sqlite3"
        self.store.backup(backup)
        restored = sqlite3.connect(backup)
        try:
            self.assertEqual(restored.execute("SELECT id FROM tasks").fetchone()[0], task["id"])
            self.assertEqual(restored.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            restored.close()

    def test_export_contains_all_recovery_data(self):
        self.task()
        exported = self.store.export()
        self.assertEqual(len(exported["tasks"]), 1)
        self.assertEqual(len(exported["events"]), 1)

    def test_cli_failure_returns_nonzero(self):
        with redirect_stderr(io.StringIO()):
            code = cli.main(["--root", str(self.root), "task", "show", "missing"])
        self.assertEqual(code, 2)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="harness install ")
        self.root = Path(self.temp.name)
        (self.root / "AGENTS.md").write_text("# Owner rules\nKeep these rules.\n")
        (self.root / "important.txt").write_text("untouched")

    def tearDown(self):
        self.temp.cleanup()

    def test_dry_run_does_not_write(self):
        plan = install.install(self.root)
        self.assertFalse(plan["applied"])
        self.assertFalse((self.root / ".harness").exists())
        self.assertNotIn(install.START, (self.root / "AGENTS.md").read_text())

    def test_install_preserves_owner_rules_and_is_idempotent(self):
        install.install(self.root, apply=True)
        self.assertIn("Keep these rules.", (self.root / "AGENTS.md").read_text())
        self.assertEqual(install.install(self.root, apply=True)["changes"], [])
        self.assertEqual((self.root / "important.txt").read_text(), "untouched")

    def test_external_instruction_edits_survive_update(self):
        install.install(self.root, apply=True)
        with (self.root / "AGENTS.md").open("a") as stream:
            stream.write("\nA new owner rule.\n")
        install.install(self.root, apply=True)
        self.assertIn("A new owner rule.", (self.root / "AGENTS.md").read_text())

    def test_modified_managed_file_blocks_update(self):
        install.install(self.root, apply=True)
        managed = self.root / ".developer-harness/developer_harness/__init__.py"
        managed.write_text("local edit")
        with self.assertRaises(HarnessError):
            install.install(self.root, apply=True)

    def test_modified_managed_block_blocks_update(self):
        install.install(self.root, apply=True)
        path = self.root / "AGENTS.md"
        path.write_text(path.read_text().replace("## Developer Harness", "## Local edits inside block"))
        with self.assertRaises(HarnessError):
            install.install(self.root, apply=True)

    def test_unowned_file_never_overwritten(self):
        path = self.root / ".developer-harness/dh.py"
        path.parent.mkdir()
        path.write_text("my existing file")
        with self.assertRaises(HarnessError):
            install.install(self.root, apply=True)
        self.assertFalse((self.root / ".harness/config.json").exists())

    def test_uninstall_retains_owner_rules_and_personal_data(self):
        install.install(self.root, apply=True)
        install.uninstall(self.root, apply=True)
        self.assertIn("Keep these rules.", (self.root / "AGENTS.md").read_text())
        self.assertNotIn(install.START, (self.root / "AGENTS.md").read_text())
        self.assertTrue((self.root / ".harness/config.json").is_file())
        self.assertFalse((self.root / ".developer-harness/dh.py").exists())

    def test_malformed_markers_fail_before_any_write(self):
        (self.root / "AGENTS.md").write_text(install.START + "\nunclosed")
        with self.assertRaises(HarnessError):
            install.install(self.root, apply=True)
        self.assertFalse((self.root / ".developer-harness").exists())

    def test_installed_cli_runs_from_target_path_with_spaces(self):
        install.install(self.root, adapters=["claude", "gemini", "copilot"], apply=True)
        process = subprocess.run([sys.executable, str(self.root / ".developer-harness/dh.py"), "--root", str(self.root), "doctor"],
                                 capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertTrue(json.loads(process.stdout)["ok"])
        self.assertTrue((self.root / ".github/copilot-instructions.md").exists())


if __name__ == "__main__":
    unittest.main()
