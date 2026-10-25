"""Bounded named checks; no shell, implicit retries, or model/provider calls."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from . import config as configuration
from .engine import expect, fingerprint, fresh, selected_criteria
from .store import Store, new_id
from .util import HarnessError, atomic_write, canonical, file_hash, now, redact, safe_path


def _elapsed_seconds(start_ns: int) -> float:
    """Return a positive high-resolution monotonic duration."""
    elapsed = max(0, time.perf_counter_ns() - start_ns) / 1_000_000_000
    resolution = max(time.get_clock_info("perf_counter").resolution, 0.000001)
    return max(round(elapsed, 6), resolution)


def _terminate(process):
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except (ProcessLookupError, PermissionError, OSError):
        pass


def execute(argv: list[str], root: Path, timeout: float, max_bytes: int) -> dict:
    """Keep at most max_bytes of child output in memory, before redaction."""
    allowed = {"PATH", "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "SystemRoot",
               "SYSTEMROOT", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL"}
    env = {key: value for key, value in os.environ.items() if key in allowed}
    env.update(CI="1", NO_COLOR="1", PYTHONUNBUFFERED="1")
    start_ns = time.perf_counter_ns()
    try:
        process = subprocess.Popen(argv, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   env=env, shell=False, start_new_session=os.name == "posix")
    except OSError as exc:
        return {"status": "failed", "exit_code": None, "elapsed_seconds": 0,
                "output": redact(str(exc)), "output_truncated": False}
    chunks = bytearray()
    exceeded = threading.Event()

    def read():
        try:
            while True:
                data = process.stdout.read(4096)
                if not data:
                    break
                remaining = max_bytes - len(chunks)
                chunks.extend(data[:max(0, remaining)])
                if len(data) > remaining:
                    exceeded.set()
                    break
        except (OSError, ValueError):
            pass

    thread = threading.Thread(target=read, daemon=True)
    thread.start()
    status = None
    try:
        while process.poll() is None:
            if exceeded.is_set():
                status = "output_limit"
                _terminate(process)
                break
            if _elapsed_seconds(start_ns) > timeout:
                status = "timeout"
                _terminate(process)
                break
            time.sleep(0.01)
        process.wait(timeout=5)
        thread.join(timeout=0.25)
        if thread.is_alive():
            _terminate(process)
            thread.join(timeout=1)
            status = status or "failed"  # A descendant retained the output pipe.
        if exceeded.is_set():
            status = "output_limit"
    except BaseException:
        _terminate(process)
        process.wait(timeout=5)
        thread.join(timeout=1)
        raise
    finally:
        if not thread.is_alive():
            process.stdout.close()
    return {"status": status or ("passed" if process.returncode == 0 else "failed"),
            "exit_code": process.returncode, "elapsed_seconds": _elapsed_seconds(start_ns),
            "output": redact(bytes(chunks).decode("utf-8", errors="replace")),
            "output_truncated": exceeded.is_set()}


def run_check(store: Store, task_id: str, version: int, name: str, criteria: list[str], no_cache: bool = False) -> dict:
    config = configuration.load(store.root)
    if name not in config["commands"]:
        raise HarnessError("Check is not configured. Discovery suggestions never authorize execution.")
    command = config["commands"][name]
    limits = config["limits"]
    with store.transaction():
        task = store.get(task_id)
        expect(task, version)
        if task["state"] not in {"active", "verifying"}:
            raise HarnessError("Checks run only for active or verifying tasks.")
        criteria = selected_criteria(task, criteria)
        before = fingerprint(store.root, task, config)
        records = [e for e in store.records("evidence", task_id) if e.get("kind") == "check"]
        if any(e["status"] == "running" for e in records):
            raise HarnessError("A check is already running or interrupted. Inspect it; use recover only after its process has stopped.")
        if not no_cache:
            matches = [e for e in records if e.get("command") == name
                       and e.get("fingerprint", {}).get("sha256") == before["sha256"]]
            latest = matches[-1] if matches else None
            if latest and set(criteria) <= set(latest["criteria"]) and fresh(latest, before, config, store.root):
                store.event("check.cache_hit", task_id, {"receipt": latest["id"]})
                return {**latest, "cached": True}
        if len(records) >= limits["max_checks_per_task"]:
            raise HarnessError("Task check-count budget exhausted; checkpoint and revise the plan.")
        spent = sum(e.get("elapsed_seconds", 0) for e in records)
        remaining = limits["max_task_seconds"] - spent
        if remaining <= 0:
            raise HarnessError("Task execution-time budget exhausted; checkpoint before continuing.")
        failures = 0
        for record in reversed(records):
            if record.get("command") == name and record.get("fingerprint", {}).get("sha256") == before["sha256"]:
                if record["status"] == "passed":
                    break
                failures += 1
        if failures >= limits["repeat_failure_limit"]:
            raise HarnessError("Repeated failure circuit is open for this unchanged input. Change the implementation/configuration or checkpoint the blocker.")
        run_id = new_id("check")
        argv = [sys.executable if arg == "{python}" else arg for arg in command["argv"]]
        timeout = min(command["timeout_seconds"], remaining)
        record = {"task_id": task_id, "kind": "check", "command": name, "criteria": criteria,
                  "created_at": now(), "fingerprint": before, "status": "running", "cached": False,
                  "elapsed_seconds": timeout, "argv": argv}
        store.db.execute("INSERT INTO evidence VALUES(?,?,?,?,?)", (run_id, task_id, "check", record["created_at"], canonical(record)))
        store.event("check.started", task_id, {"id": run_id, "command": name, "fingerprint": before["sha256"]})
    # Don't hold a database write lock while arbitrary project code runs.
    execution_started_ns = time.perf_counter_ns()
    try:
        result = execute(argv, store.root, timeout, limits["max_log_bytes"])
        after = fingerprint(store.root, task, configuration.load(store.root))
        if after["sha256"] != before["sha256"]:
            result["status"] = "inputs_changed"
        record.update({k: v for k, v in result.items() if k != "output"})
        log_path = f".harness/logs/{run_id}.txt"
        atomic_write(safe_path(store.root, log_path), result["output"])
        record.update(artifact=log_path, artifact_sha256=file_hash(safe_path(store.root, log_path)), finished_at=now())
    except BaseException as exc:
        record.update(status="interrupted", elapsed_seconds=_elapsed_seconds(execution_started_ns),
                      error=redact(str(exc)), finished_at=now())
        with store.transaction():
            store.db.execute("UPDATE evidence SET data=? WHERE id=?", (canonical(record), run_id))
            store.event("check.interrupted", task_id, {"id": run_id})
        raise
    with store.transaction():
        store.db.execute("UPDATE evidence SET data=? WHERE id=?", (canonical(record), run_id))
        store.event("check.finished", task_id, {"id": run_id, "status": record["status"], "elapsed_seconds": record["elapsed_seconds"]})
    return {"id": run_id, **record}


def recover(store: Store, task_id: str, reason: str) -> dict:
    if not reason.strip():
        raise HarnessError("Recovery requires a reason and confirmation the old process has stopped.")
    recovered = []
    with store.transaction():
        store.get(task_id)
        for record in store.records("evidence", task_id):
            if record.get("status") == "running":
                record["status"] = "interrupted"
                record["recovery_reason"] = reason
                # Retain the original time reservation as a conservative charge.
                store.db.execute("UPDATE evidence SET data=? WHERE id=?",
                                 (canonical({k: v for k, v in record.items() if k != "id"}), record["id"]))
                recovered.append(record["id"])
        store.event("check.recovered", task_id, {"ids": recovered, "reason": reason})
    return {"recovered": recovered}
