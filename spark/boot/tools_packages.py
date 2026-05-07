"""Factory module for package tool group (D.5).

Registers the following 15 MCP tools:
  scf_list_available_packages, scf_get_package_info, scf_list_installed_packages,
  scf_install_package, scf_check_updates, scf_update_package, scf_update_packages,
  scf_apply_updates, scf_plan_install, scf_remove_package, scf_get_package_changelog,
  scf_resolve_conflict_ai, scf_approve_conflict, scf_reject_conflict,
  scf_finalize_update.

The factory ``register_package_tools(engine, mcp, tool_names)`` is called from
``SparkFrameworkEngine.register_tools()`` after ``_init_runtime_objects()`` and
``register_policy_tools()``.  It sets ``engine._install_package_tool_fn`` so that
``register_bootstrap_tools`` (called right after) can invoke ``scf_install_package``.
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


def register_package_tools(engine: Any, mcp: Any, tool_names: list[str]) -> None:
    """Register 15 package lifecycle and conflict resolution tools into mcp.

    Sets ``engine._install_package_tool_fn`` so that ``register_bootstrap_tools``
    (called immediately after) can call ``scf_install_package`` during bootstrap.

    Args:
        engine: SparkFrameworkEngine instance.
        mcp: FastMCP instance.
        tool_names: Shared list to which tool names are appended on registration.
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

    # ─── install_helpers aliases and shims ──────────────────────────────── #
    _read_text_if_possible = _ih._read_text_if_possible
    _supports_stateful_merge = _ih._supports_stateful_merge
    _build_session_entry = _ih._build_session_entry
    _replace_session_entry = _ih._replace_session_entry
    _find_session_entry = _ih._find_session_entry
    _count_remaining_conflicts = _ih._count_remaining_conflicts
    _resolve_conflict_automatically = _ih._resolve_conflict_automatically
    _build_install_result = _ih._build_install_result
    _build_diff_summary = _ih._build_diff_summary
    _resolve_effective_update_mode = _ih._resolve_effective_update_mode
    _normalize_file_policies = _ih._normalize_file_policies
    _validate_extend_policy_target = _ih._validate_extend_policy_target
    _summarize_available_updates = _ih._summarize_available_updates

    def _save_snapshots(package_id: str, files: list[tuple[str, Path]]) -> dict[str, list[str]]:
        """Shim: injects ``snapshots`` from register_tools() scope."""
        return _ih._save_snapshots(package_id, files, snapshots)

    def _render_marker_text(file_entry: dict[str, Any]) -> str:
        """Shim: injects ``merge_engine`` from register_tools() scope."""
        return _ih._render_marker_text(file_entry, merge_engine)

    def _propose_conflict_resolution(
        session: dict[str, Any],
        conflict_id: str,
        persist: bool = True,
    ) -> dict[str, Any]:
        """Shim: injects ``sessions`` from register_tools() scope."""
        return _ih._propose_conflict_resolution(session, conflict_id, sessions, persist)

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

    # _build_install_result aliased above (pure helper)

    def _build_remote_file_records(
        package_id: str,
        pkg_version: str,
        pkg: dict[str, Any],
        pkg_manifest: dict[str, Any],
        files: list[str],
        file_policies: dict[str, str],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Shim: injects ``registry`` from register_tools() scope."""
        return _ih._build_remote_file_records(
            package_id, pkg_version, pkg, pkg_manifest, files, file_policies, registry
        )

    # _build_diff_summary aliased above (pure helper)

    # _resolve_effective_update_mode aliased above (pure helper)

    def _build_update_flow_payload(
        package_id: str,
        pkg_version: str,
        conflict_mode: str,
        requested_update_mode: str,
        effective_update_mode: dict[str, Any],
        diff_summary: dict[str, Any],
    ) -> dict[str, Any]:
        """Shim: injects ``inventory`` from register_tools() scope."""
        return _ih._build_update_flow_payload(
            package_id, pkg_version, conflict_mode, requested_update_mode,
            effective_update_mode, diff_summary, inventory
        )

    def _detect_workspace_migration_state() -> dict[str, Any]:
        """Shim: injects ``github_root`` and ``manifest`` from register_tools() scope."""
        return _ih._detect_workspace_migration_state(ctx.github_root, manifest)

    # _normalize_file_policies and _validate_extend_policy_target aliased above (pure helpers)

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
        _validate_extend_policy_target(file_path)
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

    def _get_package_install_context(package_id: str) -> dict[str, Any]:
        """Shim: injects ``registry`` and ``manifest`` from register_tools() scope."""
        return _ih._get_package_install_context(package_id, registry, manifest)

    def _classify_install_files(
        package_id: str,
        files: list[str],
        file_policies: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Shim: injects ``manifest``, ``workspace_root``, ``snapshots`` from register_tools() scope."""
        return _ih._classify_install_files(
            package_id, files, manifest, ctx.workspace_root, snapshots, file_policies
        )

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

    # D.3: inietta scf_install_package come callback per scf_bootstrap_workspace.
    engine._install_package_tool_fn = scf_install_package

    # _summarize_available_updates aliased above (pure helper)

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


