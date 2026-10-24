"""Versioned, explicit project configuration. Discovery never executes code."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re

from .util import HarnessError, digest, read_json, safe_path

DEFAULT = {
    "schema_version": 1,
    "name": "My workspace",
    "purpose": "Personalize this workspace with your AI assistant.",
    "profile": "general",
    "communication": {"language": "en", "detail": "concise", "experience": "mixed"},
    "workflow": {"mode": "standard", "max_active_tasks": 2, "independent_review": False},
    "limits": {"context_chars": 16000, "max_checks_per_task": 20,
               "max_task_seconds": 1800, "max_log_bytes": 131072,
               "repeat_failure_limit": 3, "receipt_max_age_hours": 24},
    "budget": {"currency": "EUR", "limit_micros": 0},
    "commands": {},
    "required_checks": [],
    "integrations": [],
}
MODES = {"light", "standard", "assured"}
KEY = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def require(condition, message):
    if not condition:
        raise HarnessError("Configuration: " + message)


def validate(config: dict) -> dict:
    require(isinstance(config, dict), "root must be an object")
    require(set(config) == set(DEFAULT), "unknown or missing top-level fields; see config reference")
    require(type(config["schema_version"]) is int and config["schema_version"] == 1, "unsupported schema_version")
    for key in ("name", "purpose", "profile"):
        require(isinstance(config[key], str) and bool(config[key].strip()), f"{key} must be nonempty text")
    require(KEY.fullmatch(config["profile"]), "profile must be a lowercase slug")
    for group in ("communication", "workflow", "limits", "budget"):
        require(isinstance(config[group], dict) and set(config[group]) == set(DEFAULT[group]), f"invalid {group} fields")
    require(isinstance(config["workflow"]["mode"], str) and config["workflow"]["mode"] in MODES,
            "workflow.mode must be light, standard, or assured")
    require(type(config["workflow"]["independent_review"]) is bool, "independent_review must be boolean")
    require(type(config["workflow"]["max_active_tasks"]) is int and 1 <= config["workflow"]["max_active_tasks"] <= 20,
            "max_active_tasks must be between 1 and 20")
    for key, value in config["communication"].items():
        require(isinstance(value, str) and bool(value), f"communication.{key} must be text")
    ranges = {"context_chars": (2000, 200000), "max_checks_per_task": (1, 1000),
              "max_task_seconds": (1, 86400), "max_log_bytes": (1024, 10485760),
              "repeat_failure_limit": (1, 20), "receipt_max_age_hours": (1, 720)}
    for key, (low, high) in ranges.items():
        value = config["limits"][key]
        require(type(value) is int and low <= value <= high, f"limits.{key} must be an integer in [{low}, {high}]")
    require(config["budget"]["currency"] in ("EUR", "USD", "GBP"), "unsupported budget currency")
    require(type(config["budget"]["limit_micros"]) is int and config["budget"]["limit_micros"] >= 0,
            "limit_micros must be a nonnegative integer")
    require(isinstance(config["commands"], dict), "commands must be an object")
    for name, command in config["commands"].items():
        require(isinstance(name, str) and KEY.fullmatch(name), "invalid command name")
        require(isinstance(command, dict) and set(command) == {"argv", "timeout_seconds", "description"},
                f"{name}: expected argv, timeout_seconds, description")
        argv = command["argv"]
        require(isinstance(argv, list) and 1 <= len(argv) <= 100 and all(isinstance(x, str) and x and "\x00" not in x for x in argv),
                f"{name}: argv must be a nonempty string array")
        require(type(command["timeout_seconds"]) is int and 1 <= command["timeout_seconds"] <= 3600,
                f"{name}: timeout_seconds must be 1..3600")
        require(isinstance(command["description"], str) and command["description"].strip(), f"{name}: description required")
    require(isinstance(config["required_checks"], list) and all(isinstance(x, str) and x in config["commands"] for x in config["required_checks"]),
            "required_checks must name configured commands")
    require(isinstance(config["integrations"], list), "integrations must be a list")
    for item in config["integrations"]:
        require(isinstance(item, dict) and set(item) == {"name", "version", "purpose", "owner", "data_boundary", "rollback"},
                "integration must declare name, version, purpose, owner, data_boundary, rollback")
        require(all(isinstance(v, str) and v.strip() for v in item.values()), "integration fields cannot be empty")
    return config


def load(root: Path) -> dict:
    return validate(read_json(safe_path(root, ".harness/config.json")))


def config_hash(config: dict) -> str:
    return digest(config)


def make(profile: str = "general", name: str | None = None) -> dict:
    config = deepcopy(DEFAULT)
    directory = Path(__file__).resolve().parent / "resources" / "profiles"
    profile_file = safe_path(directory, profile + ".json")
    if not profile_file.is_file():
        raise HarnessError(f"Unknown profile: {profile}")
    patch = read_json(profile_file)
    config["profile"] = profile
    config["purpose"] = patch["purpose"]
    config["workflow"].update(patch.get("workflow", {}))
    if name:
        config["name"] = name
    return validate(config)
