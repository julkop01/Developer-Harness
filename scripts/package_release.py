#!/usr/bin/env python3
"""Create a deterministic source ZIP and verify every manifested file."""
from pathlib import Path
import argparse
import hashlib
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", "__pycache__", "build", "dist", ".venv", ".harness", "developer_harness.egg-info"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    destination = Path(args.output).resolve()
    if destination.exists():
        parser.error("Output exists; use a new path.")
    files = sorted(p for p in ROOT.rglob("*") if p.is_file() and not any(x in EXCLUDED for x in p.relative_to(ROOT).parts)
                   and p.name != "MANIFEST.sha256" and p.resolve() != destination
                   and p.suffix not in {".pyc", ".zip"} and not p.name.endswith(".zip.sha256"))
    for path in files:
        if path.is_symlink() or path.name.startswith(".env") or path.suffix in {".key", ".pem", ".sqlite3"}:
            parser.error(f"Private or unsupported source path: {path.relative_to(ROOT)}")
    entries = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in files}
    manifest = "".join(hashlib.sha256(content).hexdigest() + "  " + rel + "\n" for rel, content in entries.items())
    entries["MANIFEST.sha256"] = manifest.encode()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for rel, content in sorted(entries.items()):
            entry = zipfile.ZipInfo("Developer-Harness/" + rel, date_time=(2026, 10, 24, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, content)
    with zipfile.ZipFile(destination) as archive:
        for rel, content in entries.items():
            assert archive.read("Developer-Harness/" + rel) == content, rel
    checksum = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(destination.suffix + ".sha256").write_text(checksum + "  " + destination.name + "\n", encoding="utf-8")
    print(f"Created {destination.name}: {len(entries)} files, SHA-256 {checksum}")


if __name__ == "__main__":
    main()
