# Modulo assets/collectors — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""Collectors per agenti engine e pacchetti — letture I/O dirette."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from spark.core.utils import parse_markdown_frontmatter
from spark.registry.store import PackageResourceStore


def _read_agent_summary(path: Path) -> str:
    """Return a short description for an agent file (frontmatter or first line)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    fm = parse_markdown_frontmatter(text)
    desc = str(fm.get("description") or "").strip()
    if desc:
        return desc[:200]
    body = text.split("---", 2)[-1] if text.startswith("---") else text
    for raw in body.splitlines():
        stripped = raw.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith(">"):
            return stripped[:200]
    return ""


def _collect_engine_agents(engine_root: Path) -> list[tuple[str, str]]:
    """Return ``[(name, owner_label)]`` for all agents declared by the engine manifest."""
    manifest_path = engine_root / "engine-manifest.json"
    if not manifest_path.is_file():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    agents = (manifest.get("mcp_resources") or {}).get("agents") or []
    if not isinstance(agents, list):
        return []
    owner = str(manifest.get("package", "spark-framework-engine"))
    return [(str(name), owner) for name in agents if isinstance(name, str)]


def _collect_package_agents(
    store: "PackageResourceStore",
    package_ids: Iterable[str],
) -> dict[str, list[tuple[str, str]]]:
    """Return ``{package_id: [(agent_name, summary), ...]}`` for installed packages."""
    out: dict[str, list[tuple[str, str]]] = {}
    for pkg_id in package_ids:
        names = store.list_resources(pkg_id, "agents")
        entries: list[tuple[str, str]] = []
        for name in names:
            path = store.resolve(pkg_id, "agents", name)
            summary = _read_agent_summary(path) if path is not None else ""
            entries.append((name, summary))
        if entries:
            out[pkg_id] = entries
    return out
