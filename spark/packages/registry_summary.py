# Modulo packages/registry_summary — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""Helpers per estrarre informazioni public-friendly dal registry SCF."""
from __future__ import annotations

from typing import Any, Mapping


def _resolve_package_version(manifest_version: Any, registry_version: Any) -> str:
    """Prefer the package manifest version and fall back to the registry hint."""
    manifest_value = str(manifest_version or "").strip()
    if manifest_value:
        return manifest_value
    registry_value = str(registry_version or "").strip()
    if registry_value:
        return registry_value
    return "unknown"


def _get_registry_min_engine_version(package_entry: Mapping[str, Any]) -> str:
    """Return the canonical registry minimum engine version, accepting the legacy key."""
    return str(
        package_entry.get("min_engine_version", package_entry.get("engine_min_version", ""))
    ).strip()


def _build_registry_package_summary(package_entry: Mapping[str, Any]) -> dict[str, Any]:
    """Build the public summary payload for one registry package entry."""
    return {
        "id": package_entry.get("id"),
        "description": package_entry.get("description", ""),
        "latest_version": package_entry.get("latest_version", ""),
        "status": package_entry.get("status", "unknown"),
        "repo_url": package_entry.get("repo_url", ""),
        "min_engine_version": _get_registry_min_engine_version(package_entry),
    }
