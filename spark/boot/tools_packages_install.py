"""Install-group package tools — Sprint 3 D1.

Registers 1 MCP tool:
  scf_install_package.

Returns ``scf_install_package`` so the facade can assign
``engine._install_package_tool_fn`` and pass it to the update sub-factory.

Module-level helpers (pure functions moved out of closure):
  _section_markers, _parse_section_markers, _render_package_section,
  _create_file_with_section, _update_package_section.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from spark.boot import install_helpers as _ih
from spark.core.constants import ENGINE_VERSION, _BOOTSTRAP_PACKAGE_ID, _BACKUPS_SUBDIR
from spark.core.models import (
    MERGE_STATUS_CLEAN,
    MERGE_STATUS_CONFLICT,
    MERGE_STATUS_IDENTICAL,
)
from spark.core.utils import _is_v3_package
from spark.manifest import (
    ManifestManager,
    _scf_backup_workspace,
    _scf_diff_workspace,
)
from spark.merge.sections import (
    _classify_copilot_instructions_format,
    _prepare_copilot_instructions_migration,
    _scf_section_merge,
    _scf_section_merge_text,
)
from spark.merge.validators import (
    _SUPPORTED_CONFLICT_MODES,
    _normalize_merge_text,
)
from spark.packages import _get_deployment_modes
from spark.workspace import (
    _read_update_policy_payload,
    _validate_update_mode,
)
from spark.boot.tools_bootstrap import _gateway_write_text

_log = logging.getLogger("spark-framework-engine")

__all__ = ["register_install_package_tools"]


# ── Module-level pure helpers (formerly closure-local in register_package_tools) ── #

def _section_markers(package_id: str) -> tuple[str, str]:
    """Return begin/end markers for the package-owned section inside a shared file."""
    return (
        f"<!-- SCF:SECTION:{package_id}:BEGIN -->",
        f"<!-- SCF:SECTION:{package_id}:END -->",
    )


def _parse_section_markers(text: str, package_id: str) -> tuple[int, int] | None:
    """Return the normalized content slice between package section markers, if present."""
    normalized_text = _normalize_merge_text(text)
    begin_marker, end_marker = _section_markers(package_id)
    begin_index = normalized_text.find(begin_marker)
    if begin_index < 0:
        return None

    content_start = begin_index + len(begin_marker)
    if content_start < len(normalized_text) and normalized_text[content_start] == "\n":
        content_start += 1

    end_index = normalized_text.find(end_marker, content_start)
    if end_index < 0:
        return None

    content_end = end_index
    if content_end > content_start and normalized_text[content_end - 1] == "\n":
        content_end -= 1
    return (content_start, content_end)


def _render_package_section(package_id: str, content: str) -> str:
    """Render one package-owned section bounded by SCF HTML comment markers."""
    begin_marker, end_marker = _section_markers(package_id)
    normalized_content = _normalize_merge_text(content)
    if normalized_content and not normalized_content.endswith("\n"):
        normalized_content = f"{normalized_content}\n"
    return f"{begin_marker}\n{normalized_content}{end_marker}\n"


def _create_file_with_section(file_path: str, package_id: str, content: str) -> str:
    """Create a new shared file that initially contains only the current package section."""
    _ih._validate_extend_policy_target(file_path)
    return _render_package_section(package_id, content)


def _update_package_section(existing_text: str, package_id: str, content: str) -> str:
    """Insert or replace only the current package section while preserving outer content."""
    normalized_existing = _normalize_merge_text(existing_text)
    parsed_section = _parse_section_markers(normalized_existing, package_id)
    rendered_section = _render_package_section(package_id, content)
    if parsed_section is None:
        stripped_existing = normalized_existing.rstrip("\n")
        if not stripped_existing:
            return rendered_section
        return f"{stripped_existing}\n\n{rendered_section}"

    begin_marker, end_marker = _section_markers(package_id)
    begin_index = normalized_existing.find(begin_marker)
    end_index = normalized_existing.find(end_marker, parsed_section[1])
    if begin_index < 0 or end_index < 0:
        return rendered_section
    section_end = end_index + len(end_marker)
    if section_end < len(normalized_existing) and normalized_existing[section_end] == "\n":
        section_end += 1
    return f"{normalized_existing[:begin_index]}{rendered_section}{normalized_existing[section_end:]}"


# ── Sub-factory ──────────────────────────────────────────────────────────── #

def register_install_package_tools(engine: Any, mcp: Any, tool_names: list[str]) -> Any:
    """Register ``scf_install_package`` and return the callable.

    The facade assigns ``engine._install_package_tool_fn`` to the returned
    value so that ``register_bootstrap_tools`` (called right after) can
    invoke it during workspace bootstrap.
    """
    ctx = engine._ctx
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
    _read_text_if_possible = _ih._read_text_if_possible
    _supports_stateful_merge = _ih._supports_stateful_merge
    _build_session_entry = _ih._build_session_entry
    _replace_session_entry = _ih._replace_session_entry
    _find_session_entry = _ih._find_session_entry
    _build_install_result = _ih._build_install_result
    _build_diff_summary = _ih._build_diff_summary
    _resolve_effective_update_mode = _ih._resolve_effective_update_mode
    _normalize_file_policies = _ih._normalize_file_policies
    _validate_extend_policy_target = _ih._validate_extend_policy_target

    # ── shims ────────────────────────────────────────────────────────────── #
    def _save_snapshots(package_id: str, files: list[tuple[str, Path]]) -> dict[str, list[str]]:
        """Shim: injects ``snapshots``."""
        return _ih._save_snapshots(package_id, files, snapshots)

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

    def _build_remote_file_records(
        package_id: str,
        pkg_version: str,
        pkg: dict[str, Any],
        pkg_manifest: dict[str, Any],
        files: list[str],
        file_policies: dict[str, str],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Shim: injects ``registry``."""
        return _ih._build_remote_file_records(
            package_id, pkg_version, pkg, pkg_manifest, files, file_policies, registry
        )

    def _build_update_flow_payload(
        package_id: str,
        pkg_version: str,
        conflict_mode: str,
        requested_update_mode: str,
        effective_update_mode: dict[str, Any],
        diff_summary: dict[str, Any],
    ) -> dict[str, Any]:
        """Shim: injects ``inventory``."""
        return _ih._build_update_flow_payload(
            package_id, pkg_version, conflict_mode, requested_update_mode,
            effective_update_mode, diff_summary, inventory
        )

    def _detect_workspace_migration_state() -> dict[str, Any]:
        """Shim: injects ``github_root`` and ``manifest``."""
        return _ih._detect_workspace_migration_state(ctx.github_root, manifest)

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

    # ── tool ─────────────────────────────────────────────────────────────── #

    @_register_tool("scf_install_package")
    async def scf_install_package(
        package_id: str,
        conflict_mode: str = "abort",
        update_mode: str = "",
        deployment_mode: str = "auto",
        migrate_copilot_instructions: bool = False,
    ) -> dict[str, Any]:
        """Install an SCF package from the public registry.

        Packages with min_engine_version >= 3.0.0 are installed in the
        engine store (v3 path). Legacy packages (< 3.0.0) are written
        directly into .github/ (v2 path).

        Args:
            package_id: Registry ID of the package to install.
            conflict_mode: How to handle file conflicts with untracked
                existing files. One of: abort, replace, manual, auto,
                assisted. Default: abort.
            update_mode: Update strategy for tracked files. One of: ask,
                integrative, replace, conservative, selective. Empty
                string delegates to the workspace update policy.
                Default: "".
            deployment_mode: Controls whether v3 package files are
                copied into .github/ after engine-store installation.
                One of:
                auto   — copies only if the manifest declares
                         standalone_copy=True;
                store  — engine store only, never copies;
                copy   — copies standalone_files from the manifest
                         (emits deployment_warning if none declared).
                Default: auto.
            migrate_copilot_instructions: When True, migrates
                copilot-instructions.md from legacy format to SCF-marker
                format before installing. Default: False.

        Returns:
            dict with at minimum:
                success (bool): True if installation completed.
                package (str): Package ID.
                version (str): Installed version.

            v3 path — additional keys on success:
                deployment_summary (dict):
                    engine_store (bool): True if stored in engine store.
                    standalone_copy (bool): True if files written to
                        .github/.
                    standalone_files_count (int): Files written count.
                deployment_notice (str): Present when
                    deployment_mode='auto' and manifest has no
                    standalone_copy. Mutually exclusive with
                    deployment_warning.
                deployment_warning (str): Present when
                    deployment_mode='copy' but manifest declares no
                    standalone_files. Mutually exclusive with
                    deployment_notice.
                standalone_files_written (list[str]): Files written.
                standalone_files_preserved (list[str]): Files skipped.
                standalone_files_errors (list[str]): Errors if any.

            v2 legacy path — additional keys on success:
                installed (list[str]): Files written to .github/.
                preserved (list[str]): Tracked files skipped.
                extended_files (list[str]): Section-merged files.
                delegated_files (list[str]): Files skipped by policy.
                replaced_files (list[str]): Replaced unconditionally.
                merge_clean (list[dict]): Cleanly merged files.
                merge_conflict (list[dict]): Unresolved conflicts.
                session_id (str | None): Active merge session ID.
                snapshot_written (list[str]): Snapshots saved.
                backup_path (str | None): Backup archive path.

            On action_required (success=True, install paused):
                action_required (str): One of:
                    authorize_github_write,
                    migrate_copilot_instructions,
                    choose_update_mode.
                message (str): Description of required action.

            On failure (success=False):
                error (str): Error description.
        """
        if conflict_mode not in _SUPPORTED_CONFLICT_MODES:
            return _build_install_result(
                False,
                error=(
                    f"Unsupported conflict_mode '{conflict_mode}'. "
                    "Supported modes: abort, replace, manual, auto, assisted."
                ),
                package=package_id,
                conflict_mode=conflict_mode,
            )
        _SUPPORTED_DEPLOYMENT_MODES = {"auto", "store", "copy"}
        if deployment_mode not in _SUPPORTED_DEPLOYMENT_MODES:
            return _build_install_result(
                False,
                error=(
                    f"Unsupported deployment_mode '{deployment_mode}'. "
                    "Supported modes: auto, store, copy."
                ),
                package=package_id,
                conflict_mode=conflict_mode,
            )
        requested_update_mode = ""
        if update_mode.strip():
            validated_update_mode = _validate_update_mode(
                update_mode,
                allow_selective=True,
            )
            if validated_update_mode is None:
                return _build_install_result(
                    False,
                    error=(
                        f"Unsupported update_mode '{update_mode}'. Supported modes: "
                        "ask, integrative, replace, conservative, selective."
                    ),
                    package=package_id,
                    conflict_mode=conflict_mode,
                    update_mode=update_mode,
                )
            requested_update_mode = validated_update_mode

        install_context = _get_package_install_context(package_id)
        if install_context.get("success") is False:
            return install_context

        pkg = install_context["pkg"]
        pkg_manifest = install_context["pkg_manifest"]
        files = install_context["files"]
        pkg_version = install_context["pkg_version"]
        min_engine_version = install_context["min_engine_version"]
        file_ownership_policy = install_context["file_ownership_policy"]
        file_policies = install_context["file_policies"]
        installed_versions = install_context["installed_versions"]
        missing_dependencies = install_context["missing_dependencies"]
        present_conflicts = install_context["present_conflicts"]
        engine_compatible = install_context["engine_compatible"]

        if not engine_compatible:
            return _build_install_result(
                False,
                error=(
                    f"Package '{package_id}' requires engine version >= {min_engine_version}."
                ),
                package=package_id,
                required_engine_version=min_engine_version,
                engine_version=ENGINE_VERSION,
            )
        if missing_dependencies:
            return _build_install_result(
                False,
                error=(
                    f"Package '{package_id}' requires missing dependencies: "
                    f"{', '.join(missing_dependencies)}"
                ),
                package=package_id,
                missing_dependencies=missing_dependencies,
                installed_packages=installed_versions,
            )
        if present_conflicts:
            return _build_install_result(
                False,
                error=(
                    f"Package '{package_id}' conflicts with installed packages: "
                    f"{', '.join(present_conflicts)}"
                ),
                package=package_id,
                present_conflicts=present_conflicts,
                installed_packages=installed_versions,
            )

        # Branch v3 lifecycle: pacchetti che dichiarano min_engine_version
        # >= 3.0.0 vengono installati nello store engine, non in workspace.
        if _is_v3_package(pkg_manifest):
            v3_result = await engine._install_package_v3(
                package_id=package_id,
                pkg=pkg,
                pkg_manifest=pkg_manifest,
                pkg_version=pkg_version,
                min_engine_version=min_engine_version,
                dependencies=install_context["dependencies"],
                conflict_mode=conflict_mode,
                build_install_result=_build_install_result,
            )
            # B.2: dopo install v3 applica standalone_files se richiesto.
            if v3_result.get("success") and deployment_mode != "store":
                modes = _get_deployment_modes(pkg_manifest)
                should_copy = (
                    deployment_mode == "copy"
                    or (deployment_mode == "auto" and modes.get("standalone_copy"))
                )
                if should_copy:
                    standalone_files_declared = modes.get("standalone_files", [])
                    if not standalone_files_declared and deployment_mode == "copy":
                        # copy esplicito ma manifest non dichiara standalone_files:
                        # avvisa senza bloccare l'installazione (store è comunque ok).
                        v3_result["deployment_warning"] = (
                            "deployment_mode='copy' richiesto, ma il manifest del pacchetto "
                            "non dichiara file standalone (standalone_files vuoto o assente). "
                            "Nessun file è stato scritto in .github/. "
                            "I file sono disponibili solo nell'engine store."
                        )
                        v3_result["deployment_summary"] = {
                            "engine_store": True,
                            "standalone_copy": False,
                            "standalone_files_count": 0,
                        }
                    else:
                        # Procedi normalmente con la copia standalone.
                        manifest_for_standalone = ManifestManager(ctx.github_root)
                        standalone_result = engine._install_standalone_files_v3(
                            package_id=package_id,
                            pkg_version=pkg_version,
                            pkg_manifest=pkg_manifest,
                            manifest=manifest_for_standalone,
                        )
                        v3_result["standalone_files_written"] = standalone_result.get(
                            "files_written", []
                        )
                        v3_result["standalone_files_preserved"] = standalone_result.get(
                            "preserved", []
                        )
                        if not standalone_result.get("success"):
                            v3_result["standalone_files_errors"] = standalone_result.get(
                                "errors", []
                            )
                        v3_result["deployment_summary"] = {
                            "engine_store": True,
                            "standalone_copy": True,
                            "standalone_files_count": len(
                                v3_result.get("standalone_files_written", [])
                            ),
                        }
                elif deployment_mode == "auto" and not modes.get("standalone_copy"):
                    # auto senza standalone_copy dichiarato: file solo nello store.
                    v3_result["deployment_notice"] = (
                        "Pacchetto installato solo nell'engine store. "
                        "I file NON sono stati scritti in .github/. "
                        "Per copiare i file nel workspace, "
                        "richiama scf_install_package con deployment_mode='copy'."
                    )
                    v3_result["deployment_summary"] = {
                        "engine_store": True,
                        "standalone_copy": False,
                        "standalone_files_count": 0,
                    }
            if deployment_mode == "store" and v3_result.get("success"):
                v3_result.setdefault(
                    "deployment_summary",
                    {
                        "engine_store": True,
                        "standalone_copy": False,
                        "standalone_files_count": 0,
                    },
                )
            return v3_result
        # Pacchetti legacy (< 3.0.0): warning su stderr e flusso v2 invariato.
        _log.warning(
            "[SPARK-ENGINE][WARNING] Package %s declares min_engine_version=%s; "
            "using legacy v2 file-copy install flow.",
            package_id,
            min_engine_version or "<unspecified>",
        )

        try:
            classification_report = _classify_install_files(
                package_id,
                files,
                file_policies=file_policies,
            )
        except ValueError as exc:
            return _build_install_result(
                False,
                error=str(exc),
                package=package_id,
                version=pkg_version,
                file_ownership_policy=file_ownership_policy,
            )
        ownership_conflicts = list(classification_report["ownership_issues"])
        if ownership_conflicts:
            return _build_install_result(
                False,
                error=(
                    f"Package '{package_id}' conflicts with files already owned by another package."
                ),
                package=package_id,
                version=pkg_version,
                file_ownership_policy=file_ownership_policy,
                effective_file_ownership_policy="error",
                conflicts=ownership_conflicts,
                conflicts_detected=classification_report["conflict_plan"],
                blocked_files=[item["file"] for item in classification_report["conflict_plan"]],
                requires_user_resolution=True,
            )

        remote_candidate_files = [
            str(item["file"])
            for item in classification_report["records"]
            if item.get("classification") != "delegate_skip"
        ]

        policy_payload, policy_source = _read_update_policy_payload(ctx.github_root)
        remote_files: list[dict[str, Any]] = []
        remote_fetch_errors: list[str] = []
        diff_records: list[dict[str, Any]] = []
        diff_summary = {"total": 0, "counts": {}, "files": []}
        if requested_update_mode or policy_source == "file":
            remote_files, remote_fetch_errors = _build_remote_file_records(
                package_id,
                pkg_version,
                pkg,
                pkg_manifest,
                remote_candidate_files,
                file_policies,
            )
            if remote_fetch_errors:
                return _build_install_result(
                    False,
                    package=package_id,
                    version=pkg_version,
                    delegated_files=[
                        str(item["file"])
                        for item in classification_report["delegate_plan"]
                        if item.get("classification") == "delegate_skip"
                    ],
                    conflicts_detected=classification_report["conflict_plan"],
                    errors=remote_fetch_errors,
                )

            diff_records = _scf_diff_workspace(
                package_id,
                pkg_version,
                remote_files,
                manifest,
            )
            diff_summary = _build_diff_summary(diff_records)
        effective_update_mode = _resolve_effective_update_mode(
            package_id,
            requested_update_mode,
            diff_records,
            policy_payload,
            policy_source,
        )
        flow_payload = _build_update_flow_payload(
            package_id,
            pkg_version,
            conflict_mode,
            requested_update_mode,
            effective_update_mode,
            diff_summary,
        )
        if flow_payload["authorization_required"] and not flow_payload["github_write_authorized"]:
            return _build_install_result(
                True,
                action_required="authorize_github_write",
                message=(
                    "GitHub protected writes require authorization for this session before "
                    "installing package files under .github/."
                ),
                **flow_payload,
            )

        migration_state = _detect_workspace_migration_state()
        copilot_record = next(
            (
                item for item in remote_files
                if str(item.get("path", "")).strip() == ".github/copilot-instructions.md"
                and str(item.get("scf_merge_strategy", "replace")).strip() == "merge_sections"
            ),
            None,
        )
        copilot_format = str(
            migration_state.get("copilot_instructions", {}).get("current_format", "missing")
        ).strip() or "missing"
        requires_copilot_migration = copilot_record is not None and copilot_format in {
            "plain",
            "scf_markers_partial",
        }
        explicit_copilot_migration = requires_copilot_migration and migrate_copilot_instructions
        if requires_copilot_migration and not migrate_copilot_instructions:
            return _build_install_result(
                True,
                action_required="migrate_copilot_instructions",
                message=(
                    "copilot-instructions.md uses a legacy format. Confirm the explicit migration "
                    "before SPARK adds or updates SCF marker sections."
                ),
                current_format=copilot_format,
                proposed_format=(
                    "scf_markers_complete"
                    if copilot_format == "scf_markers_partial"
                    else "scf_markers"
                ),
                migration_state=migration_state,
                migrate_copilot_instructions=False,
                **flow_payload,
            )
        if requires_copilot_migration and not flow_payload["github_write_authorized"]:
            return _build_install_result(
                True,
                action_required="authorize_github_write",
                message=(
                    "Authorize writes under .github before migrating copilot-instructions.md "
                    "to the SCF marker format."
                ),
                current_format=copilot_format,
                proposed_format=(
                    "scf_markers_complete"
                    if copilot_format == "scf_markers_partial"
                    else "scf_markers"
                ),
                migration_state=migration_state,
                migrate_copilot_instructions=True,
                **flow_payload,
            )

        if flow_payload["policy_enforced"] and not flow_payload["auto_update"] and not requested_update_mode:
            return _build_install_result(
                True,
                action_required="choose_update_mode",
                message="Choose an update_mode to continue with the package install.",
                suggested_update_mode=(
                    "integrative"
                    if flow_payload["resolved_update_mode"] == "ask"
                    else flow_payload["resolved_update_mode"]
                ),
                **flow_payload,
            )

        if requested_update_mode in {"ask", "selective"} or (
            flow_payload["policy_enforced"] and flow_payload["resolved_update_mode"] in {"ask", "selective"}
        ):
            return _build_install_result(
                True,
                action_required="choose_update_mode",
                message="Choose an explicit update_mode to continue.",
                suggested_update_mode=(
                    "integrative"
                    if flow_payload["resolved_update_mode"] == "ask"
                    else None
                ),
                **flow_payload,
            )

        effective_conflict_mode = (
            "replace"
            if flow_payload["resolved_update_mode"] == "replace"
            else conflict_mode
        )
        unresolved_conflicts = [
            item
            for item in classification_report["conflict_plan"]
            if item.get("classification") == "conflict_untracked_existing"
            and not (
                explicit_copilot_migration
                and str(item.get("file", "")).strip() == ".github/copilot-instructions.md"
            )
        ]
        if unresolved_conflicts and effective_conflict_mode == "abort":
            return _build_install_result(
                False,
                error=(
                    f"Package '{package_id}' would overwrite existing untracked files. "
                    "Review conflicts and retry with conflict_mode='replace'."
                ),
                package=package_id,
                version=pkg_version,
                conflicts_detected=unresolved_conflicts,
                blocked_files=[item["file"] for item in unresolved_conflicts],
                requires_user_resolution=True,
                **flow_payload,
            )

        preserved = [item["file"] for item in classification_report["preserve_plan"]]
        if not remote_files:
            remote_files, remote_fetch_errors = _build_remote_file_records(
                package_id,
                pkg_version,
                pkg,
                pkg_manifest,
                remote_candidate_files,
                file_policies,
            )
            if remote_fetch_errors:
                return _build_install_result(
                    False,
                    package=package_id,
                    version=pkg_version,
                    delegated_files=[
                        str(item["file"])
                        for item in classification_report["delegate_plan"]
                        if item.get("classification") == "delegate_skip"
                    ],
                    preserved=preserved,
                    conflicts_detected=classification_report["conflict_plan"],
                    **flow_payload,
                    errors=remote_fetch_errors,
                )
        remote_files_by_path = {
            str(item.get("path", item.get("file", ""))): item for item in remote_files
        }
        staged_files: list[tuple[str, str, str, str, bool]] = []
        replaced_files: list[str] = []
        extended_files: list[str] = []
        adopted_bootstrap_files: list[str] = []
        adopted_bootstrap_rels: list[str] = []
        delegated_files = [
            str(item["file"])
            for item in classification_report["delegate_plan"]
            if item.get("classification") == "delegate_skip"
        ]
        merge_clean: list[dict[str, Any]] = []
        merge_conflict: list[dict[str, Any]] = []
        session_entries: list[dict[str, Any]] = []
        manifest_targets: list[tuple[str, Path]] = []
        snapshot_written: list[str] = []
        snapshot_skipped: list[str] = []
        merge_candidates = {
            str(item["file"])
            for item in classification_report["merge_plan"]
            if item.get("classification") == "merge_candidate"
        }
        used_manual_merge = False
        for item in classification_report["records"]:
            file_path = str(item["file"])
            item_classification = str(item["classification"])
            if item_classification == "preserve_tracked_modified":
                if flow_payload["resolved_update_mode"] == "replace":
                    replaced_files.append(file_path)
                else:
                    continue
            if item_classification == "update_tracked_clean" and flow_payload["resolved_update_mode"] == "conservative":
                preserved.append(file_path)
                continue
            if item_classification == "delegate_skip":
                continue
            if item_classification == "merge_candidate":
                if flow_payload["resolved_update_mode"] == "conservative":
                    preserved.append(file_path)
                    continue
                if effective_conflict_mode == "replace":
                    replaced_files.append(file_path)
                elif not _supports_stateful_merge(effective_conflict_mode):
                    preserved.append(file_path)
                    continue
            if item_classification == "conflict_cross_owner":
                continue
            if (
                item_classification == "conflict_untracked_existing"
                and effective_conflict_mode != "replace"
                and not (
                    explicit_copilot_migration
                    and file_path == ".github/copilot-instructions.md"
                )
            ):
                continue
            rel = file_path.removeprefix(".github/")
            if item_classification == "conflict_untracked_existing" and not explicit_copilot_migration:
                replaced_files.append(file_path)
            remote_file = remote_files_by_path.get(file_path)
            if remote_file is None:
                preserved.append(file_path)
                continue
            content = str(remote_file.get("content", ""))
            staged_files.append(
                (
                    file_path,
                    rel,
                    content,
                    item_classification,
                    bool(item.get("adopt_bootstrap_owner", False)),
                )
            )
        # --- Diff-based cleanup: remove files obsoleted by this update ---
        old_files: set[str] = {
            entry["file"]
            for entry in manifest.load()
            if entry.get("package") == package_id
        }
        new_files: set[str] = {f.removeprefix(".github/") for f in files if f}
        to_remove: set[str] = old_files - new_files
        removed_files: list[str] = []
        preserved_obsolete: list[str] = []
        for rel_path in sorted(to_remove):
            is_modified = manifest.is_user_modified(rel_path)
            file_abs = ctx.github_root / rel_path
            if is_modified:
                preserved_obsolete.append(rel_path)
                _log.warning("Obsolete file preserved (user-modified): %s", rel_path)
            else:
                if file_abs.is_file():
                    try:
                        file_abs.unlink()
                        removed_files.append(rel_path)
                        _log.info("Obsolete file removed: %s", rel_path)
                    except OSError as exc:
                        _log.warning("Cannot remove obsolete file %s: %s", rel_path, exc)
        # --- End diff-based cleanup ---
        installed: list[str] = []
        backups: dict[Path, str | None] = {}
        written_paths: list[tuple[str, str, Path]] = []
        session_payload: dict[str, Any] | None = None
        auto_validator_results: dict[str, Any] = {}
        backup_path: str | None = None
        if flow_payload["resolved_update_mode"] == "replace":
            files_to_backup = [
                (rel, ctx.workspace_root / file_path)
                for file_path, rel, _, _, _ in staged_files
                if (ctx.workspace_root / file_path).is_file()
            ]
            if files_to_backup:
                try:
                    backup_path = _scf_backup_workspace(
                        package_id,
                        files_to_backup,
                        backup_root=engine._runtime_dir / _BACKUPS_SUBDIR,
                    )
                except (OSError, ValueError) as exc:
                    return _build_install_result(
                        False,
                        error=f"Cannot create workspace backup: {exc}",
                        delegated_files=delegated_files,
                        preserved=preserved,
                        replaced_files=replaced_files,
                        conflicts_detected=classification_report["conflict_plan"],
                        **flow_payload,
                    )
        try:
            for file_path, rel, content, staged_classification, adopt_bootstrap_owner in staged_files:
                dest = ctx.workspace_root / file_path
                previous_content = _read_text_if_possible(dest) if dest.is_file() else None
                backups[dest] = previous_content

                remote_strategy = str(
                    remote_files_by_path.get(file_path, {}).get(
                        "scf_merge_strategy",
                        "replace",
                    )
                ).strip() or "replace"

                if remote_strategy == "merge_sections":
                    merge_base_text = previous_content or ""
                    if (
                        file_path == ".github/copilot-instructions.md"
                        and migrate_copilot_instructions
                        and _classify_copilot_instructions_format(merge_base_text) in {
                            "plain",
                            "scf_markers_partial",
                        }
                    ):
                        merge_base_text = _prepare_copilot_instructions_migration(merge_base_text)
                    next_text = _scf_section_merge_text(
                        content,
                        merge_base_text,
                        remote_strategy,
                        package_id,
                        pkg_version,
                    )
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    _gateway_write_text(
                        ctx.workspace_root,
                        rel,
                        next_text,
                        manifest,
                        package_id,
                        pkg_version,
                        remote_strategy,
                    )
                    written_paths.append((file_path, rel, dest))
                    manifest_targets.append((rel, dest))
                    installed.append(file_path)
                    if adopt_bootstrap_owner:
                        adopted_bootstrap_files.append(file_path)
                        adopted_bootstrap_rels.append(rel)
                    extended_files.append(file_path)
                    continue

                if staged_classification == "extend_section":
                    if dest.exists() and previous_content is None:
                        raise OSError(f"Cannot extend non-text file: {dest}")
                    if remote_strategy == "replace":
                        remote_strategy = "merge_sections"
                    next_text = _scf_section_merge(
                        content,
                        dest,
                        remote_strategy,
                        package_id,
                        pkg_version,
                    )
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    _gateway_write_text(
                        ctx.workspace_root,
                        rel,
                        next_text,
                        manifest,
                        package_id,
                        pkg_version,
                        remote_strategy,
                    )
                    written_paths.append((file_path, rel, dest))
                    manifest_targets.append((rel, dest))
                    installed.append(file_path)
                    if adopt_bootstrap_owner:
                        adopted_bootstrap_files.append(file_path)
                        adopted_bootstrap_rels.append(rel)
                    extended_files.append(file_path)
                    continue

                if file_path in merge_candidates and _supports_stateful_merge(effective_conflict_mode):
                    base_text = snapshots.load_snapshot(package_id, rel)
                    ours_text = previous_content
                    if base_text is None or ours_text is None:
                        preserved.append(file_path)
                        snapshot_skipped.append(file_path)
                        continue

                    used_manual_merge = effective_conflict_mode == "manual"
                    merge_result = merge_engine.diff3_merge(base_text, ours_text, content)
                    if merge_result.status in {MERGE_STATUS_CLEAN, MERGE_STATUS_IDENTICAL}:
                        merged_text = merge_result.merged_text
                        if merged_text != ours_text:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            _gateway_write_text(
                                ctx.workspace_root,
                                rel,
                                merged_text,
                                manifest,
                                package_id,
                                pkg_version,
                                remote_strategy,
                            )
                            written_paths.append((file_path, rel, dest))
                        merge_clean.append(
                            {
                                "file": file_path,
                                "status": merge_result.status,
                            }
                        )
                        manifest_targets.append((rel, dest))
                        installed.append(file_path)
                        if adopt_bootstrap_owner:
                            adopted_bootstrap_files.append(file_path)
                            adopted_bootstrap_rels.append(rel)
                        continue

                    merged_text = merge_engine.render_with_markers(merge_result)
                    if effective_conflict_mode in {"manual", "assisted"}:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        _gateway_write_text(
                            ctx.workspace_root,
                            rel,
                            merged_text,
                            manifest,
                            package_id,
                            pkg_version,
                            remote_strategy,
                        )
                        written_paths.append((file_path, rel, dest))
                    merge_conflict.append(
                        {
                            "file": file_path,
                            "status": merge_result.status,
                            "conflict_count": len(merge_result.conflicts),
                        }
                    )
                    session_entries.append(
                        _build_session_entry(
                            file_path,
                            rel,
                            base_text,
                            ours_text,
                            content,
                            merged_text,
                        )
                    )
                    continue

                dest.parent.mkdir(parents=True, exist_ok=True)
                _gateway_write_text(
                    ctx.workspace_root,
                    rel,
                    content,
                    manifest,
                    package_id,
                    pkg_version,
                    remote_strategy,
                )
                written_paths.append((file_path, rel, dest))
                manifest_targets.append((rel, dest))
                installed.append(file_path)
                if adopt_bootstrap_owner:
                    adopted_bootstrap_files.append(file_path)
                    adopted_bootstrap_rels.append(rel)

            if session_entries:
                session_payload = sessions.create_session(
                    package_id,
                    pkg_version,
                    session_entries,
                    conflict_mode=conflict_mode,
                )

                if conflict_mode == "auto":
                    auto_clean_entries: list[dict[str, Any]] = []
                    remaining_conflict_entries: list[dict[str, Any]] = []
                    for conflict in list(session_payload.get("files", [])):
                        conflict_id = str(conflict.get("conflict_id", "")).strip()
                        resolution = _propose_conflict_resolution(
                            session_payload,
                            conflict_id,
                            persist=False,
                        )
                        current = _find_session_entry(session_payload, conflict_id)
                        if current is None:
                            continue
                        current_index, current_entry = current
                        public_file = str(current_entry.get("file", "")).strip()
                        manifest_rel = str(current_entry.get("manifest_rel", "")).strip()
                        workspace_path = str(current_entry.get("workspace_path", public_file)).strip()
                        dest = ctx.workspace_root / workspace_path
                        validator_results = current_entry.get("validator_results")
                        if isinstance(validator_results, dict):
                            auto_validator_results[public_file] = validator_results

                        if resolution.get("success") is True:
                            proposed_text = str(current_entry.get("proposed_text", "") or "")
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            _gateway_write_text(
                                ctx.workspace_root,
                                manifest_rel,
                                proposed_text,
                                manifest,
                                package_id,
                                pkg_version,
                            )
                            written_paths.append((public_file, manifest_rel, dest))
                            current_entry["resolution_status"] = "approved"
                            _replace_session_entry(session_payload, current_index, current_entry)
                            auto_clean_entries.append(
                                {
                                    "file": public_file,
                                    "status": "auto_resolved",
                                }
                            )
                            continue

                        marker_text = _render_marker_text(current_entry)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        _gateway_write_text(
                            ctx.workspace_root,
                            manifest_rel,
                            marker_text,
                            manifest,
                            package_id,
                            pkg_version,
                        )
                        written_paths.append((public_file, manifest_rel, dest))
                        current_entry["resolution_status"] = "manual"
                        _replace_session_entry(session_payload, current_index, current_entry)
                        remaining_conflict_entries.append(
                            {
                                "file": public_file,
                                "status": MERGE_STATUS_CONFLICT,
                                "conflict_count": 1,
                            }
                        )

                    merge_clean.extend(auto_clean_entries)
                    merge_conflict = remaining_conflict_entries
                    if remaining_conflict_entries:
                        sessions.save_session(session_payload)
                    else:
                        for file_entry in list(session_payload.get("files", [])):
                            manifest_rel = str(file_entry.get("manifest_rel", "")).strip()
                            workspace_path = str(file_entry.get("workspace_path", "")).strip()
                            if manifest_rel and workspace_path:
                                manifest_targets.append(
                                    (manifest_rel, ctx.workspace_root / workspace_path)
                                )
                        session_payload = sessions.mark_status(
                            str(session_payload.get("session_id", "")).strip(),
                            "auto_completed",
                            session=session_payload,
                        )

            if manifest_targets:
                manifest_merge_strategies = {
                    manifest_rel: str(
                        remote_files_by_path.get(f".github/{manifest_rel}", {}).get(
                            "scf_merge_strategy",
                            "replace",
                        )
                    ).strip()
                    or "replace"
                    for manifest_rel, _ in manifest_targets
                }
                manifest.upsert_many(
                    package_id,
                    pkg_version,
                    manifest_targets,
                    merge_strategies_by_file=manifest_merge_strategies,
                )
                if adopted_bootstrap_rels:
                    manifest.remove_owner_entries(_BOOTSTRAP_PACKAGE_ID, adopted_bootstrap_rels)
                snapshot_report = _save_snapshots(package_id, manifest_targets)
                snapshot_written.extend(snapshot_report["written"])
                snapshot_skipped.extend(snapshot_report["skipped"])
        except OSError as exc:
            rollback_errors: list[str] = []
            for _, _, dest in reversed(written_paths):
                previous_content = backups.get(dest)
                try:
                    if previous_content is None:
                        if dest.is_file():
                            dest.unlink()
                    else:
                        dest.write_text(previous_content, encoding="utf-8")
                except OSError as rollback_exc:
                    rollback_errors.append(f"{dest}: {rollback_exc}")
            result: dict[str, Any] = {
                "success": False,
                "package": package_id,
                "version": pkg_version,
                "installed": [],
                "preserved": preserved,
                "removed_obsolete_files": removed_files,
                "preserved_obsolete_files": preserved_obsolete,
                "errors": [f"write failure: {exc}"],
                "rolled_back": len(rollback_errors) == 0,
            }
            if rollback_errors:
                result["rollback_errors"] = rollback_errors
            return result
        success_result: dict[str, Any] = _build_install_result(
            True,
            package=package_id,
            version=pkg_version,
            installed=installed,
            extended_files=extended_files,
            delegated_files=delegated_files,
            preserved=preserved,
            removed_obsolete_files=removed_files,
            preserved_obsolete_files=preserved_obsolete,
            replaced_files=replaced_files,
            adopted_bootstrap_files=adopted_bootstrap_files,
            merged_files=[item["file"] for item in merge_clean + merge_conflict],
            merge_clean=merge_clean,
            merge_conflict=merge_conflict,
            conflicts_detected=classification_report["conflict_plan"],
            session_id=None if session_payload is None else session_payload["session_id"],
            session_status=None if session_payload is None else session_payload["status"],
            session_expires_at=None if session_payload is None else session_payload["expires_at"],
            snapshot_written=snapshot_written,
            snapshot_skipped=snapshot_skipped,
            requires_user_resolution=len(merge_conflict) > 0,
            backup_path=backup_path,
            migration_state=migration_state if requires_copilot_migration else None,
            resolution_applied=(
                "auto"
                if effective_conflict_mode == "auto" and not merge_conflict and session_payload is not None
                else "manual"
                if effective_conflict_mode == "auto" and merge_conflict
                else "assisted"
                if effective_conflict_mode == "assisted" and session_payload is not None
                else "manual"
                if used_manual_merge or (effective_conflict_mode == "manual" and session_payload is not None)
                else "replace" if replaced_files else "none"
            ),
            validator_results=auto_validator_results if auto_validator_results else None,
            remaining_conflicts=len(merge_conflict) if merge_conflict else None,
            **flow_payload,
        )
        return success_result

    return scf_install_package
