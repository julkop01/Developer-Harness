#!/usr/bin/env python3
"""An actual end-to-end local task, using only the standard library."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from developer_harness import config, context, engine, install, runner
from developer_harness.store import Store
from developer_harness.util import json_write


def main():
    with tempfile.TemporaryDirectory(prefix="developer-harness-example-") as directory:
        root = Path(directory)
        (root / "calculator.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (root / "test_calculator.py").write_text(
            "import unittest\nfrom calculator import add\n\nclass Regression(unittest.TestCase):\n"
            "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n"
            "    def test_negative(self):\n        self.assertEqual(add(-2, 3), 1)\n", encoding="utf-8")
        install.initialize(root, "library-cli")
        cfg = config.load(root)
        cfg["commands"] = {"test": {"argv": ["{python}", "-m", "unittest", "-v"],
                                     "timeout_seconds": 30, "description": "Arithmetic regression cases"}}
        cfg["required_checks"] = ["test"]
        json_write(root / ".harness/config.json", cfg)
        with Store(root) as store:
            task = engine.new_task(store, "Verify addition", "Addition works for positive and negative input",
                                   ["Positive and negative regression examples pass"], ["."], "example-builder")
            task = engine.transition(store, task["id"], "active", task["version"], "Baseline understood")
            receipt = runner.run_check(store, task["id"], task["version"], "test", ["c1"])
            assert receipt["status"] == "passed", receipt
            engine.checkpoint(store, task["id"], task["version"], "Both regression examples passed", "Review acceptance and diff")
            task = engine.transition(store, task["id"], "verifying", task["version"], "Checks complete")
            task = engine.transition(store, task["id"], "review", task["version"], "Current evidence passes")
            engine.review(store, task["id"], task["version"], "example-builder", "pass", "Self-review: inspected both regression assertions")
            task = engine.transition(store, task["id"], "done", task["version"], "Acceptance and review complete")
            print(f"Temporary workspace: {root}\nResult: {task['state']}\n")
            print(context.context_pack(store, task["id"])["text"])
            assert store.audit()["ok"]
    print("Example passed. Temporary files removed.")


if __name__ == "__main__":
    main()
