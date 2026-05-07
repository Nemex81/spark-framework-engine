"""Diagnostics-group package tools — Sprint 3 D1.

Registers 4 MCP tools:
  scf_resolve_conflict_ai, scf_approve_conflict,
  scf_reject_conflict, scf_finalize_update.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from spark.boot import install_helpers as _ih
from spark.merge import (
    MergeSessionManager,
    run_post_merge_validators,
)
from spark.boot.tools_bootstrap import _gateway_write_text


_log = logging.getLogger("spark-framework-engine")

__all__ = ["register_diagnostics_package_tools"]


def register_diagnostics_package_tools(engine: Any, mcp: Any, tool_names: list[str]) -> None:
    """Register 4 merge-conflict diagnostics tools."""
    ctx = engine._ctx
    manifest = engine._manifest
    merge_engine = engine._merge_engine
    snapshots = engine._snapshots
    sessions = engine._sessions

    def _register_tool(name: str) -> Any:
        tool_names.append(name)
        return mcp.tool()

    # ── install_helpers aliases ──────────────────────────────────────────── #
    _read_text_if_possible = _ih._read_text_if_possible
    _find_session_entry = _ih._find_session_entry
    _replace_session_entry = _ih._replace_session_entry
    _count_remaining_conflicts = _ih._count_remaining_conflicts

    # ── shims ────────────────────────────────────────────────────────────── #
    def _render_marker_text(file_entry: dict[str, Any]) -> str:
        """Shim: injects ``merge_engine``."""
        return _ih._render_marker_text(file_entry, merge_engine)

    def _propose_conflict_resolution(
        session: dict[str, Any],
        conflict_id: str,
        persist: bool = True,
    ) -> dict[str, Any]:
        """Shim: injects ``sessions``."""
        return _ih._propose_conflict_resolution(session, conflict_id, sessions, persist)

    def _save_snapshots(package_id: str, files: list[tuple[str, Path]]) -> dict[str, list[str]]:
        """Shim: injects ``snapshots``."""
        return _ih._save_snapshots(package_id, files, snapshots)

    # ── tools ─────────────────────────────────────────────────────────────── #

    @_register_tool("scf_resolve_conflict_ai")
    async def scf_resolve_conflict_ai(session_id: str, conflict_id: str) -> dict[str, Any]:
        """Proponi una risoluzione automatica conservativa per un conflitto di merge."""
        session = sessions.load_active_session(session_id)
        if session is None:
            return {
                "success": False,
                "error": "session_not_found",
                "session_id": session_id,
                "conflict_id": conflict_id,
            }

        session_status = str(session.get("status", "")).strip() or "unknown"
        if session_status != "active":
            return {
                "success": False,
                "error": "session_not_active",
                "session_id": session_id,
                "session_status": session_status,
                "conflict_id": conflict_id,
            }

        resolution = _propose_conflict_resolution(session, conflict_id)
        if resolution.get("error") == "conflict_not_found":
            return {
                "success": False,
                "error": "conflict_not_found",
                "session_id": session_id,
                "conflict_id": conflict_id,
            }

        return {
            "success": bool(resolution.get("success", False)),
            "session_id": session_id,
            "conflict_id": conflict_id,
            "proposed_text": resolution.get("proposed_text"),
            "validator_results": resolution.get("validator_results"),
            "resolution_status": resolution.get("resolution_status", "manual"),
            "fallback": resolution.get("fallback"),
            "reason": resolution.get("reason"),
        }

    @_register_tool("scf_approve_conflict")
    async def scf_approve_conflict(session_id: str, conflict_id: str) -> dict[str, Any]:
        """Approva e scrivi nel workspace una proposta gia' validata per un conflitto."""
        session = sessions.load_active_session(session_id)
        if session is None:
            return {
                "success": False,
                "error": "session_not_found",
                "session_id": session_id,
                "conflict_id": conflict_id,
            }

        session_status = str(session.get("status", "")).strip() or "unknown"
        if session_status != "active":
            return {
                "success": False,
                "error": "session_not_active",
                "session_id": session_id,
                "session_status": session_status,
                "conflict_id": conflict_id,
            }

        found = _find_session_entry(session, conflict_id)
        if found is None:
            return {
                "success": False,
                "error": "conflict_not_found",
                "session_id": session_id,
                "conflict_id": conflict_id,
            }

        index, file_entry = found
        proposed_text = file_entry.get("proposed_text")
        if not isinstance(proposed_text, str) or not proposed_text:
            return {
                "success": False,
                "error": "proposed_text_missing",
                "session_id": session_id,
                "conflict_id": conflict_id,
            }

        validator_results = file_entry.get("validator_results")
        if not isinstance(validator_results, dict):
            validator_results = run_post_merge_validators(
                proposed_text,
                str(file_entry.get("base_text", "") or ""),
                str(file_entry.get("ours_text", "") or ""),
                str(file_entry.get("file", file_entry.get("workspace_path", "")) or ""),
            )
        if not validator_results.get("passed", False):
            file_entry["validator_results"] = validator_results
            file_entry["resolution_status"] = "manual"
            _replace_session_entry(session, index, file_entry)
            sessions.save_session(session)
            return {
                "success": False,
                "error": "validator_failed",
                "session_id": session_id,
                "conflict_id": conflict_id,
                "validator_results": validator_results,
            }

        workspace_path = str(file_entry.get("workspace_path", "")).strip()
        manifest_rel = str(file_entry.get("manifest_rel", "")).strip() or workspace_path.removeprefix(".github/")
        owner_pkg = str(session.get("package", "")).strip()
        owner_version = str(session.get("package_version", "")).strip()
        dest = ctx.workspace_root / workspace_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        _gateway_write_text(
            ctx.workspace_root,
            manifest_rel,
            proposed_text,
            manifest,
            owner_pkg,
            owner_version,
        )

        file_entry["validator_results"] = validator_results
        file_entry["resolution_status"] = "approved"
        _replace_session_entry(session, index, file_entry)
        sessions.save_session(session)

        return {
            "success": True,
            "session_id": session_id,
            "conflict_id": conflict_id,
            "approved": True,
            "remaining_conflicts": _count_remaining_conflicts(session),
        }

    @_register_tool("scf_reject_conflict")
    async def scf_reject_conflict(session_id: str, conflict_id: str) -> dict[str, Any]:
        """Rifiuta una proposta e mantiene il file in fallback manuale con marker."""
        session = sessions.load_active_session(session_id)
        if session is None:
            return {
                "success": False,
                "error": "session_not_found",
                "session_id": session_id,
                "conflict_id": conflict_id,
            }

        session_status = str(session.get("status", "")).strip() or "unknown"
        if session_status != "active":
            return {
                "success": False,
                "error": "session_not_active",
                "session_id": session_id,
                "session_status": session_status,
                "conflict_id": conflict_id,
            }

        found = _find_session_entry(session, conflict_id)
        if found is None:
            return {
                "success": False,
                "error": "conflict_not_found",
                "session_id": session_id,
                "conflict_id": conflict_id,
            }

        index, file_entry = found
        marker_text = _render_marker_text(file_entry)
        workspace_path = str(file_entry.get("workspace_path", "")).strip()
        manifest_rel = str(file_entry.get("manifest_rel", "")).strip() or workspace_path.removeprefix(".github/")
        owner_pkg = str(session.get("package", "")).strip()
        owner_version = str(session.get("package_version", "")).strip()
        dest = ctx.workspace_root / workspace_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        _gateway_write_text(
            ctx.workspace_root,
            manifest_rel,
            marker_text,
            manifest,
            owner_pkg,
            owner_version,
        )

        file_entry["resolution_status"] = "rejected"
        _replace_session_entry(session, index, file_entry)
        sessions.save_session(session)

        return {
            "success": True,
            "session_id": session_id,
            "conflict_id": conflict_id,
            "rejected": True,
            "fallback": "manual",
            "remaining_conflicts": _count_remaining_conflicts(session),
        }

    @_register_tool("scf_finalize_update")
    async def scf_finalize_update(session_id: str) -> dict[str, Any]:
        """Finalize a manual merge session after the user resolves all conflict markers."""
        session = sessions.load_active_session(session_id)
        if session is None:
            return {
                "success": False,
                "error": f"Merge session '{session_id}' not found.",
                "session_id": session_id,
            }

        session_status = str(session.get("status", "")).strip() or "unknown"
        if session_status != "active":
            return {
                "success": False,
                "error": f"Merge session '{session_id}' is not active.",
                "session_id": session_id,
                "session_status": session_status,
            }

        package_id = str(session.get("package", "")).strip()
        package_version = str(session.get("package_version", "")).strip()
        pending: list[dict[str, Any]] = []
        written_files: list[str] = []
        manifest_targets: list[tuple[str, Path]] = []
        validator_results_map: dict[str, Any] = {}
        updated_session = dict(session)
        updated_files = list(updated_session.get("files", []))

        for index, file_entry in enumerate(list(session.get("files", []))):
            workspace_path = str(file_entry.get("workspace_path", "")).strip()
            manifest_rel = str(file_entry.get("manifest_rel", "")).strip()
            public_file = str(file_entry.get("file", workspace_path)).strip()
            dest = ctx.workspace_root / workspace_path
            if not dest.is_file():
                pending.append({
                    "file": public_file,
                    "reason": "missing_file",
                })
                continue
            content = _read_text_if_possible(dest)
            if content is None:
                pending.append({
                    "file": public_file,
                    "reason": "unreadable_text",
                })
                continue
            if merge_engine.has_conflict_markers(content):
                pending.append({
                    "file": public_file,
                    "reason": "conflict_markers_present",
                })
                continue

            if isinstance(file_entry.get("validator_results"), dict):
                validator_results_map[public_file] = file_entry["validator_results"]

            updated_file_entry = dict(file_entry)
            updated_file_entry["resolution_status"] = "approved"
            updated_files[index] = MergeSessionManager._normalize_session_file_entry(updated_file_entry)
            written_files.append(public_file)
            manifest_targets.append((manifest_rel, dest))

        if pending:
            return {
                "success": False,
                "error": "Manual merge session still has unresolved files.",
                "session_id": session_id,
                "session_status": session_status,
                "manual_pending": pending,
            }

        manifest.upsert_many(package_id, package_version, manifest_targets)
        snapshot_report = _save_snapshots(package_id, manifest_targets)
        updated_session["files"] = updated_files
        finalized_session = sessions.mark_status(session_id, "finalized", session=updated_session)
        return {
            "success": True,
            "session_id": session_id,
            "session_status": None if finalized_session is None else finalized_session.get("status"),
            "written_files": written_files,
            "manifest_updated": [manifest_rel for manifest_rel, _ in manifest_targets],
            "snapshot_updated": snapshot_report["written"],
            "snapshot_skipped": snapshot_report["skipped"],
            "manual_pending": [],
            "validator_results": validator_results_map,
        }
