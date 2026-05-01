"""Update-policy helpers — SPARK Framework Engine.

Extracted to ``spark.workspace.policy`` during Phase 0 modular refactoring.
All symbols are re-exported from ``spark.workspace``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from spark.core.constants import _ALLOWED_UPDATE_MODES, _USER_PREFS_FILENAME

_log: logging.Logger = logging.getLogger("spark-framework-engine")


def _default_update_policy() -> dict[str, Any]:
    """Return the canonical workspace update policy defaults."""
    return {
        "auto_update": False,
        "default_mode": "ask",
        "mode_per_package": {},
        "mode_per_file_role": {},
        "last_changed": "",
        "changed_by_user": False,
    }


def _default_update_policy_payload() -> dict[str, Any]:
    """Wrap the default update policy in the persisted JSON payload shape."""
    return {"update_policy": _default_update_policy()}


def _update_policy_path(github_root: Path) -> Path:
    """Return the persisted workspace update policy path."""
    return github_root / _USER_PREFS_FILENAME


def _normalize_update_mode(mode: str) -> str:
    """Normalize an update mode token for validation and storage."""
    return mode.strip().lower()


def _validate_update_mode(mode: str, *, allow_selective: bool) -> str | None:
    """Validate and normalize one update mode token."""
    normalized = _normalize_update_mode(mode)
    if normalized not in _ALLOWED_UPDATE_MODES:
        return None
    if not allow_selective and normalized == "selective":
        return None
    return normalized


def _read_update_policy_payload(github_root: Path) -> tuple[dict[str, Any], str]:
    """Load the workspace update policy, falling back to defaults when missing or invalid."""
    policy_path = _update_policy_path(github_root)
    if not policy_path.is_file():
        return _default_update_policy_payload(), "default_missing"

    try:
        raw_payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning("spark-user-prefs.json unreadable, using defaults: %s", exc)
        return _default_update_policy_payload(), "default_corrupt"

    if not isinstance(raw_payload, dict):
        return _default_update_policy_payload(), "default_invalid"

    raw_policy = raw_payload.get("update_policy", raw_payload)
    if not isinstance(raw_policy, dict):
        return _default_update_policy_payload(), "default_invalid"

    policy = _default_update_policy()
    if isinstance(raw_policy.get("auto_update"), bool):
        policy["auto_update"] = raw_policy["auto_update"]

    default_mode = raw_policy.get("default_mode")
    if isinstance(default_mode, str):
        validated_mode = _validate_update_mode(default_mode, allow_selective=False)
        if validated_mode is not None:
            policy["default_mode"] = validated_mode

    mode_per_package = raw_policy.get("mode_per_package")
    if isinstance(mode_per_package, dict):
        policy["mode_per_package"] = {
            str(key).strip(): normalized_mode
            for key, value in mode_per_package.items()
            if str(key).strip()
            for normalized_mode in [_validate_update_mode(str(value), allow_selective=True)]
            if normalized_mode is not None
        }

    mode_per_file_role = raw_policy.get("mode_per_file_role")
    if isinstance(mode_per_file_role, dict):
        policy["mode_per_file_role"] = {
            str(key).strip(): normalized_mode
            for key, value in mode_per_file_role.items()
            if str(key).strip()
            for normalized_mode in [_validate_update_mode(str(value), allow_selective=True)]
            if normalized_mode is not None
        }

    last_changed = raw_policy.get("last_changed")
    if isinstance(last_changed, str):
        policy["last_changed"] = last_changed.strip()

    changed_by_user = raw_policy.get("changed_by_user")
    if isinstance(changed_by_user, bool):
        policy["changed_by_user"] = changed_by_user

    return {"update_policy": policy}, "file"


def _write_update_policy_payload(github_root: Path, payload: dict[str, Any]) -> Path:
    """Persist the workspace update policy payload to disk."""
    policy_path = _update_policy_path(github_root)
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return policy_path
