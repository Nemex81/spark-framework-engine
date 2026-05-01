"""Pure utility functions — estratte da spark-framework-engine.py durante Fase 0.

Funzioni e regex pre-compilate prive di stato e prive di dipendenze su classi
del motore. Contengono solo helper di parsing, hashing, normalizzazione e
risoluzione di ordini di dipendenza.
"""
from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

_log: logging.Logger = logging.getLogger("spark-framework-engine")


def _utc_now() -> datetime:
    """Return the current UTC timestamp as an aware datetime."""
    return datetime.now(timezone.utc)


def _format_utc_timestamp(value: datetime) -> str:
    """Serialize an aware UTC datetime to the engine timestamp format."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc_timestamp(value: str) -> datetime | None:
    """Parse a stored UTC timestamp, returning None for invalid values."""
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _sha256_text(text: str) -> str:
    """Return the SHA-256 of a UTF-8 text payload."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_manifest_relative_path(path_value: str) -> str | None:
    """Normalize a package path to the manifest-relative form under .github/."""
    normalized = path_value.replace("\\", "/").strip()
    if not normalized:
        return None
    if normalized.startswith(".github/"):
        normalized = normalized[len(".github/") :]
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        return None

    candidate = PurePosixPath(normalized)
    parts = candidate.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return None
    return candidate.as_posix()


def _infer_scf_file_role(path_value: str) -> str:
    """Infer a default SCF file role from its package-relative path."""
    normalized = path_value.replace("\\", "/")
    if "/agents/" in f"/{normalized}" or normalized.endswith(".agent.md"):
        return "agent"
    if "/instructions/" in f"/{normalized}" or normalized.endswith(".instructions.md"):
        return "instruction"
    if "/skills/" in f"/{normalized}" or normalized.endswith("/SKILL.md") or normalized.endswith(".skill.md"):
        return "skill"
    if "/prompts/" in f"/{normalized}" or normalized.endswith(".prompt.md"):
        return "prompt"
    return "config"


# Pre-compiled patterns for YAML list detection in frontmatter.
_FM_INLINE_LIST_RE: re.Pattern[str] = re.compile(r"^\[(.+)\]$")
_FM_BLOCK_ITEM_RE: re.Pattern[str] = re.compile(r"^(\s+)-\s+(.*)")
_SEMVER_RE: re.Pattern[str] = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


def parse_markdown_frontmatter(content: str) -> dict[str, Any]:
    """Parse optional YAML-style frontmatter from markdown content.

    Supports scalar values (string, boolean, integer), inline lists
    ``key: [a, b, c]`` and block lists (key followed by ``  - value`` lines).
    """
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    result: dict[str, Any] = {}
    current_list_key: str | None = None
    for raw_line in parts[1].strip().splitlines():
        # Block list item (indented dash) — checked before stripping whitespace.
        block_m = _FM_BLOCK_ITEM_RE.match(raw_line)
        if block_m and current_list_key is not None:
            item = block_m.group(2).strip().strip('"').strip("'")
            if item:
                result[current_list_key].append(item)
            continue
        # Any non-item line closes the open block list.
        current_list_key = None
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, raw_value = line.partition(":")
        key = key.strip()
        value_str = raw_value.strip()
        # Inline list: key: [a, b]
        inline_m = _FM_INLINE_LIST_RE.match(value_str)
        if inline_m:
            items = [s.strip().strip('"').strip("'") for s in inline_m.group(1).split(",")]
            result[key] = [i for i in items if i]
            continue
        # Block list start: key: <empty>
        if not value_str:
            current_list_key = key
            result[key] = []
            continue
        # Scalar value.
        value_str = value_str.strip('"').strip("'")
        if value_str.lower() in ("true", "yes"):
            result[key] = True
        elif value_str.lower() in ("false", "no"):
            result[key] = False
        elif value_str.isdigit():
            result[key] = int(value_str)
        else:
            result[key] = value_str
    return result


def _extract_version_from_changelog(changelog_path: Path) -> str:
    """Extract the latest version string from a changelog markdown file."""
    if not changelog_path.is_file():
        _log.warning("Changelog not found: %s", changelog_path)
        return "unknown"
    try:
        text = changelog_path.read_text(encoding="utf-8")
    except OSError as exc:
        _log.error("Cannot read changelog %s: %s", changelog_path, exc)
        return "unknown"
    pattern = re.compile(
        r"^\s*#{1,3}\s+\[?(v?[\d]+\.[\d]+\.[\d]+[^\]\s]*)\]?",
        re.MULTILINE,
    )
    match = pattern.search(text)
    return match.group(1) if match else "unknown"


def _normalize_string_list(value: Any) -> list[str]:
    """Return a normalized list of non-empty strings."""
    if not isinstance(value, list):
        return []
    items = [str(item).strip() for item in value]
    return [item for item in items if item]


def _parse_semver_triplet(version: str) -> tuple[int, int, int] | None:
    """Parse the numeric core of a semantic version string."""
    match = _SEMVER_RE.match(version.strip())
    if match is None:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return (major, minor, patch)


def _is_engine_version_compatible(current_version: str, minimum_version: str) -> bool:
    """Return True when the current engine version satisfies the minimum version."""
    if not minimum_version.strip():
        return True
    current = _parse_semver_triplet(current_version)
    minimum = _parse_semver_triplet(minimum_version)
    if current is None or minimum is None:
        return False
    return current >= minimum


# v3 install threshold: pacchetti che dichiarano min_engine_version >= 3.0.0
# usano lo store centralizzato + McpResourceRegistry.
_V3_LIFECYCLE_MIN_ENGINE_VERSION: tuple[int, int, int] = (3, 0, 0)


def _is_v3_package(pkg_manifest: Mapping[str, Any]) -> bool:
    """Return True quando il pacchetto richiede il lifecycle v3 (store-based).

    Un pacchetto è considerato v3 se ``min_engine_version >= 3.0.0`` nel
    suo ``package-manifest.json``. Pacchetti con versione minore o assente
    ricadono sul flusso v2 di copia file in workspace/.github/.
    """
    raw = str(pkg_manifest.get("min_engine_version", "")).strip()
    if not raw:
        return False
    parsed = _parse_semver_triplet(raw)
    if parsed is None:
        return False
    return parsed >= _V3_LIFECYCLE_MIN_ENGINE_VERSION


def _resolve_dependency_update_order(
    target_ids: list[str],
    package_dependencies: dict[str, list[str]],
) -> dict[str, Any]:
    """Build a deterministic dependency-aware update order for selected packages."""
    unique_targets = sorted({pkg_id for pkg_id in target_ids if pkg_id})
    dependency_graph: dict[str, set[str]] = {pkg_id: set() for pkg_id in unique_targets}
    reverse_graph: dict[str, set[str]] = {pkg_id: set() for pkg_id in unique_targets}
    for pkg_id in unique_targets:
        for dependency in package_dependencies.get(pkg_id, []):
            if dependency in dependency_graph:
                dependency_graph[pkg_id].add(dependency)
                reverse_graph[dependency].add(pkg_id)

    ready = sorted([pkg_id for pkg_id, deps in dependency_graph.items() if not deps])
    ordered: list[str] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for dependent in sorted(reverse_graph[current]):
            dependency_graph[dependent].discard(current)
            if not dependency_graph[dependent] and dependent not in ordered and dependent not in ready:
                ready.append(dependent)
        ready.sort()

    cycles = sorted([pkg_id for pkg_id, deps in dependency_graph.items() if deps])
    return {
        "order": ordered,
        "cycles": cycles,
    }
