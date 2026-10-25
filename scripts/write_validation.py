#!/usr/bin/env python3
"""Generate a release validation record from commands actually run now."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from developer_harness import __version__

COMMANDS = [
    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
    [sys.executable, "examples/walkthrough.py"],
    [sys.executable, "scripts/release_check.py"],
]


def run(command: list[str]) -> dict:
    started = time.perf_counter()
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    output = (process.stdout or "") + (process.stderr or "")
    match = re.search(r"Ran (\d+) tests?", output)
    return {
        "command": command,
        "exit_code": process.returncode,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "tests": int(match.group(1)) if match else None,
        "output_tail": output[-12000:],
    }


def source_commit() -> str | None:
    supplied = os.environ.get("SOURCE_SHA")
    if supplied:
        return supplied
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="RELEASE_VALIDATION.json")
    args = parser.parse_args()
    checks = [run(command) for command in COMMANDS]
    hosted = {
        "status": os.environ.get("HOSTED_CI_STATUS", "unknown"),
        "workflow_run_id": os.environ.get("HOSTED_CI_RUN_ID") or None,
        "source_sha": source_commit(),
    }
    record = {
        "schema_version": 2,
        "product": "Developer Harness",
        "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "os": platform.system(),
            "machine": platform.machine(),
        },
        "source_commit": source_commit(),
        "hosted_matrix": hosted,
        "checks": checks,
        "scope": "Commands above were executed in this environment; hosted_matrix is a separate attestation.",
        "review": "No independent human or agent identity is inferred from this record.",
    }
    output = (ROOT / args.output).resolve()
    try:
        output.relative_to(ROOT)
    except ValueError:
        parser.error("output must stay inside the repository")
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    ok = all(check["exit_code"] == 0 for check in checks)
    print(json.dumps({
        "ok": ok,
        "output": output.relative_to(ROOT).as_posix(),
        "version": __version__,
        "source_commit": record["source_commit"],
        "hosted_matrix": hosted,
    }, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
