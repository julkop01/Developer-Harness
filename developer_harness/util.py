"""Small filesystem boundary, deterministic fingerprints, and output hygiene."""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from datetime import datetime, timezone


class HarnessError(Exception):
    """An actionable user error; CLI converts this to a nonzero result."""


IGNORED_DIRS = {
    ".git", ".harness", ".developer-harness", ".venv", "venv", "node_modules",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build",
    ".next", ".cache", ".ssh", ".aws", ".azure", ".gnupg", "coverage",
}
SENSITIVE = (".env*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*",
             "*credentials*", "*secrets*", "*.sqlite*", "*.db", "*.zip")
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def redact(value: str) -> str:
    value = ANSI.sub("", value)
    value = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", value)
    value = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{15,}|github_pat_[A-Za-z0-9_]{15,})", "[REDACTED]", value)
    value = re.sub(r"(?im)((?:api[_-]?key|password|secret|access[_-]?token)\s*[=:]\s*)[^\s,;]+", r"\1[REDACTED]", value)
    value = re.sub(r"(https?://)[^/@\s]+:[^/@\s]+@", r"\1[REDACTED]@", value)
    return value


def relative_path(value: str, allow_root: bool = False) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise HarnessError("Use a nonempty repository-relative path with '/' separators.")
    p = Path(value)
    if p.is_absolute() or re.match(r"^[A-Za-z]:", value) or ".." in p.parts:
        raise HarnessError(f"Path must stay inside the repository: {value}")
    clean = p.as_posix()
    if clean == "." and not allow_root:
        raise HarnessError("This operation requires a file or directory below the repository root.")
    return clean


def safe_path(root: Path, value: str, allow_root: bool = False) -> Path:
    value = relative_path(value, allow_root)
    root = root.resolve()
    p = root / value
    current = root
    for part in Path(value).parts:
        current = current / part
        if current.is_symlink():
            raise HarnessError(f"Symlink paths are not supported: {value}")
    if not p.resolve().is_relative_to(root):
        raise HarnessError(f"Path escapes repository: {value}")
    return p


def atomic_write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise HarnessError(f"Refusing to replace symlink: {path.name}")
    raw = data.encode("utf-8") if isinstance(data, str) else data
    fd, tmp = tempfile.mkstemp(prefix=".dh-write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def json_write(path: Path, value) -> None:
    atomic_write(path, json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HarnessError(f"Cannot read valid JSON: {path.name}: {exc}") from exc


def sensitive(path: str) -> bool:
    p = Path(path)
    return any(part.lower() in IGNORED_DIRS for part in p.parts) or any(
        fnmatch.fnmatch(p.name.lower(), pattern) for pattern in SENSITIVE)


def files(root: Path, scopes: list[str] | None = None, strict: bool = False, limit: int = 20000) -> list[str]:
    """Exclude common generated/private paths and Git-ignored untracked files."""
    root = root.resolve()
    patterns = []
    ignore = safe_path(root, ".harnessignore")
    if ignore.is_file():
        patterns = [s.strip() for s in ignore.read_text(encoding="utf-8").splitlines()
                    if s.strip() and not s.lstrip().startswith("#")]
    result = []
    scopes = [relative_path(s, True) for s in (scopes or ["."])]

    def selected(rel):
        return any(s == "." or rel == s or rel.startswith(s + "/") for s in scopes)

    for base, dirs, names in os.walk(root, followlinks=False):
        dirs.sort()
        names.sort()
        for name in dirs[:]:
            path = Path(base) / name
            rel = path.relative_to(root).as_posix()
            excluded = sensitive(rel) or any(fnmatch.fnmatch(rel, p.rstrip("/")) for p in patterns)
            if excluded or path.is_symlink():
                dirs.remove(name)
                if strict and path.is_symlink() and not excluded and selected(rel):
                    raise HarnessError(f"Task scope contains a symlink directory: {rel}")
        for name in names:
            path = Path(base) / name
            rel = path.relative_to(root).as_posix()
            if sensitive(rel) or not selected(rel) or any(fnmatch.fnmatch(rel, p) for p in patterns):
                continue
            if path.is_symlink():
                if strict:
                    raise HarnessError(f"Task scope contains a symlink file: {rel}")
                continue
            result.append(rel)
            if len(result) > limit:
                raise HarnessError("Repository file limit exceeded; narrow the task scope.")
    # Git's ignore rules are respected without interpreting them approximately.
    try:
        ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "--stdin", "-z"],
                                 input=("\x00".join(result) + "\x00").encode(),
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
        if ignored.returncode in (0, 1):
            excluded = set(ignored.stdout.decode("utf-8", errors="replace").split("\x00"))
            result = [p for p in result if p not in excluded]
    except (OSError, subprocess.TimeoutExpired):
        pass  # Common exclusions still apply when Git is unavailable.
    return sorted(result)


def file_hash(path: Path, max_bytes: int = 32 * 1024 * 1024) -> str:
    if not path.is_file() or path.is_symlink():
        raise HarnessError(f"Missing or unsupported source file: {path.name}")
    if path.stat().st_size > max_bytes:
        raise HarnessError(f"File exceeds fingerprint limit; narrow scope or explicitly ignore: {path.name}")
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_info(root: Path) -> dict:
    try:
        def run(*args):
            r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=5)
            return r.stdout.strip() if r.returncode == 0 else None
        return {"head": run("rev-parse", "HEAD"), "branch": run("branch", "--show-current")}
    except (OSError, subprocess.TimeoutExpired):
        return {"head": None, "branch": None}


def snapshot(root: Path, scopes: list[str]) -> dict:
    entries = {p: file_hash(safe_path(root, p)) for p in files(root, scopes, strict=True)}
    git = git_info(root)
    return {"files": entries, "git": git, "sha256": digest({"files": entries, "git": git})}
