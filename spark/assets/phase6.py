# Modulo assets/phase6 — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""Orchestrazione Phase 6: applica gli asset di bootstrap nel workspace."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from spark.assets.collectors import _collect_engine_agents, _collect_package_agents
from spark.assets.rendering import (
    _render_agents_md,
    _render_clinerules,
    _render_plugin_agents_md,
    _render_project_profile_template,
    _extract_profile_summary,
)
from spark.registry.store import PackageResourceStore


def _apply_phase6_assets(
    workspace_root: Path,
    engine_root: Path,
    installed_packages: Iterable[str],
    github_write_authorized: bool,
) -> dict[str, Any]:
    """Generate AGENTS.md, AGENTS-{plugin}.md, .clinerules, project-profile.md.

    Idempotent: AGENTS.md uses safe-merge with SCF markers; AGENTS-{plugin}.md
    is rewritten on every run; .clinerules and project-profile.md are written
    only when missing. Returns a report dict.
    """
    report: dict[str, Any] = {
        "agents_md": None,
        "plugin_agents_md": [],
        "clinerules": None,
        "project_profile": None,
        "skipped": [],
    }
    if not github_write_authorized:
        report["skipped"].append("github_write_unauthorized")
        return report

    github_root = workspace_root / ".github"
    github_root.mkdir(parents=True, exist_ok=True)

    store = PackageResourceStore(engine_root)
    engine_agents = _collect_engine_agents(engine_root)
    package_agents = _collect_package_agents(store, list(installed_packages))

    # 1) AGENTS.md (safe-merge)
    agents_md_path = github_root / "AGENTS.md"
    existing = agents_md_path.read_text(encoding="utf-8") if agents_md_path.is_file() else None
    new_content = _render_agents_md(engine_agents, package_agents, existing)
    if existing != new_content:
        agents_md_path.write_text(new_content, encoding="utf-8")
        report["agents_md"] = "written"
    else:
        report["agents_md"] = "unchanged"

    # 2) AGENTS-{plugin}.md (always rewrite to keep in sync)
    for pkg_id, agents in package_agents.items():
        plugin_path = github_root / f"AGENTS-{pkg_id}.md"
        plugin_path.write_text(_render_plugin_agents_md(pkg_id, agents), encoding="utf-8")
        report["plugin_agents_md"].append(plugin_path.name)
    report["plugin_agents_md"].sort()

    # 3) project-profile.md (only if missing)
    profile_path = github_root / "project-profile.md"
    if not profile_path.is_file():
        profile_path.write_text(_render_project_profile_template(), encoding="utf-8")
        report["project_profile"] = "created"
    else:
        report["project_profile"] = "preserved"

    # 4) .clinerules (only if missing — never overwrite user content)
    clinerules_path = workspace_root / ".clinerules"
    if not clinerules_path.is_file():
        profile_text = (
            profile_path.read_text(encoding="utf-8")
            if profile_path.is_file() else ""
        )
        summary = _extract_profile_summary(profile_text)
        clinerules_path.write_text(_render_clinerules(summary), encoding="utf-8")
        report["clinerules"] = "created"
    else:
        report["clinerules"] = "preserved"

    return report
