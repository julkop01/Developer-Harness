"""Canonical, model-neutral host adapter contracts.

This module defines data shapes only. It does not activate host integrations,
grant tool authority, or claim that a host emits events it cannot actually emit.
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any
from urllib.parse import urlsplit, parse_qsl

from .util import HarnessError

SECRET_VALUE_PATTERNS = [
    re.compile(r"^sk-[A-Za-z0-9_-]{16,}$", re.I),
    re.compile(r"^ghp_[A-Za-z0-9]{16,}$"),
    re.compile(r"^github_pat_[A-Za-z0-9_]{16,}$"),
    re.compile(r"^gh[oprs]_[A-Za-z0-9]{16,}$"),
    re.compile(r"^AIza[A-Za-z0-9_-]{16,}$"),
    re.compile(r"^xox[baprs]-[A-Za-z0-9-]{10,}$"),
]
SECRET_FLAG = re.compile(r"(^|[-_])(api[-_]?key|apikey|token|secret|password|passwd|auth|credential|access[-_]?key|private[-_]?key)$", re.I)
SECRET_QUERY = re.compile(r"^(token|key|api[_-]?key|access[_-]?token|secret|password|auth)$", re.I)

PROTOCOLS = {
    "dh.session.v1": {
        "required": {
            "schema": str, "adapter": str, "session_id": str, "workspace": str,
            "status": str, "updated_at": str, "capabilities": list,
        },
        "optional": {"started_at": str, "task_id": (str, type(None)), "worktree": (str, type(None)), "metadata": dict},
        "enums": {"status": {"active", "idle", "stopped", "unknown"}},
    },
    "dh.tool_event.v1": {
        "required": {
            "schema": str, "adapter": str, "session_id": str, "event_id": str,
            "phase": str, "tool": str, "operation": str, "timestamp": str,
        },
        "optional": {
            "path": (str, type(None)), "exit_code": (int, type(None)),
            "duration_ms": (int, float, type(None)), "metadata": dict,
        },
        "enums": {"phase": {"before", "after", "failure"}},
    },
    "dh.context.v1": {
        "required": {
            "schema": str, "adapter": str, "session_id": str, "pressure": str,
            "unit": str, "compacting": bool, "timestamp": str,
        },
        "optional": {
            "used": (int, float, type(None)), "limit": (int, float, type(None)),
            "metadata": dict,
        },
        "enums": {
            "pressure": {"normal", "high", "critical", "unknown"},
            "unit": {"tokens", "chars", "unknown"},
        },
    },
    "dh.permission.v1": {
        "required": {
            "schema": str, "adapter": str, "session_id": str, "request_id": str,
            "capability": str, "decision": str, "scope": str, "timestamp": str,
        },
        "optional": {"metadata": dict},
        "enums": {"decision": {"requested", "granted", "denied", "unknown"}},
    },
    "dh.mcp.v1": {
        "required": {
            "schema": str, "adapter": str, "name": str, "transport": str,
            "env_keys": list,
        },
        "optional": {
            "command": (str, type(None)), "args": list, "url": (str, type(None)),
            "scope": str, "metadata": dict,
        },
        "enums": {"transport": {"stdio", "http", "sse", "unknown"}},
    },
}

ADAPTERS = {
    "codex": {
        "label": "OpenAI Codex",
        "instruction_surface": "AGENTS.md",
        "native_bridge": False,
        "protocols": ["dh.session.v1", "dh.tool_event.v1", "dh.context.v1", "dh.permission.v1", "dh.mcp.v1"],
        "status": "contract-ready",
    },
    "claude": {
        "label": "Claude Code",
        "instruction_surface": "CLAUDE.md",
        "native_bridge": False,
        "protocols": ["dh.session.v1", "dh.tool_event.v1", "dh.context.v1", "dh.permission.v1", "dh.mcp.v1"],
        "status": "contract-ready",
    },
    "opencode": {
        "label": "OpenCode",
        "instruction_surface": "AGENTS.md",
        "native_bridge": False,
        "protocols": ["dh.session.v1", "dh.tool_event.v1", "dh.context.v1", "dh.permission.v1", "dh.mcp.v1"],
        "status": "contract-ready",
    },
    "gemini": {
        "label": "Gemini CLI",
        "instruction_surface": "GEMINI.md",
        "native_bridge": False,
        "protocols": ["dh.session.v1", "dh.tool_event.v1", "dh.context.v1", "dh.permission.v1", "dh.mcp.v1"],
        "status": "contract-ready",
    },
    "cursor": {
        "label": "Cursor",
        "instruction_surface": "AGENTS.md",
        "native_bridge": False,
        "protocols": ["dh.session.v1", "dh.tool_event.v1", "dh.context.v1", "dh.permission.v1", "dh.mcp.v1"],
        "status": "contract-ready",
    },
    "copilot": {
        "label": "GitHub Copilot",
        "instruction_surface": ".github/copilot-instructions.md",
        "native_bridge": False,
        "protocols": ["dh.session.v1", "dh.tool_event.v1", "dh.context.v1", "dh.permission.v1", "dh.mcp.v1"],
        "status": "contract-ready",
    },
}


def _nonempty(value: str, field: str) -> None:
    if not value.strip():
        raise HarnessError(f"Protocol field {field} must be nonempty text.")


def _validate_list_of_strings(value: Any, field: str) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise HarnessError(f"Protocol field {field} must be a string array.")


def _looks_secret(value: str) -> bool:
    if any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
        return True
    return (len(value) >= 32 and re.fullmatch(r"[A-Za-z0-9_+/=.-]+", value) is not None
            and re.search(r"[A-Za-z]", value) is not None and re.search(r"[0-9]", value) is not None
            and "/" not in value and "@" not in value)


def _reject_mcp_secrets(document: dict) -> None:
    args = document.get("args", [])
    for index, value in enumerate(args):
        if _looks_secret(value):
            raise HarnessError("MCP args must not contain secret-looking values.")
        inline = re.match(r"^(--?[A-Za-z0-9_-]+)=(.+)$", value)
        if inline and (SECRET_FLAG.search(inline.group(1).lstrip("-")) or _looks_secret(inline.group(2))):
            raise HarnessError("MCP args must not contain inline secret values.")
        if index and SECRET_FLAG.search(args[index - 1].lstrip("-")):
            raise HarnessError("MCP args must not contain values following secret-named flags.")
    url = document.get("url")
    if url:
        parsed = urlsplit(url)
        if parsed.username or parsed.password:
            raise HarnessError("MCP URLs must not contain userinfo credentials.")
        if any(SECRET_QUERY.search(key) for key, _ in parse_qsl(parsed.query, keep_blank_values=True)):
            raise HarnessError("MCP URLs must not contain credential query parameters.")


def validate(document: dict) -> dict:
    """Validate one canonical adapter document and return a defensive copy."""
    if not isinstance(document, dict):
        raise HarnessError("Protocol document must be an object.")
    schema = document.get("schema")
    if schema not in PROTOCOLS:
        raise HarnessError("Unknown adapter protocol schema.")
    spec = PROTOCOLS[schema]
    allowed = set(spec["required"]) | set(spec["optional"])
    unknown = set(document) - allowed
    missing = set(spec["required"]) - set(document)
    if unknown:
        raise HarnessError("Unknown protocol fields: " + ", ".join(sorted(unknown)))
    if missing:
        raise HarnessError("Missing protocol fields: " + ", ".join(sorted(missing)))
    for field, expected in {**spec["required"], **spec["optional"]}.items():
        if field not in document:
            continue
        value = document[field]
        if not isinstance(value, expected):
            raise HarnessError(f"Protocol field {field} has the wrong type.")
        if expected is str and field != "schema":
            _nonempty(value, field)
    for field in ("capabilities", "env_keys", "args"):
        if field in document:
            _validate_list_of_strings(document[field], field)
    for field, values in spec.get("enums", {}).items():
        if document[field] not in values:
            raise HarnessError(f"Protocol field {field} has unsupported value {document[field]!r}.")
    if schema == "dh.mcp.v1":
        if document["transport"] == "stdio" and not document.get("command"):
            raise HarnessError("stdio MCP entries require command.")
        if document["transport"] in {"http", "sse"} and not document.get("url"):
            raise HarnessError("HTTP/SSE MCP entries require url.")
        if any("=" in key or not key.strip() for key in document["env_keys"]):
            raise HarnessError("MCP env_keys may contain names only, never secret values.")
        _reject_mcp_secrets(document)
    if schema == "dh.context.v1":
        used, limit = document.get("used"), document.get("limit")
        if used is not None and used < 0 or limit is not None and limit <= 0:
            raise HarnessError("Context usage values must be nonnegative and limit must be positive.")
    if "adapter" in document and document["adapter"] not in ADAPTERS:
        raise HarnessError("Unknown adapter id.")
    return deepcopy(document)


def protocols() -> list[dict]:
    return [
        {
            "schema": name,
            "required": sorted(spec["required"]),
            "optional": sorted(spec["optional"]),
            "enums": {field: sorted(values) for field, values in spec.get("enums", {}).items()},
        }
        for name, spec in sorted(PROTOCOLS.items())
    ]


def adapters() -> list[dict]:
    return [{"id": name, **deepcopy(spec)} for name, spec in sorted(ADAPTERS.items())]
