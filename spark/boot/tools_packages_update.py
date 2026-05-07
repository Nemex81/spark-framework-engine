"""Update-group package tools — Sprint 3 D1.

Registers 4 MCP tools:
  scf_check_updates, scf_update_package, scf_update_packages, scf_apply_updates.

Receives ``scf_install_package`` and ``scf_plan_install`` as keyword-only
arguments from the facade to satisfy cross-submodule call dependencies.
"""
from __future__ import annotations

import logging
from typing import Any

from spark.boot import install_helpers as _ih
from spark.core.constants import ENGINE_VERSION
from spark.core.utils import (
    _resolve_dependency_update_order,
    _is_engine_version_compatible,
    _is_v3_package,
    _normalize_string_list,
)
from spark.merge.validators import _SUPPORTED_CONFLICT_MODES
from spark.packages import (
    _get_registry_min_engine_version,
    _resolve_package_version,
)
from spark.workspace import _validate_update_mode

_log = logging.getLogger("spark-framework-engine")

__all__ = ["register_update_package_tools"]


def register_update_package_tools(
    engine: Any,
    mcp: Any,
    tool_names: list[str],
    *,
    scf_install_package: Any,
    scf_plan_install: Any,
) -> None:
    """Register 4 update-group package tools.

    ``scf_install_package`` and ``scf_plan_install`` are callables from the
    install and query sub-factories respectively, passed by the facade to
    satisfy cross-submodule call dependencies.
    """
    ctx = engine._ctx
    # Infrastruttura factory — le seguenti catture
    # (inventory, merge_engine, snapshots, sessions) sono
    # mantenute per simmetria con gli altri sottomoduli e
    # come punti di estensione espliciti per tool futuri
    # nel gruppo update. Non rimuovere senza analisi
    # cross-modulo.
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
    _summarize_available_updates = _ih._summarize_available_updates
    _build_install_result = _ih._build_install_result

    # ── shims ────────────────────────────────────────────────────────────── #
    def _detect_workspace_migration_state() -> dict[str, Any]:
        """Shim: injects ``github_root`` and ``manifest``."""
        return _ih._detect_workspace_migration_state(ctx.github_root, manifest)

    def _get_package_install_context(package_id: str) -> dict[str, Any]:
        """Shim: injects ``registry`` and ``manifest``."""
        return _ih._get_package_install_context(package_id, registry, manifest)

    # ── private helper ───────────────────────────────────────────────────── #

    def _plan_package_updates(requested_package_id: str | None = None) -> dict[str, Any]:
        entries = manifest.load()
        if not entries:
            return {
                "success": True,
                "message": "No SCF packages installed via manifest.",
                "updates": [],
                "plan": {
                    "requested_package": requested_package_id,
                    "can_apply": False,
                    "order": [],
                    "blocked": [],
                },
            }
        try:
            reg_packages = registry.list_packages()
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"Registry unavailable: {exc}"}

        installed_versions = manifest.get_installed_versions()
        reg_index: dict[str, Any] = {p["id"]: p for p in reg_packages if "id" in p}
        updates: list[dict[str, Any]] = []
        manifest_cache: dict[str, dict[str, Any]] = {}
        dependency_map: dict[str, list[str]] = {}
        candidate_ids: set[str] = set()
        blocked: list[dict[str, Any]] = []

        for pkg_id in sorted(installed_versions):
            reg_entry = reg_index.get(pkg_id)
            if reg_entry is None:
                updates.append({
                    "package": pkg_id,
                    "status": "not_in_registry",
                    "installed": installed_versions[pkg_id],
                })
                continue

            installed_ver = installed_versions[pkg_id]
            registry_latest_ver = str(reg_entry.get("latest_version", "")).strip()
            pkg_manifest: dict[str, Any] | None = None
            manifest_error: str | None = None
            try:
                pkg_manifest = registry.fetch_package_manifest(reg_entry["repo_url"])
                manifest_cache[pkg_id] = pkg_manifest
            except Exception as exc:  # noqa: BLE001
                manifest_error = str(exc)

            latest_ver = _resolve_package_version(
                pkg_manifest.get("version", "") if pkg_manifest is not None else "",
                registry_latest_ver,
            )
            status = "up_to_date" if installed_ver == latest_ver else "update_available"
            update_entry: dict[str, Any] = {
                "package": pkg_id,
                "status": status,
                "installed": installed_ver,
                "latest": latest_ver,
                "registry_status": reg_entry.get("status", "unknown"),
            }

            if pkg_manifest is not None:
                if status == "update_available":
                    dependencies = _normalize_string_list(pkg_manifest.get("dependencies", []))
                    dependency_map[pkg_id] = dependencies
                    min_engine_version = str(
                        pkg_manifest.get(
                            "min_engine_version",
                            _get_registry_min_engine_version(reg_entry),
                        )
                    ).strip()
                    missing_dependencies = [
                        dependency for dependency in dependencies if dependency not in installed_versions
                    ]
                    engine_compatible = _is_engine_version_compatible(
                        ENGINE_VERSION,
                        min_engine_version,
                    )
                    update_entry["dependencies"] = dependencies
                    update_entry["missing_dependencies"] = missing_dependencies
                    update_entry["min_engine_version"] = min_engine_version
                    update_entry["engine_compatible"] = engine_compatible

                    if missing_dependencies:
                        update_entry["status"] = "blocked_missing_dependencies"
                        blocked.append({
                            "package": pkg_id,
                            "reason": "missing_dependencies",
                            "missing_dependencies": missing_dependencies,
                        })
                    elif not engine_compatible:
                        update_entry["status"] = "blocked_engine_version"
                        blocked.append({
                            "package": pkg_id,
                            "reason": "engine_version",
                            "required_engine_version": min_engine_version,
                            "engine_version": ENGINE_VERSION,
                        })
                    else:
                        candidate_ids.add(pkg_id)
            elif manifest_error is not None:
                update_entry["status"] = "metadata_unavailable"
                update_entry["error"] = f"Cannot fetch package manifest: {manifest_error}"
                blocked.append({
                    "package": pkg_id,
                    "reason": "metadata_unavailable",
                    "error": manifest_error,
                })

            updates.append(update_entry)

        selected_ids = set(candidate_ids)
        selected_blocked = list(blocked)
        if requested_package_id:
            matching_update = next(
                (item for item in updates if item.get("package") == requested_package_id),
                None,
            )
            if matching_update is None:
                return {
                    "success": False,
                    "error": f"Package '{requested_package_id}' is not installed.",
                    "updates": updates,
                }
            selected_ids = {requested_package_id} if requested_package_id in candidate_ids else set()
            selected_blocked = [
                item for item in blocked if item.get("package") == requested_package_id
            ]
            if requested_package_id in candidate_ids:
                pending = [requested_package_id]
                while pending:
                    current = pending.pop()
                    for dependency in dependency_map.get(current, []):
                        if dependency in candidate_ids and dependency not in selected_ids:
                            selected_ids.add(dependency)
                            pending.append(dependency)

        resolution = _resolve_dependency_update_order(list(selected_ids), dependency_map)
        if resolution["cycles"]:
            for pkg_id in resolution["cycles"]:
                selected_blocked.append({
                    "package": pkg_id,
                    "reason": "dependency_cycle",
                })

        plan_order: list[dict[str, Any]] = []
        for pkg_id in resolution["order"]:
            update_entry = next(item for item in updates if item.get("package") == pkg_id)
            plan_order.append({
                "package": pkg_id,
                "installed": update_entry.get("installed", ""),
                "target": update_entry.get("latest", ""),
                "dependencies": [
                    dependency
                    for dependency in dependency_map.get(pkg_id, [])
                    if dependency in selected_ids
                ],
            })

        summary = {
            "up_to_date": len([u for u in updates if u.get("status") == "up_to_date"]),
            "update_available": len([u for u in updates if u.get("status") == "update_available"]),
            "not_in_registry": len([u for u in updates if u.get("status") == "not_in_registry"]),
            "blocked": len(selected_blocked),
        }
        return {
            "success": True,
            "updates": updates,
            "total": len(updates),
            "summary": summary,
            "plan": {
                "requested_package": requested_package_id,
                "can_apply": len(plan_order) > 0 and len(selected_blocked) == 0,
                "order": plan_order,
                "blocked": selected_blocked,
            },
        }

    # ── tools ─────────────────────────────────────────────────────────────── #

    @_register_tool("scf_check_updates")
    async def scf_check_updates() -> dict[str, Any]:
        """Return only the installed SCF packages that have an update available."""
        report = _plan_package_updates()
        if report.get("success") is False:
            return report
        updates = _summarize_available_updates(report)
        return {
            "success": True,
            "count": len(updates),
            "updates": updates,
        }

    @_register_tool("scf_update_package")
    async def scf_update_package(
        package_id: str,
        conflict_mode: str = "abort",
        update_mode: str = "",
        migrate_copilot_instructions: bool = False,
    ) -> dict[str, Any]:
        """Update one installed SCF package while preserving user-modified files."""
        if conflict_mode not in _SUPPORTED_CONFLICT_MODES:
            return {
                "success": False,
                "error": (
                    f"Unsupported conflict_mode '{conflict_mode}'. "
                    "Supported modes: abort, replace, manual, auto, assisted."
                ),
                "package": package_id,
                "conflict_mode": conflict_mode,
            }

        if update_mode.strip():
            validated_update_mode = _validate_update_mode(
                update_mode,
                allow_selective=True,
            )
            if validated_update_mode is None:
                return {
                    "success": False,
                    "error": (
                        f"Unsupported update_mode '{update_mode}'. Supported modes: "
                        "ask, integrative, replace, conservative, selective."
                    ),
                    "package": package_id,
                    "conflict_mode": conflict_mode,
                    "update_mode": update_mode,
                }
            update_mode = validated_update_mode

        installed_versions = manifest.get_installed_versions()
        if package_id not in installed_versions:
            return {
                "success": False,
                "error": f"Package '{package_id}' is not installed.",
                "package": package_id,
            }

        version_from = installed_versions[package_id]
        # Branch v3: rileviamo subito se il pacchetto installato è v3_store
        # e in tal caso instradiamo allo handler dedicato senza passare
        # per il plan v2 (che assume scritture in workspace/.github/).
        existing_entries = manifest.load()
        v3_entry = next(
            (
                e
                for e in existing_entries
                if str(e.get("installation_mode", "")).strip() == "v3_store"
                and str(e.get("package", "")).strip() == package_id
            ),
            None,
        )
        if v3_entry is not None:
            install_context = _get_package_install_context(package_id)
            if install_context.get("success") is False:
                return install_context
            pkg_manifest_remote = install_context["pkg_manifest"]
            if not _is_v3_package(pkg_manifest_remote):
                return {
                    "success": False,
                    "package": package_id,
                    "error": (
                        f"Package '{package_id}' is locally installed as v3_store "
                        "but the registry version declares min_engine_version<3.0.0. "
                        "Mixed flows are not supported."
                    ),
                }
            v3_result = await engine._update_package_v3(
                package_id=package_id,
                pkg=install_context["pkg"],
                pkg_manifest=pkg_manifest_remote,
                pkg_version=install_context["pkg_version"],
                min_engine_version=install_context["min_engine_version"],
                dependencies=install_context["dependencies"],
                conflict_mode=conflict_mode,
                build_install_result=_build_install_result,
            )
            if isinstance(v3_result, dict):
                v3_result.setdefault("version_from", version_from)
                v3_result.setdefault("version_to", install_context["pkg_version"])
                v3_result.setdefault(
                    "already_up_to_date",
                    bool(v3_result.get("idempotent", False)),
                )
            return v3_result

        migration_state = _detect_workspace_migration_state()
        if (
            migration_state["legacy_workspace"]
            and migration_state["policy_source"] != "file"
            and not update_mode.strip()
        ):
            return {
                "success": True,
                "package": package_id,
                "version_from": version_from,
                "already_up_to_date": False,
                "action_required": "configure_update_policy",
                "available_update_modes": [
                    {
                        "value": "ask",
                        "label": "ask",
                        "recommended": True,
                        "description": "Keep auto_update disabled and ask before package updates.",
                    },
                    {
                        "value": "integrative",
                        "label": "integrative",
                        "recommended": False,
                        "description": "Enable automatic integrative updates for package files.",
                    },
                    {
                        "value": "conservative",
                        "label": "conservative",
                        "recommended": False,
                        "description": "Enable automatic conservative updates preserving local changes.",
                    },
                ],
                "recommended_update_mode": "ask",
                "migration_state": migration_state,
                "message": (
                    "Legacy workspace detected without spark-user-prefs.json. Configure the update "
                    "policy before applying package updates."
                ),
            }

        plan_report = _plan_package_updates(package_id)
        if plan_report.get("success") is False:
            return plan_report

        requested_update = next(
            (item for item in plan_report.get("updates", []) if item.get("package") == package_id),
            None,
        )
        if requested_update is None:
            return {
                "success": False,
                "error": f"Package '{package_id}' is not installed.",
                "package": package_id,
            }

        if requested_update.get("status") == "up_to_date":
            return {
                "success": True,
                "package": package_id,
                "already_up_to_date": True,
                "version_from": version_from,
                "version_to": version_from,
                "updated_files": [],
                "preserved_files": [],
            }

        blocked = [
            item for item in plan_report.get("plan", {}).get("blocked", [])
            if item.get("package") == package_id
        ]
        if blocked:
            return {
                "success": False,
                "package": package_id,
                "error": "Cannot update package because the update plan is blocked.",
                "blocked": blocked,
                "version_from": version_from,
                "version_to": requested_update.get("latest", version_from),
            }

        install_report = await scf_install_package(
            package_id,
            conflict_mode=conflict_mode,
            update_mode=update_mode,
            migrate_copilot_instructions=migrate_copilot_instructions,
        )
        if install_report.get("action_required"):
            return {
                "success": True,
                "package": package_id,
                "version_from": version_from,
                "version_to": requested_update.get("latest", version_from),
                "already_up_to_date": False,
                **install_report,
            }

        if install_report.get("success") is False:
            result = {
                "success": False,
                "package": package_id,
                "error": install_report.get("error", "unknown error"),
                "version_from": version_from,
                "version_to": requested_update.get("latest", version_from),
                "details": install_report,
            }
            if "conflicts_detected" in install_report:
                result["conflicts_detected"] = [
                    {
                        "package": package_id,
                        "conflicts": list(install_report.get("conflicts_detected", [])),
                    }
                ]
            return result

        preserved_files = list(install_report.get("preserved", [])) + list(
            install_report.get("preserved_obsolete_files", [])
        )
        return {
            "success": True,
            "package": package_id,
            "version_from": version_from,
            "version_to": install_report.get("version", requested_update.get("latest", version_from)),
            "updated_files": list(install_report.get("installed", [])),
            "preserved_files": preserved_files,
            "removed_obsolete_files": list(install_report.get("removed_obsolete_files", [])),
            "merged_files": list(install_report.get("merged_files", [])),
            "merge_clean": list(install_report.get("merge_clean", [])),
            "merge_conflict": list(install_report.get("merge_conflict", [])),
            "session_id": install_report.get("session_id"),
            "session_status": install_report.get("session_status"),
            "session_expires_at": install_report.get("session_expires_at"),
            "snapshot_written": list(install_report.get("snapshot_written", [])),
            "snapshot_skipped": list(install_report.get("snapshot_skipped", [])),
            "requires_user_resolution": bool(install_report.get("requires_user_resolution", False)),
            "resolution_applied": install_report.get("resolution_applied", "none"),
            "validator_results": install_report.get("validator_results"),
            "remaining_conflicts": install_report.get("remaining_conflicts"),
            "already_up_to_date": False,
            "resolved_update_mode": install_report.get("resolved_update_mode"),
            "update_mode_source": install_report.get("update_mode_source"),
            "policy_source": install_report.get("policy_source"),
            "authorization_required": bool(install_report.get("authorization_required", False)),
            "github_write_authorized": bool(install_report.get("github_write_authorized", False)),
            "diff_summary": install_report.get("diff_summary"),
            "backup_path": install_report.get("backup_path"),
        }

    @_register_tool("scf_update_packages")
    async def scf_update_packages() -> dict[str, Any]:
        """Check installed SCF packages for updates and build an ordered update preview."""
        return _plan_package_updates()

    @_register_tool("scf_apply_updates")
    async def scf_apply_updates(
        package_id: str | None = None,
        conflict_mode: str = "abort",
        migrate_copilot_instructions: bool = False,
    ) -> dict[str, Any]:
        """Apply package updates by reinstalling latest versions from the registry.

        If package_id is provided, applies the update only for that package.
        Otherwise applies all available updates.
        """
        if conflict_mode not in _SUPPORTED_CONFLICT_MODES:
            return {
                "success": False,
                "error": (
                    f"Unsupported conflict_mode '{conflict_mode}'. "
                    "Supported modes: abort, replace, manual, auto, assisted."
                ),
                "package": package_id,
                "conflict_mode": conflict_mode,
            }
        report = _plan_package_updates(package_id)
        if report.get("success") is False:
            return report
        plan = report.get("plan", {})
        plan_order = list(plan.get("order", []))
        blocked = list(plan.get("blocked", []))
        target_ids = [item.get("package", "") for item in plan_order if item.get("package")]
        if blocked:
            return {
                "success": False,
                "error": "Cannot apply updates because the update plan is blocked.",
                "plan": plan,
                "updates": report.get("updates", []),
            }
        if package_id and not target_ids:
            return {
                "success": False,
                "error": f"No update available for package '{package_id}'.",
                "updates": report.get("updates", []),
                "plan": plan,
            }
        if not target_ids:
            return {
                "success": True,
                "message": "No updates to apply.",
                "applied": [],
                "failed": [],
                "plan": plan,
            }
        preflight_reports: list[dict[str, Any]] = []
        batch_conflicts: list[dict[str, Any]] = []
        for pkg_id in target_ids:
            preview = await scf_plan_install(pkg_id)
            preflight_reports.append(preview)
            if preview.get("success") is False:
                return {
                    "success": False,
                    "error": f"Cannot preflight package '{pkg_id}' before apply.",
                    "applied": [],
                    "failed": [],
                    "plan": plan,
                    "preflight": preflight_reports,
                }
            preview_conflicts = list(preview.get("conflict_plan", []))
            if preview_conflicts and conflict_mode != "replace":
                batch_conflicts.append(
                    {
                        "package": pkg_id,
                        "conflicts": preview_conflicts,
                    }
                )
        if batch_conflicts:
            return {
                "success": False,
                "error": "Batch preflight detected unresolved conflicts. No files written.",
                "applied": [],
                "failed": [],
                "plan": plan,
                "batch_conflicts": batch_conflicts,
                "preflight": preflight_reports,
            }
        applied: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        for pkg_id in target_ids:
            result = await scf_install_package(
                pkg_id,
                conflict_mode=conflict_mode,
                migrate_copilot_instructions=migrate_copilot_instructions,
            )
            if result.get("success") is True:
                applied.append(result)
            else:
                failed.append({"package": pkg_id, "error": result.get("error", "unknown error")})
        return {
            "success": len(failed) == 0,
            "applied": applied,
            "failed": failed,
            "total_targets": len(target_ids),
            "plan": plan,
            "conflict_mode": conflict_mode,
        }
