"""Read-only Git worktree lifecycle and conflict planning."""
from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess
import time

from .store import Store
from .util import HarnessError


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    if not shutil.which("git"):
        raise HarnessError("Git is required for worktree lifecycle inspection.")
    process = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=20,
        shell=False,
    )
    if check and process.returncode != 0:
        message = (process.stderr or process.stdout or "git command failed").strip()
        raise HarnessError(message[:2000])
    return process


def _parse_worktrees(text: str) -> list[dict]:
    result, current = [], {}
    for line in text.splitlines() + [""]:
        if not line:
            if current:
                result.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        if key in {"bare", "detached", "prunable", "locked"}:
            current[key] = True if not value else value
        else:
            current[key] = value
    return result


def _status(path: Path) -> list[str]:
    process = _git(path, "status", "--porcelain=v1", "--untracked-files=normal")
    return [line for line in process.stdout.splitlines() if line]


def _counts(root: Path, base: str, branch: str) -> tuple[int | None, int | None]:
    process = _git(root, "rev-list", "--left-right", "--count", f"{base}...{branch}", check=False)
    if process.returncode != 0:
        return None, None
    left, right = process.stdout.strip().split()
    return int(right), int(left)


def _merged(root: Path, branch: str, base: str) -> bool:
    return _git(root, "merge-base", "--is-ancestor", branch, base, check=False).returncode == 0


def _conflicts(root: Path, base: str, branch: str) -> tuple[bool | None, list[str]]:
    """Use git merge-tree without touching any working tree."""
    process = _git(root, "merge-tree", "--write-tree", base, branch, check=False)
    if process.returncode == 0:
        return False, []
    output = (process.stdout or "") + "\n" + (process.stderr or "")
    conflict_files = []
    for line in output.splitlines():
        if "CONFLICT" in line:
            tail = line.rsplit(" in ", 1)[-1].strip()
            if tail and tail not in conflict_files:
                conflict_files.append(tail)
    # Git returns 1 when merge-tree found conflicts. Other failures are unknown.
    return (True, conflict_files) if process.returncode == 1 else (None, [])


def _commit_time(root: Path, ref: str) -> int | None:
    process = _git(root, "show", "-s", "--format=%ct", ref, check=False)
    try:
        return int(process.stdout.strip()) if process.returncode == 0 else None
    except ValueError:
        return None


def report(root: Path, base: str = "main", stale_days: int = 7, store: Store | None = None) -> dict:
    if type(stale_days) is not int or stale_days < 0 or stale_days > 3650:
        raise HarnessError("stale_days must be an integer in 0..3650.")
    root = root.resolve()
    _git(root, "rev-parse", "--show-toplevel")
    base_ref = base if base.startswith("refs/") else f"refs/heads/{base}"
    if _git(root, "show-ref", "--verify", "--quiet", base_ref, check=False).returncode != 0:
        raise HarnessError(f"Unknown base branch: {base}")

    raw = _parse_worktrees(_git(root, "worktree", "list", "--porcelain").stdout)
    session_rows = []
    if store is not None:
        session_rows = [json.loads(r["data"]) for r in store.db.execute("SELECT data FROM host_sessions")]
    cutoff = time.time() - stale_days * 86400
    items = []
    for entry in raw:
        path = Path(entry["worktree"]).resolve()
        branch_ref = entry.get("branch")
        branch = branch_ref.removeprefix("refs/heads/") if branch_ref else None
        dirty_files = _status(path) if path.exists() else []
        ahead = behind = None
        merged = False
        conflict = None
        conflict_files: list[str] = []
        if branch:
            ahead, behind = _counts(root, base, branch)
            if branch != base:
                merged = _merged(root, branch, base)
                if not merged and ahead:
                    conflict, conflict_files = _conflicts(root, base, branch)
        commit_ts = _commit_time(root, entry.get("HEAD", branch or base))
        stale = bool(not dirty_files and branch != base and commit_ts is not None and commit_ts < cutoff)
        if branch == base:
            state = "base"
        elif dirty_files:
            state = "dirty"
        elif merged:
            state = "merged"
        elif conflict is True:
            state = "conflict"
        elif ahead and conflict is False:
            state = "merge-ready"
        elif stale:
            state = "stale"
        else:
            state = "idle"
        linked = [
            row["session_id"] for row in session_rows
            if row.get("worktree") and Path(row["worktree"]).resolve() == path
        ]
        items.append({
            "path": str(path),
            "branch": branch,
            "head": entry.get("HEAD"),
            "state": state,
            "dirty": bool(dirty_files),
            "dirty_files": dirty_files[:100],
            "ahead": ahead,
            "behind": behind,
            "merged": merged,
            "conflict": conflict,
            "conflict_files": conflict_files[:100],
            "stale": stale,
            "last_commit_epoch": commit_ts,
            "sessions": linked,
            "locked": bool(entry.get("locked")),
            "prunable": bool(entry.get("prunable")),
        })
    aggregates = {
        "worktrees": len(items),
        "dirty": sum(item["dirty"] for item in items),
        "merge_ready": sum(item["state"] == "merge-ready" for item in items),
        "conflicts": sum(item["state"] == "conflict" for item in items),
        "merged": sum(item["state"] == "merged" for item in items),
        "stale": sum(item["state"] == "stale" for item in items),
        "linked_sessions": sum(len(item["sessions"]) for item in items),
    }
    return {"schema": "dh.worktrees.v1", "base": base, "stale_days": stale_days, "worktrees": items, "aggregates": aggregates}


def cleanup_plan(worktree_report: dict) -> dict:
    remove, keep = [], []
    for item in worktree_report["worktrees"]:
        reason = None
        if item["state"] == "merged" and not item["dirty"] and not item["locked"]:
            reason = "clean worktree whose branch is already merged into base"
        elif item["state"] == "stale" and not item["dirty"] and not item["locked"] and not item["sessions"]:
            reason = "clean stale worktree with no linked active session"
        target = {"path": item["path"], "branch": item["branch"], "state": item["state"]}
        if reason:
            remove.append({**target, "reason": reason})
        else:
            keep.append({**target, "reason": "not proven safe for automatic removal"})
    return {
        "schema": "dh.worktree-cleanup-plan.v1",
        "remove_candidates": remove,
        "keep": keep,
        "execution": "plan only; Developer Harness 1.5 never removes a worktree automatically",
    }
