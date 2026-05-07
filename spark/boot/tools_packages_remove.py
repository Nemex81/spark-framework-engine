"""Remove-group package tools — Sprint 3 D1.

Registers 2 MCP tools:
  scf_remove_package, scf_get_package_changelog.
"""
from __future__ import annotations

import logging
from typing import Any

from spark.core.constants import _CHANGELOGS_SUBDIR
from spark.core.utils import _extract_version_from_changelog


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
