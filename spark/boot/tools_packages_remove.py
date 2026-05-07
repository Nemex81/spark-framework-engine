"""Remove-group package tools — Sprint 3 D1.

Registers 2 MCP tools:
  scf_remove_package, scf_get_package_changelog.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from spark.boot import install_helpers as _ih
from spark.core.constants import ENGINE_VERSION, _BOOTSTRAP_PACKAGE_ID, _BACKUPS_SUBDIR, _CHANGELOGS_SUBDIR
from spark.core.models import (
    MERGE_STATUS_CLEAN,
    MERGE_STATUS_CONFLICT,
    MERGE_STATUS_IDENTICAL,
    MergeConflict,
    MergeResult,
)
from spark.core.utils import (
    _resolve_dependency_update_order,
    _extract_version_from_changelog,
    _format_utc_timestamp,
    _is_engine_version_compatible,
    _is_v3_package,
    _normalize_string_list,
    _utc_now,
)
from spark.manifest import (
    ManifestManager,
    SnapshotManager,
    WorkspaceWriteGateway,
    _normalize_remote_file_record,
    _scf_backup_workspace,
    _scf_diff_workspace,
)
from spark.merge import (
    MergeSessionManager,
    run_post_merge_validators,
    validate_completeness,
    validate_structural,
    validate_tool_coherence,
)
from spark.merge.sections import (
    _SCF_SECTION_HEADER,
    _classify_copilot_instructions_format,
    _prepare_copilot_instructions_migration,
    _scf_extract_merge_priority,
    _scf_iter_section_blocks,
    _scf_render_section,
    _scf_section_markers,
    _scf_section_merge,
    _scf_section_merge_text,
    _scf_split_frontmatter,
    _scf_strip_section,
    _section_markers_for_package,
    _strip_package_section,
)
from spark.merge.validators import (
    _MARKDOWN_HEADING_RE,
    _SUPPORTED_CONFLICT_MODES,
    _extract_frontmatter_block,
    _extract_markdown_headings,
    _normalize_merge_text,
    _resolve_disjoint_line_additions,
)
from spark.packages import (
    _build_registry_package_summary,
    _get_deployment_modes,
    _get_registry_min_engine_version,
    _install_package_v3_into_store,
    _list_orphan_overrides_for_package,
    _remove_package_v3_from_store,
    _resolve_package_version,
    _v3_overrides_blocking_update,
)
from spark.registry import (
    _V3_STORE_INSTALLATION_MODE,
    _build_package_raw_url_base,
    _resource_filename_candidates,
    _v3_store_sentinel_file,
)
from spark.workspace import (
    _V2_MIGRATION_DELETE_FILES,
    _V2_MIGRATION_DELETE_PATTERNS,
    _V2_MIGRATION_KEEP_DIRS,
    _V2_MIGRATION_KEEP_FILES,
    _V2_MIGRATION_OVERRIDE_DIRS,
    _classify_v2_workspace_file,
    _default_update_policy,
    _default_update_policy_payload,
    _normalize_update_mode,
    _read_update_policy_payload,
    _update_policy_path,
    _validate_update_mode,
    _write_update_policy_payload,
)
from spark.boot.tools_bootstrap import _gateway_write_bytes, _gateway_write_text
from spark.boot.tools_resources import _ff_to_dict

_log = logging.getLogger("spark-framework-engine")

__all__ = ["register_remove_package_tools"]


def register_remove_package_tools(engine: Any, mcp: Any, tool_names: list[str]) -> None:
    """Register 2 package remove/changelog tools."""
    ctx = engine._ctx
    inventory = engine._inventory
    manifest = engine._manifest
    snapshots = engine._snapshots

    def _register_tool(name: str) -> Any:
        tool_names.append(name)
        return mcp.tool()

    @_register_tool("scf_remove_package")
    async def scf_remove_package(package_id: str) -> dict[str, Any]:
        """Remove an installed SCF package from the workspace.

        Deletes all files installed by the package that have not been
        modified by the user. Modified files are preserved and reported.
        """
        installed = manifest.get_installed_versions()
        if package_id not in installed:
            return {
                "success": False,
                "error": (
                    f"Pacchetto '{package_id}' non trovato nel manifest. "
                    "Usa scf_list_installed_packages per vedere i pacchetti installati."
                ),
                "package": package_id,
            }
        # Branch v3: se l'entry installation_mode è v3_store usiamo
        # il path dedicato che pulisce store + registry + manifest.
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
            v3_result = await engine._remove_package_v3(
                package_id=package_id,
                manifest=manifest,
                v3_entry=v3_entry,
            )
            # Cleanup snapshot legacy se presenti (es. ex pacchetti v2).
            deleted_snapshots = snapshots.delete_package_snapshots(package_id)
            if isinstance(v3_result, dict):
                v3_result["deleted_snapshots"] = deleted_snapshots
                v3_result.setdefault("preserved_user_modified", [])
            return v3_result
        preserved = manifest.remove_package(package_id)
        deleted_snapshots = snapshots.delete_package_snapshots(package_id)
        return {
            "success": True,
            "package": package_id,
            "preserved_user_modified": preserved,
            "deleted_snapshots": deleted_snapshots,
        }

    @_register_tool("scf_get_package_changelog")
    async def scf_get_package_changelog(package_id: str) -> dict[str, Any]:
        """Return the changelog content for one installed SCF package."""
        content = inventory.get_package_changelog(package_id)
        if content is None:
            return {
                "success": False,
                "error": f"Changelog not found for package '{package_id}'.",
                "package": package_id,
            }
        changelog_path = ctx.github_root / _CHANGELOGS_SUBDIR / f"{package_id}.md"
        return {
            "package": package_id,
            "path": str(changelog_path),
            "content": content,
            "version": _extract_version_from_changelog(changelog_path),
        }
