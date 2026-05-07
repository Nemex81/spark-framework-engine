"""Query-group package tools — Sprint 3 D1.

Registers 4 read-only MCP tools:
  scf_list_available_packages, scf_get_package_info,
  scf_list_installed_packages, scf_plan_install.

Returns ``scf_plan_install`` so the facade can pass it to
``register_update_package_tools`` (needed by ``scf_apply_updates``).
"""
from __future__ import annotations

import logging
from typing import Any

from spark.boot import install_helpers as _ih
from spark.core.constants import ENGINE_VERSION
from spark.core.utils import (
    _is_engine_version_compatible,
    _normalize_string_list,
)
from spark.packages import (
    _build_registry_package_summary,
    _get_registry_min_engine_version,
    _resolve_package_version,
)

_log = logging.getLogger("spark-framework-engine")

__all__ = ["register_query_package_tools"]


def register_query_package_tools(engine: Any, mcp: Any, tool_names: list[str]) -> Any:
    """Register 4 read-only package query tools.

    Returns ``scf_plan_install`` so the facade can pass it to the update
    sub-factory (needed by ``scf_apply_updates``).
    """
    ctx = engine._ctx
    # Infrastruttura factory: catturato per futura espansione
    # o simmetria con gli altri sottomoduli.
    inventory = engine._inventory
    manifest = engine._manifest
    registry = engine._registry_client
    merge_engine = engine._merge_engine
    snapshots = engine._snapshots
    sessions = engine._sessions

    def _register_tool(name: str) -> Any:
        tool_names.append(name)
        return mcp.tool()

    # ── install_helpers aliases ──────────────────────────────────────────── #
    _normalize_file_policies = _ih._normalize_file_policies

    # ── shims ────────────────────────────────────────────────────────────── #
    def _get_package_install_context(package_id: str) -> dict[str, Any]:
        """Shim: injects ``registry`` and ``manifest``."""
        return _ih._get_package_install_context(package_id, registry, manifest)

    def _classify_install_files(
        package_id: str,
        files: list[str],
        file_policies: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Shim: injects ``manifest``, ``workspace_root``, ``snapshots``."""
        return _ih._classify_install_files(
            package_id, files, manifest, ctx.workspace_root, snapshots, file_policies
        )

    # ── tools ────────────────────────────────────────────────────────────── #

    @_register_tool("scf_list_available_packages")
    async def scf_list_available_packages() -> dict[str, Any]:
        """List all packages currently available in the public SCF registry."""
        try:
            packages = registry.list_packages()
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"Registry unavailable: {exc}"}
        return {
            "success": True,
            "count": len(packages),
            "packages": [_build_registry_package_summary(p) for p in packages],
        }

    @_register_tool("scf_get_package_info")
    async def scf_get_package_info(package_id: str) -> dict[str, Any]:
        """Return detailed information for a package, including file manifest stats."""
        try:
            packages = registry.list_packages()
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"Registry unavailable: {exc}"}
        pkg = next((p for p in packages if p.get("id") == package_id), None)
        if pkg is None:
            return {
                "success": False,
                "error": f"Package '{package_id}' not found in registry.",
                "available": [p.get("id") for p in packages],
            }
        try:
            pkg_manifest = registry.fetch_package_manifest(pkg["repo_url"])
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "error": f"Cannot fetch package manifest: {exc}",
                "package": pkg,
            }
        files: list[str] = pkg_manifest.get("files", [])
        installed_versions = manifest.get_installed_versions()
        dependencies = _normalize_string_list(pkg_manifest.get("dependencies", []))
        conflicts = _normalize_string_list(pkg_manifest.get("conflicts", []))
        min_engine_version = str(
            pkg_manifest.get("min_engine_version", _get_registry_min_engine_version(pkg))
        ).strip()
        categories = {
            "root": 0,
            "agents": 0,
            "skills": 0,
            "instructions": 0,
            "prompts": 0,
            "other": 0,
        }
        for fp in files:
            if fp.startswith(".github/agents/"):
                categories["agents"] += 1
            elif fp.startswith(".github/skills/"):
                categories["skills"] += 1
            elif fp.startswith(".github/instructions/"):
                categories["instructions"] += 1
            elif fp.startswith(".github/prompts/"):
                categories["prompts"] += 1
            elif fp.startswith(".github/") and fp.count("/") == 1:
                categories["root"] += 1
            else:
                categories["other"] += 1
        return {
            "success": True,
            "package": {
                "id": pkg.get("id"),
                "description": pkg.get("description", ""),
                "repo_url": pkg.get("repo_url", ""),
                "latest_version": pkg.get("latest_version", ""),
                "status": pkg.get("status", "unknown"),
                "min_engine_version": _get_registry_min_engine_version(pkg),
                "tags": pkg.get("tags", []),
            },
            "manifest": {
                "schema_version": str(pkg_manifest.get("schema_version", "1.0")),
                "package": pkg_manifest.get("package", package_id),
                "version": _resolve_package_version(
                    pkg_manifest.get("version", ""),
                    pkg.get("latest_version", ""),
                ),
                "display_name": pkg_manifest.get("display_name", ""),
                "description": pkg_manifest.get("description", pkg.get("description", "")),
                "author": pkg_manifest.get("author", ""),
                "min_engine_version": min_engine_version,
                "dependencies": dependencies,
                "conflicts": conflicts,
                "file_ownership_policy": str(
                    pkg_manifest.get("file_ownership_policy", "error")
                ).strip()
                or "error",
                "file_policies": _normalize_file_policies(
                    pkg_manifest.get("file_policies", {})
                ),
                "changelog_path": str(pkg_manifest.get("changelog_path", "")).strip(),
                "file_count": len(files),
                "categories": categories,
                "files": files,
            },
            "compatibility": {
                "engine_version": ENGINE_VERSION,
                "engine_compatible": _is_engine_version_compatible(
                    ENGINE_VERSION,
                    min_engine_version,
                ),
                "installed_packages": installed_versions,
                "missing_dependencies": [
                    dependency
                    for dependency in dependencies
                    if dependency not in installed_versions
                ],
                "present_conflicts": [
                    conflict
                    for conflict in conflicts
                    if conflict in installed_versions
                ],
            },
        }

    @_register_tool("scf_list_installed_packages")
    async def scf_list_installed_packages() -> dict[str, Any]:
        """List packages currently installed in the active workspace."""
        entries = manifest.load()
        if not entries:
            return {"count": 0, "packages": []}
        grouped: dict[str, dict[str, Any]] = {}
        for entry in entries:
            pkg_id = entry.get("package", "")
            if not pkg_id:
                continue
            node = grouped.setdefault(
                pkg_id,
                {
                    "package": pkg_id,
                    "version": entry.get("package_version", ""),
                    "file_count": 0,
                    "files": [],
                },
            )
            node["file_count"] += 1
            node["files"].append(entry.get("file", ""))
        packages = sorted(grouped.values(), key=lambda x: str(x["package"]))
        return {"count": len(packages), "packages": packages}

    @_register_tool("scf_plan_install")
    async def scf_plan_install(package_id: str) -> dict[str, Any]:
        """Return a dry-run install plan for one SCF package without modifying the workspace."""
        install_context = _get_package_install_context(package_id)
        if install_context.get("success") is False:
            return install_context

        files = install_context["files"]
        pkg_version = install_context["pkg_version"]
        min_engine_version = install_context["min_engine_version"]
        dependencies = install_context["dependencies"]
        file_policies = install_context["file_policies"]
        installed_versions = install_context["installed_versions"]
        missing_dependencies = install_context["missing_dependencies"]
        present_conflicts = install_context["present_conflicts"]
        engine_compatible = install_context["engine_compatible"]
        try:
            classification_report = _classify_install_files(
                package_id,
                files,
                file_policies=file_policies,
            )
        except ValueError as exc:
            return {
                "success": False,
                "package": package_id,
                "version": pkg_version,
                "error": str(exc),
            }

        dependency_issues: list[dict[str, Any]] = []
        if not engine_compatible:
            dependency_issues.append(
                {
                    "reason": "engine_version",
                    "required_engine_version": min_engine_version,
                    "engine_version": ENGINE_VERSION,
                }
            )
        if missing_dependencies:
            dependency_issues.append(
                {
                    "reason": "missing_dependencies",
                    "missing_dependencies": missing_dependencies,
                }
            )
        if present_conflicts:
            dependency_issues.append(
                {
                    "reason": "declared_conflicts",
                    "present_conflicts": present_conflicts,
                }
            )

        return {
            "success": True,
            "package": package_id,
            "version": pkg_version,
            "write_plan": classification_report["write_plan"],
            "extend_plan": classification_report["extend_plan"],
            "delegate_plan": classification_report["delegate_plan"],
            "preserve_plan": classification_report["preserve_plan"],
            "conflict_plan": classification_report["conflict_plan"],
            "merge_plan": classification_report["merge_plan"],
            "dependency_issues": dependency_issues,
            "ownership_issues": classification_report["ownership_issues"],
            "installed_packages": installed_versions,
            "conflict_mode_required": classification_report["conflict_mode_required"],
            "can_install": len(dependency_issues) == 0 and len(classification_report["conflict_plan"]) == 0,
            "can_install_with_replace": len(dependency_issues) == 0 and classification_report["can_install_with_replace"],
            "supported_conflict_modes": ["abort", "replace", "manual", "auto", "assisted"],
            "engine_version": ENGINE_VERSION,
            "min_engine_version": min_engine_version,
            "dependencies": dependencies,
        }

    return scf_plan_install
