#!/usr/bin/env python3
"""Deterministic distribution checks; does not replace behavior tests."""
from pathlib import Path
import ast
import json
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from developer_harness import __version__, config


def main():
    failures = []
    sources = list((ROOT / "developer_harness").rglob("*.py"))
    for source in sources:
        try:
            ast.parse(source.read_text(encoding="utf-8"), filename=str(source.relative_to(ROOT)))
        except SyntaxError as exc:
            failures.append(str(exc))
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    if metadata["project"]["version"] != __version__:
        failures.append("Version mismatch")
    release_notes = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    if not release_notes.startswith(f"# Developer Harness {__version__}\n"):
        failures.append("RELEASE_NOTES.md does not match the package version")
    for profile in (ROOT / "developer_harness/resources/profiles").glob("*.json"):
        try:
            config.make(profile.stem)
        except Exception as exc:
            failures.append(str(exc))
    markdown = [p for p in ROOT.rglob("*.md") if not any(d in p.parts for d in (".git", ".venv", "build", "dist", ".harness"))]
    for path in markdown:
        content = path.read_text(encoding="utf-8")
        for target in re.findall(r"!?\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)", content):
            if re.match(r"^(https?://|mailto:|#)", target):
                continue
            local = target.split("#", 1)[0]
            if local and not (path.parent / local).exists():
                failures.append(f"Broken local link in {path.relative_to(ROOT)}: {target}")
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.is_symlink():
            failures.append(f"Symlink in distribution: {path.relative_to(ROOT)}")
        if path.is_file() and (path.name.startswith(".env") or path.suffix in {".sqlite3", ".pem", ".key"}):
            failures.append(f"Private/runtime file in distribution: {path.relative_to(ROOT)}")
    required = ["README.md", "LICENSE", "START_HERE.md", "SECURITY.md", "CHANGELOG.md", "RELEASE_NOTES.md",
                "assets/github-banner.png", "assets/x-flyer.png", "assets/README.md", "examples/walkthrough.py"]
    for name in required:
        if not (ROOT / name).is_file():
            failures.append(f"Required release artifact missing: {name}")
    print(json.dumps({"ok": not failures, "version": __version__, "python_sources": len(sources),
                      "markdown_files": len(markdown), "failures": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
