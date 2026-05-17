"""Factory module for bootstrap tool group (D.3).

Registers the following 4 MCP tools:
  scf_verify_workspace, scf_verify_system, scf_bootstrap_workspace,
  scf_migrate_workspace.

The factory ``register_bootstrap_tools(engine, mcp, tool_names)`` is called
from ``SparkFrameworkEngine.register_tools()`` after ``scf_install_package``
has been defined and ``engine._install_package_tool_fn`` has been set.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from spark.core.constants import ENGINE_VERSION, _BOOTSTRAP_PACKAGE_ID
from spark.manifest import ManifestManager, WorkspaceWriteGateway, _scf_diff_workspace
from spark.merge.validators import _SUPPORTED_CONFLICT_MODES
from spark.packages import _get_registry_min_engine_version
from spark.assets import _apply_phase6_assets
from spark.workspace import (
    MigrationPlanner,
    _default_update_policy_payload,
    _read_update_policy_payload,
    _update_policy_path,
    _write_update_policy_payload,
)
from spark.boot import install_helpers as _ih
from spark.core.utils import (
    _infer_scf_file_role,
    _normalize_dependency_ids,
    _normalize_manifest_relative_path,
    _normalize_string_list,
    _sha256_text,
    _utc_now,
    parse_markdown_frontmatter,
)

if TYPE_CHECKING:
    from spark.boot.engine import SparkFrameworkEngine  # pragma: no cover

_log = logging.getLogger("spark-framework-engine")


def _resolve_local_manifest(engine_root: Path, package_id: str) -> dict[str, Any] | None:
    """Load the local package manifest from the engine packages store.

    Args:
        engine_root: Root directory of the SCF engine.
        package_id: Package identifier.

    Returns:
        Parsed manifest dict if found and readable, else None.
    """
    manifest_path = engine_root / "packages" / package_id / "package-manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning(
            "[SPARK-ENGINE][WARNING] Cannot read local manifest for '%s': %s",
            package_id,
            exc,
        )
        return None


def _classify_bootstrap_conflict(dest_path: Path) -> str:
    """Classifica il tipo di conflitto per un file preesistente nel workspace.

    Legge il frontmatter YAML del file esistente per determinare se è un file
    SPARK (con ``spark: true``) o un file utente/non-SPARK.

    Args:
        dest_path: Path assoluto del file preesistente nel workspace.

    Returns:
        ``"spark_outdated"`` se il file ha frontmatter ``spark: true``;
        ``"non_spark"`` altrimenti (nessun frontmatter, frontmatter diverso, file binario).
    """
    if dest_path.suffix != ".md":
        return "non_spark"
    try:
        content = dest_path.read_text(encoding="utf-8", errors="replace")
        fm = parse_markdown_frontmatter(content)
        if bool(fm.get("spark", False)):
            return "spark_outdated"
    except OSError:
        pass
    return "non_spark"


def _apply_frontmatter_only_update(
    source_path: Path,
    dest_path: Path,
) -> str | None:
    """Build merged content: frontmatter from *source_path*, body from *dest_path*.

    Reads the raw frontmatter block (between ``---`` markers) verbatim from
    the engine's canonical source file, and the body (everything after the
    closing ``---``) verbatim from the user's existing workspace file.
    Returns the concatenated result, preserving the user's body exactly.

    Args:
        source_path: Path to the engine's canonical version of the SPARK file.
        dest_path: Path to the user's existing file in the workspace.

    Returns:
        Merged content string on success; ``None`` if either file's frontmatter
        is malformed (missing closing ``---``) or cannot be read.
    """
    try:
        source_content = source_path.read_text(encoding="utf-8", errors="replace")
        dest_content = dest_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        _log.warning(
            "[SPARK-ENGINE][WARNING] frontmatter-only update: cannot read files: %s", exc
        )
        return None

    # Extract source frontmatter block as raw string (preserves exact formatting).
    if not source_content.startswith("---"):
        _log.warning(
            "[SPARK-ENGINE][WARNING] frontmatter-only update: source has no frontmatter: %s",
            source_path.name,
        )
        return None
    source_parts = source_content.split("---", 2)
    if len(source_parts) < 3:
        _log.warning(
            "[SPARK-ENGINE][WARNING] frontmatter-only update: source frontmatter unclosed: %s",
            source_path.name,
        )
        return None

    # Extract user body (everything after the second ---).
    # If dest has no frontmatter (cannot happen for spark_outdated files, but handle defensively).
    if dest_content.startswith("---"):
        dest_parts = dest_content.split("---", 2)
        user_body = dest_parts[2] if len(dest_parts) >= 3 else ""
    else:
        user_body = dest_content

    # Reconstruct: engine frontmatter block + user body.
    merged = "---" + source_parts[1] + "---" + user_body
    _log.info(
        "[SPARK-ENGINE][INFO] frontmatter-only merge prepared: %s <- %s",
        dest_path.name,
        source_path.name,
    )
    return merged


def _gateway_write_text(
    workspace_root: Path,
    github_rel: str,
    content: str,
    manifest_manager: ManifestManager,
    owner: str,
    version: str,
    merge_strategy: str | None = None,
) -> Path:
    """Route text writes under ``.github/`` through ``WorkspaceWriteGateway``."""
    gateway = WorkspaceWriteGateway(workspace_root, manifest_manager)
    return gateway.write(github_rel, content, owner, version, merge_strategy)


def _gateway_write_bytes(
    workspace_root: Path,
    github_rel: str,
    content: bytes,
    manifest_manager: ManifestManager,
    owner: str,
    version: str,
) -> Path:
    """Route binary writes under ``.github/`` through ``WorkspaceWriteGateway``."""
    gateway = WorkspaceWriteGateway(workspace_root, manifest_manager)
    return gateway.write_bytes(github_rel, content, owner, version)


def register_bootstrap_tools(
    engine: Any,
    mcp: Any,
    tool_names: list[str],
) -> None:
    """Register the 4 bootstrap MCP tools onto *mcp* and append their names to *tool_names*.

    Args:
        engine: SparkFrameworkEngine instance (typed ``Any`` to avoid circular import).
        mcp: FastMCP instance on which to register tools.
        tool_names: shared list tracking registered tool names.

    Precondition:
        ``engine._install_package_tool_fn`` must be set before calling this factory
        (satisfied by ``engine.py`` which sets it right after ``scf_install_package``
        is defined).
    """
    ctx = engine._ctx
    manifest = engine._manifest
    registry = engine._registry_client
    inventory = engine._inventory
    snapshots = engine._snapshots

    def _register_tool(name: str) -> Any:
        tool_names.append(name)
        return mcp.tool()

    # ------------------------------------------------------------------
    # Local shims (re-inject scope vars that were closures in engine.py)
    # ------------------------------------------------------------------

    def _detect_workspace_migration_state() -> dict[str, Any]:
        """Shim: injects ``github_root`` and ``manifest`` from factory scope."""
        return _ih._detect_workspace_migration_state(ctx.github_root, manifest)

    def _save_snapshots(
        package_id: str, files: list[tuple[str, Path]]
    ) -> dict[str, list[str]]:
        """Shim: injects ``snapshots`` from factory scope."""
        return _ih._save_snapshots(package_id, files, snapshots)

    def _build_remote_file_records(
        package_id: str,
        pkg_version: str,
        pkg: dict[str, Any],
        pkg_manifest: dict[str, Any],
        files: list[str],
        file_policies: dict[str, str],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Shim: injects ``registry`` from factory scope."""
        return _ih._build_remote_file_records(
            package_id, pkg_version, pkg, pkg_manifest, files, file_policies, registry
        )

    _build_diff_summary = _ih._build_diff_summary

    # ------------------------------------------------------------------
    # Universe A/B routing helpers
    # ------------------------------------------------------------------

    def _try_local_install_context(package_id: str) -> dict[str, Any] | None:
        """Probe Universe A: resolve package context from the local engine store.

        Returns a context dict with ``_universe="A"`` when the local
        ``packages/`` store has a manifest for *package_id* that declares
        ``delivery_mode=mcp_only``.  Returns ``None`` to signal that
        Universe B (remote registry) should be used instead.

        Args:
            package_id: Package identifier.

        Returns:
            Install context dict on success (Universe A), else None.
        """
        pkg_manifest = _resolve_local_manifest(ctx.engine_root, package_id)
        if pkg_manifest is None:
            return None
        if str(pkg_manifest.get("delivery_mode", "")).strip() != "mcp_only":
            return None
        files: list[str] = pkg_manifest.get("files", [])
        if not files:
            return None

        pkg_version = str(pkg_manifest.get("version", "")).strip()
        min_engine_version = str(pkg_manifest.get("min_engine_version", "")).strip()
        dependencies = _normalize_dependency_ids(pkg_manifest.get("dependencies", []))
        declared_conflicts = _normalize_string_list(pkg_manifest.get("conflicts", []))
        file_ownership_policy = (
            str(pkg_manifest.get("file_ownership_policy", "error")).strip() or "error"
        )
        file_policies = _ih._normalize_file_policies(
            pkg_manifest.get("file_policies", {}),
            pkg_manifest.get("files_metadata", []),
        )
        installed_versions = manifest.get_installed_versions()
        missing_dependencies = [d for d in dependencies if d not in installed_versions]
        present_conflicts = [c for c in declared_conflicts if c in installed_versions]

        _log.info(
            "[SPARK-ENGINE][INFO] Universe A: resolved '%s' from local store (delivery_mode=mcp_only).",
            package_id,
        )
        return {
            "success": True,
            "pkg": {"id": package_id, "latest_version": pkg_version, "status": "active"},
            "pkg_manifest": pkg_manifest,
            "files": files,
            "pkg_version": pkg_version,
            "min_engine_version": min_engine_version,
            "dependencies": dependencies,
            "declared_conflicts": declared_conflicts,
            "file_ownership_policy": file_ownership_policy,
            "file_policies": file_policies,
            "missing_dependencies": missing_dependencies,
            "present_conflicts": present_conflicts,
            "_universe": "A",
        }

    def _build_local_file_records(
        package_id: str,
        pkg_version: str,
        pkg_manifest: dict[str, Any],
        files: list[str],
        file_policies: dict[str, str],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Build file records from the local engine packages store (Universe A).

        Reads file content from disk (``packages/{package_id}/``) instead of
        fetching from a remote URL.  The returned record format is identical
        to ``_build_remote_file_records`` so the rest of the install flow
        remains unchanged.

        Args:
            package_id: Package identifier.
            pkg_version: Resolved package version string.
            pkg_manifest: Parsed package manifest dict.
            files: List of relative file paths declared in the manifest.
            file_policies: Per-file policy map.

        Returns:
            Tuple (local_files, read_errors).
        """
        store_root = ctx.engine_root / "packages" / package_id

        metadata_by_path: dict[str, dict[str, Any]] = {}
        raw_files_metadata = pkg_manifest.get("files_metadata", [])
        if isinstance(raw_files_metadata, list):
            for item in raw_files_metadata:
                if not isinstance(item, dict):
                    continue
                raw_path = str(item.get("path", "")).strip()
                normalized_rel = _normalize_manifest_relative_path(raw_path)
                if normalized_rel is None:
                    continue
                metadata_by_path[f".github/{normalized_rel}"] = item

        local_files: list[dict[str, Any]] = []
        read_errors: list[str] = []

        for file_path in files:
            metadata = metadata_by_path.get(file_path, {})
            merge_strategy = str(metadata.get("scf_merge_strategy", "")).strip()
            if not merge_strategy:
                policy = file_policies.get(file_path, "error")
                if policy == "extend":
                    merge_strategy = "merge_sections"
                elif policy == "delegate":
                    merge_strategy = "user_protected"
                else:
                    merge_strategy = "replace"

            try:
                merge_priority = int(metadata.get("scf_merge_priority", 0) or 0)
            except (TypeError, ValueError):
                merge_priority = 0

            local_path = store_root / file_path
            if not local_path.is_file():
                read_errors.append(
                    f"{file_path}: not found in local store {store_root}"
                )
                continue

            try:
                content = local_path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                read_errors.append(f"{file_path}: {exc}")
                continue

            local_files.append(
                {
                    "path": file_path,
                    "content": content,
                    "sha256": _sha256_text(content),
                    "scf_owner": (
                        str(metadata.get("scf_owner", package_id)).strip() or package_id
                    ),
                    "scf_version": (
                        str(metadata.get("scf_version", pkg_version)).strip() or pkg_version
                    ),
                    "scf_file_role": (
                        str(
                            metadata.get(
                                "scf_file_role",
                                _infer_scf_file_role(file_path.removeprefix(".github/")),
                            )
                        ).strip()
                        or _infer_scf_file_role(file_path.removeprefix(".github/"))
                    ),
                    "scf_merge_strategy": merge_strategy,
                    "scf_merge_priority": merge_priority,
                    "scf_protected": bool(metadata.get("scf_protected", False)),
                }
            )

        return local_files, read_errors

    def _get_package_install_context(package_id: str) -> dict[str, Any]:
        """Universe A/B router with registry injection.

        Probes the local engine store first (Universe A: delivery_mode=mcp_only).
        Falls back to the remote registry (Universe B) when the package is not
        present locally or does not declare ``delivery_mode=mcp_only``.
        """
        local_ctx = _try_local_install_context(package_id)
        if local_ctx is not None:
            return local_ctx
        return _ih._get_package_install_context(package_id, registry, manifest)

    # ------------------------------------------------------------------
    # Tool: scf_verify_workspace
    # ------------------------------------------------------------------

    @_register_tool("scf_verify_workspace")
    async def scf_verify_workspace() -> dict[str, Any]:
        """Verify runtime manifest integrity against files currently present in .github/."""
        report = manifest.verify_integrity()
        summary = dict(report.get("summary", {}))
        issue_count = int(summary.get("issue_count", 0))
        summary["is_clean"] = issue_count == 0
        report["summary"] = summary

        # C.1: source divergence report — confronta store vs workspace fisico.
        source_divergence: dict[str, Any] = {
            "only_in_store": [],
            "only_in_workspace": [],
            "divergent_content": [],
        }
        try:
            resolver = inventory._build_resolver()  # type: ignore[attr-defined]
            if resolver is not None:
                for resource_type in ("agents", "skills", "instructions", "prompts"):
                    merged = resolver.enumerate_merged(resource_type)
                    for name, path, source in merged:
                        if source == "store":
                            source_divergence["only_in_store"].append(
                                {"resource_type": resource_type, "name": name}
                            )
                        elif source == "workspace":
                            source_divergence["only_in_workspace"].append(
                                {"resource_type": resource_type, "name": name}
                            )
                        # source == "override": già nel workspace, non è divergenza
                if source_divergence["only_in_store"] or source_divergence["only_in_workspace"]:
                    _log.warning(
                        "[SPARK-ENGINE][WARNING] Source divergence: %d risorse solo in store, "
                        "%d solo in workspace fisico.",
                        len(source_divergence["only_in_store"]),
                        len(source_divergence["only_in_workspace"]),
                    )
        except Exception as exc:  # noqa: BLE001
            source_divergence["error"] = str(exc)
            _log.warning(
                "[SPARK-ENGINE][WARNING] Source divergence check failed: %s", exc
            )
        report["source_divergence"] = source_divergence
        return report

    # ------------------------------------------------------------------
    # Tool: scf_verify_system
    # ------------------------------------------------------------------

    @_register_tool("scf_verify_system")
    async def scf_verify_system() -> dict[str, Any]:
        """Verifica la coerenza cross-component tra motore, pacchetti e registry."""
        issues: list[dict[str, Any]] = []
        warnings: list[str] = []
        installed = manifest.get_installed_versions()

        if not installed:
            return {
                "engine_version": ENGINE_VERSION,
                "packages_checked": 0,
                "issues": [],
                "warnings": [],
                "manifest_empty": True,
                "is_coherent": True,
            }

        try:
            reg_packages = registry.list_packages()
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"Registry non raggiungibile: {exc}"}

        reg_index = {p["id"]: p for p in reg_packages if "id" in p}

        for pkg_id, _installed_ver in installed.items():
            reg_entry = reg_index.get(pkg_id)
            if reg_entry is None:
                warnings.append(f"Pacchetto '{pkg_id}' non trovato nel registry")
                continue
            try:
                pkg_manifest_data = registry.fetch_package_manifest(reg_entry["repo_url"])
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Manifest non raggiungibile per '{pkg_id}': {exc}")
                continue

            manifest_ver = str(pkg_manifest_data.get("version", "")).strip()
            registry_ver = str(reg_entry.get("latest_version", "")).strip()
            if manifest_ver != registry_ver:
                issues.append({
                    "type": "registry_stale",
                    "package": pkg_id,
                    "registry_version": registry_ver,
                    "manifest_version": manifest_ver,
                    "fix": f"Aggiornare registry.json: latest_version → {manifest_ver}",
                })

            min_engine_pkg = str(pkg_manifest_data.get("min_engine_version", "")).strip()
            min_engine_reg = _get_registry_min_engine_version(reg_entry)
            if min_engine_pkg and min_engine_reg and min_engine_pkg != min_engine_reg:
                issues.append({
                    "type": "engine_min_mismatch",
                    "package": pkg_id,
                    "registry_engine_min": min_engine_reg,
                    "manifest_engine_min": min_engine_pkg,
                    "fix": f"Aggiornare registry.json: min_engine_version → {min_engine_pkg}",
                })

        return {
            "engine_version": ENGINE_VERSION,
            "packages_checked": len(installed),
            "issues": issues,
            "warnings": warnings,
            "manifest_empty": False,
            "is_coherent": len(issues) == 0,
        }

    # ------------------------------------------------------------------
    # Tool: scf_bootstrap_workspace
    # ------------------------------------------------------------------

    @_register_tool("scf_bootstrap_workspace")
    async def scf_bootstrap_workspace(
        install_base: bool = False,
        conflict_mode: str = "abort",
        update_mode: str = "",
        migrate_copilot_instructions: bool = False,
        force: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Bootstrap the Layer 0 gateway files into this workspace.

        Copies the files declared in ``workspace_files`` of the spark-base manifest
        plus three discovery sentinels (AGENTS.md, spark-guide, spark-assistant)
        from the engine to the workspace.

        If a file exists and its sha256 differs from the source, it is NOT overwritten
        (reported in ``files_protected``) and a warning is logged to sys.stderr.
        Pass ``force=True`` to overwrite even user-modified files.
        Pass ``dry_run=True`` to simulate without writing any files.
        Idempotence is guaranteed via the spark-assistant.agent.md sentinel.

        Args:
            install_base: If True, also installs spark-base after bootstrap.
            conflict_mode: Conflict resolution mode for the install_base flow.
            update_mode: Update policy mode for the install_base flow.
            migrate_copilot_instructions: If True, migrate copilot-instructions.md.
            force: If True, overwrite even user-modified files (default False).
            dry_run: If True, simulate without writing any files (default False).

        Returns:
            A dict with at minimum these fields:
              status (str): operation status code.
              files_written (list): paths actually written (backward-compat).
              files_copied (list): paths written or would-be-written (dry_run).
              files_skipped (list): paths already present and unmodified.
              files_protected (list): user-modified paths skipped (need force=True).
              sentinel_present (bool): True if spark-assistant.agent.md exists.
              message (str): human-readable description of the operation outcome.
              preserved (list): all skipped paths (backward-compat superset).
              note (str): alias for message (backward-compat).
        """
        base_result: dict[str, Any] = {
            "status": "unknown",
            "message": "",
            "files_copied": [],
            "files_skipped": [],
            "files_protected": [],
            "sentinel_present": False,
        }
        if install_base and conflict_mode not in _SUPPORTED_CONFLICT_MODES:
            return {
                **base_result,
                "success": False,
                "status": "error",
                "message": (
                    f"Unsupported conflict_mode '{conflict_mode}'. "
                    "Supported modes: abort, replace, manual, auto, assisted."
                ),
                "files_written": [],
                "preserved": [],
                "workspace": str(ctx.workspace_root),
                "install_base_requested": install_base,
                "conflict_mode": conflict_mode,
                "note": (
                    f"Unsupported conflict_mode '{conflict_mode}'. "
                    "Supported modes: abort, replace, manual, auto, assisted."
                ),
            }
        normalized_bootstrap_mode = update_mode.strip().lower()
        from spark.core.constants import _BOOTSTRAP_UPDATE_MODES  # noqa: PLC0415
        allowed_bootstrap_modes: frozenset[str] = _BOOTSTRAP_UPDATE_MODES | {""}
        if normalized_bootstrap_mode not in allowed_bootstrap_modes:
            return {
                **base_result,
                "success": False,
                "status": "error",
                "message": (
                    f"Unsupported update_mode '{update_mode}'. Supported modes: "
                    "ask, integrative, conservative, ask_later."
                ),
                "files_written": [],
                "preserved": [],
                "workspace": str(ctx.workspace_root),
                "install_base_requested": install_base,
                "conflict_mode": conflict_mode,
                "update_mode": update_mode,
                "note": (
                    f"Unsupported update_mode '{update_mode}'. Supported modes: "
                    "ask, integrative, conservative, ask_later."
                ),
            }
        bootstrap_source_root = ctx.engine_root / "packages" / "spark-base" / ".github"
        if not bootstrap_source_root.is_dir():
            bootstrap_source_root = ctx.engine_root / ".github"
        agents_source_dir = bootstrap_source_root / "agents"
        workspace_github_root = ctx.github_root
        sentinel = workspace_github_root / "agents" / "Agent-Welcome.md"
        sentinel_rel = "agents/Agent-Welcome.md"
        policy_payload, policy_source = _read_update_policy_payload(ctx.github_root)
        migration_state = _detect_workspace_migration_state()
        legacy_bootstrap_mode = normalized_bootstrap_mode == ""

        def _bootstrap_policy_options() -> list[dict[str, Any]]:
            return [
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
                {
                    "value": "ask_later",
                    "label": "ask_later",
                    "recommended": False,
                    "description": "Create the policy file now and defer update mode choice to a later step.",
                },
            ]

        def _configure_initial_bootstrap_policy(selected_mode: str) -> tuple[dict[str, Any], Path]:
            pp = _default_update_policy_payload()
            policy = pp["update_policy"]
            if selected_mode == "integrative":
                policy["auto_update"] = True
                policy["default_mode"] = "integrative"
            elif selected_mode == "conservative":
                policy["auto_update"] = True
                policy["default_mode"] = "conservative"
            else:
                policy["auto_update"] = False
                policy["default_mode"] = "ask"
            policy["changed_by_user"] = True
            policy["last_changed"] = _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
            return pp, _write_update_policy_payload(ctx.github_root, pp)

        diff_summary: dict[str, Any] = {"total": 0, "counts": {}, "files": []}
        effective_install_update_mode = (
            "" if normalized_bootstrap_mode == "ask_later" else normalized_bootstrap_mode
        )
        policy_created = False
        policy_path = _update_policy_path(ctx.github_root)

        if not legacy_bootstrap_mode:
            if policy_source != "file":
                if normalized_bootstrap_mode == "":
                    return {
                        **base_result,
                        "success": True,
                        "status": "policy_configuration_required",
                        "message": "Configure the initial workspace update policy before running the extended bootstrap flow.",
                        "files_written": [],
                        "preserved": [],
                        "workspace": str(ctx.workspace_root),
                        "install_base_requested": install_base,
                        "conflict_mode": conflict_mode,
                        "update_mode": update_mode,
                        "action_required": "configure_update_policy",
                        "available_update_modes": _bootstrap_policy_options(),
                        "recommended_update_mode": "ask",
                        "policy_source": policy_source,
                        "migration_state": migration_state,
                        "note": "Configure the initial workspace update policy before running the extended bootstrap flow.",
                    }
                if migration_state["legacy_workspace"]:
                    orchestrator_state = inventory.get_orchestrator_state()
                    github_write_authorized = bool(
                        orchestrator_state.get("github_write_authorized", False)
                    )
                    if not github_write_authorized:
                        return {
                            **base_result,
                            "success": True,
                            "status": "authorization_required",
                            "message": "Authorize writes under .github before migrating this legacy workspace.",
                            "files_written": [],
                            "preserved": [],
                            "workspace": str(ctx.workspace_root),
                            "install_base_requested": install_base,
                            "conflict_mode": conflict_mode,
                            "update_mode": update_mode,
                            "resolved_update_mode": normalized_bootstrap_mode or None,
                            "policy_source": policy_source,
                            "policy_created": False,
                            "authorization_required": True,
                            "github_write_authorized": False,
                            "diff_summary": diff_summary,
                            "migration_state": migration_state,
                            "action_required": "authorize_github_write",
                            "note": "Authorize writes under .github before migrating this legacy workspace.",
                        }
                policy_payload, policy_path = _configure_initial_bootstrap_policy(
                    normalized_bootstrap_mode
                )
                policy_source = "file"
                policy_created = True

            if install_base:
                install_context = _get_package_install_context("spark-base")
                if install_context.get("success") is False:
                    return {
                        **base_result,
                        **install_context,
                        "status": "error",
                        "message": install_context.get("note", ""),
                        "files_written": [],
                        "files_copied": [],
                        "files_skipped": [],
                        "files_protected": [],
                        "sentinel_present": False,
                        "preserved": [],
                        "workspace": str(ctx.workspace_root),
                        "install_base_requested": install_base,
                        "conflict_mode": conflict_mode,
                        "update_mode": update_mode,
                        "policy_source": policy_source,
                    }
                if install_context.get("_universe") == "A":
                    remote_files, remote_fetch_errors = _build_local_file_records(
                        "spark-base",
                        install_context["pkg_version"],
                        install_context["pkg_manifest"],
                        install_context["files"],
                        install_context["file_policies"],
                    )
                else:
                    remote_files, remote_fetch_errors = _build_remote_file_records(
                        "spark-base",
                        install_context["pkg_version"],
                        install_context["pkg"],
                        install_context["pkg_manifest"],
                        install_context["files"],
                        install_context["file_policies"],
                    )
                if remote_fetch_errors:
                    return {
                        **base_result,
                        "success": False,
                        "status": "error",
                        "message": "Cannot build the spark-base bootstrap diff preview.",
                        "files_written": [],
                        "preserved": [],
                        "workspace": str(ctx.workspace_root),
                        "install_base_requested": install_base,
                        "conflict_mode": conflict_mode,
                        "update_mode": update_mode,
                        "policy_source": policy_source,
                        "errors": remote_fetch_errors,
                        "note": "Cannot build the spark-base bootstrap diff preview.",
                    }
                diff_summary = _build_diff_summary(
                    _scf_diff_workspace(
                        "spark-base",
                        install_context["pkg_version"],
                        remote_files,
                        manifest,
                    )
                )

            orchestrator_state_path = ctx.github_root / "runtime" / "orchestrator-state.json"
            if not orchestrator_state_path.is_file():
                inventory.set_orchestrator_state({"github_write_authorized": False})
            orchestrator_state = inventory.get_orchestrator_state()
            github_write_authorized = bool(
                orchestrator_state.get("github_write_authorized", False)
            )
            if not github_write_authorized:
                return {
                    **base_result,
                    "success": True,
                    "status": "authorization_required",
                    "message": "Authorize writes under .github before running the extended bootstrap flow.",
                    "files_written": [],
                    "preserved": [],
                    "workspace": str(ctx.workspace_root),
                    "install_base_requested": install_base,
                    "conflict_mode": conflict_mode,
                    "update_mode": update_mode,
                    "resolved_update_mode": normalized_bootstrap_mode or None,
                    "policy_source": policy_source,
                    "policy_created": policy_created,
                    "policy_path": str(policy_path),
                    "authorization_required": True,
                    "github_write_authorized": False,
                    "diff_summary": diff_summary,
                    "action_required": "authorize_github_write",
                    "note": "Authorize writes under .github before running the extended bootstrap flow.",
                }

        async def _finalize_bootstrap_result(result: dict[str, Any]) -> dict[str, Any]:
            result["install_base_requested"] = install_base
            result["conflict_mode"] = conflict_mode
            result["update_mode"] = update_mode
            result["policy_source"] = policy_source
            result["policy_created"] = policy_created
            if policy_created:
                result["policy_path"] = str(policy_path)
            # Task C fix: al primo bootstrap reale (files_written non vuota e nessuna
            # policy preesistente), crea update_policy.json con default sicuro "ask".
            if policy_source != "file" and len(result.get("files_written", [])) > 0:
                _, new_policy_path = _configure_initial_bootstrap_policy("ask")
                result["policy_source"] = "file"
                result["policy_created"] = True
                result["policy_path"] = str(new_policy_path)
            # v3.1 — New fields: backfill defaults for any caller path.
            result.setdefault("files_copied", result.get("files_written", []))
            result.setdefault("files_skipped", [])
            result.setdefault("files_protected", [])
            result.setdefault("files_conflict_non_spark", [])
            result.setdefault("files_conflict_spark_outdated", [])
            result.setdefault("spark_outdated_details", [])
            result.setdefault("files_updated_frontmatter_only", [])
            result.setdefault("sentinel_present", sentinel.is_file())
            result.setdefault("message", result.get("note", ""))
            if not legacy_bootstrap_mode:
                result["authorization_required"] = True
                result["github_write_authorized"] = True
                result["diff_summary"] = diff_summary

            # v3.0 — Phase 6 assets: AGENTS.md dinamico, .clinerules, profile.
            try:
                orchestrator_state_inner = inventory.get_orchestrator_state()
                write_authorized = bool(
                    orchestrator_state_inner.get("github_write_authorized", False)
                )
            except Exception:  # pragma: no cover - defensive
                write_authorized = False
            installed_for_phase6 = list(manifest.get_installed_versions().keys())
            try:
                _phase6_gateway = WorkspaceWriteGateway(ctx.workspace_root, manifest)
                phase6_report = _apply_phase6_assets(
                    ctx.workspace_root,
                    ctx.engine_root,
                    installed_for_phase6,
                    github_write_authorized=write_authorized,
                    gateway=_phase6_gateway,
                    engine_version=ENGINE_VERSION,
                )
                result["phase6_assets"] = phase6_report
            except OSError as exc:
                _log.warning("Phase 6 asset rendering failed: %s", exc)
                result["phase6_assets"] = {"error": str(exc)}

            if not install_base:
                return result

            installed_versions = manifest.get_installed_versions()
            if "spark-base" in installed_versions:
                result["base_install"] = {
                    "success": True,
                    "status": "already_installed",
                    "package": "spark-base",
                    "version": installed_versions["spark-base"],
                }
                result["note"] = f"{result['note']} spark-base is already installed."
                return result

            # D.3: usa il callback iniettato al posto della closure scf_install_package.
            install_pkg_fn = engine._install_package_tool_fn
            base_install = await install_pkg_fn(
                "spark-base",
                conflict_mode=conflict_mode,
                update_mode=effective_install_update_mode,
                migrate_copilot_instructions=migrate_copilot_instructions,
            )
            result["base_install"] = base_install
            if base_install.get("action_required"):
                result["bootstrap_status"] = result["status"]
                result["status"] = "base_install_action_required"
                result["note"] = "Bootstrap completed, but spark-base requires an additional action before installation can continue."
                return result
            if not base_install.get("success", False):
                result["success"] = False
                result["bootstrap_status"] = result["status"]
                result["status"] = "base_install_failed"
                result["note"] = (
                    "Bootstrap completed, but spark-base installation failed. "
                    f"Details: {base_install.get('error', 'unknown error')}"
                )
                return result

            result["bootstrap_status"] = result["status"]
            if result["status"] == "already_bootstrapped":
                result["status"] = "already_bootstrapped_and_installed"
                result["note"] = "Bootstrap assets already present and spark-base installed successfully."
            else:
                result["status"] = "bootstrapped_and_installed"
                result["note"] = "Bootstrap completed and spark-base installed successfully."
            return result

        # v3.0 FIX — Bootstrap perimeter restriction (Cat. A only).
        _SPARK_BASE_FALLBACK_WORKSPACE_FILES: list[str] = [
            ".github/copilot-instructions.md",
            ".github/instructions/framework-guard.instructions.md",
            ".github/instructions/git-policy.instructions.md",
            ".github/instructions/model-policy.instructions.md",
            ".github/instructions/personality.instructions.md",
            ".github/instructions/project-reset.instructions.md",
            ".github/instructions/spark-assistant-guide.instructions.md",
            ".github/instructions/verbosity.instructions.md",
            ".github/instructions/workflow-standard.instructions.md",
            ".github/project-profile.md",
            ".github/spark-packages.json",
        ]
        _SPARK_BASE_BOOTSTRAP_SENTINELS: list[str] = [
            ".github/AGENTS.md",
            ".github/agents/Agent-Welcome.md",
        ]

        def _load_bootstrap_workspace_files() -> list[str]:
            manifest_path = bootstrap_source_root.parent / "package-manifest.json"
            workspace_files: list[str] = []
            if manifest_path.is_file():
                try:
                    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    _log.warning(
                        "Bootstrap: unable to read spark-base manifest, "
                        "using fallback whitelist: %s",
                        exc,
                    )
                    payload = {}
                declared = payload.get("workspace_files") or []
                if isinstance(declared, list):
                    workspace_files = [
                        entry for entry in declared if isinstance(entry, str)
                    ]
            if not workspace_files:
                workspace_files = list(_SPARK_BASE_FALLBACK_WORKSPACE_FILES)
            sentinel_set = set(_SPARK_BASE_BOOTSTRAP_SENTINELS)
            without_sentinels = [
                entry for entry in workspace_files if entry not in sentinel_set
            ]
            return without_sentinels + list(_SPARK_BASE_BOOTSTRAP_SENTINELS)

        bootstrap_files: list[str] = _load_bootstrap_workspace_files()
        bootstrap_targets: list[tuple[Path, Path]] = []
        for entry in bootstrap_files:
            rel = entry.removeprefix(".github/")
            source_path = bootstrap_source_root / rel
            dest_path = workspace_github_root / rel
            bootstrap_targets.append((source_path, dest_path))

        def _bootstrap_target_is_satisfied(source_path: Path, dest_path: Path) -> bool:
            if not dest_path.is_file():
                return False
            github_rel = dest_path.relative_to(workspace_github_root).as_posix()
            owners = manifest.get_file_owners(github_rel)
            if any(owner != _BOOTSTRAP_PACKAGE_ID for owner in owners):
                return True
            return manifest._sha256(dest_path) == manifest._sha256(source_path)

        # Sentinel-based idempotency gate.
        if sentinel.is_file():
            user_mod = manifest.is_user_modified(sentinel_rel)
            if user_mod is False:
                if all(
                    _bootstrap_target_is_satisfied(source_path, dest_path)
                    for source_path, dest_path in bootstrap_targets
                ):
                    _all_bootstrap_rels = [
                        dest_path.relative_to(ctx.workspace_root).as_posix()
                        for _, dest_path in bootstrap_targets
                    ]
                    return await _finalize_bootstrap_result({
                        "success": True,
                        "status": "already_bootstrapped",
                        "files_written": [],
                        "files_copied": [],
                        "files_skipped": _all_bootstrap_rels,
                        "files_protected": [],
                        "sentinel_present": True,
                        "message": "Bootstrap assets already present and verified.",
                        "preserved": [],
                        "workspace": str(ctx.workspace_root),
                        "note": "Bootstrap assets already present and verified. Run /scf-list-available to inspect the package catalog.",
                    })
            if user_mod is True:
                if not force:
                    return {
                        "success": True,
                        "status": "user_modified",
                        "files_written": [],
                        "files_copied": [],
                        "files_skipped": [],
                        "files_protected": [sentinel_rel],
                        "sentinel_present": True,
                        "message": "Sentinel file has been modified by user. No files overwritten. Use force=True to override.",
                        "preserved": [sentinel_rel],
                        "workspace": str(ctx.workspace_root),
                        "install_base_requested": install_base,
                        "note": "Sentinel file has been modified by user. No files overwritten.",
                    }
                _log.warning(
                    "Bootstrap sentinel force-overwrite requested (force=True): %s",
                    sentinel_rel,
                )

        missing_sources = [
            str(source_path)
            for source_path, _ in bootstrap_targets
            if not source_path.is_file()
        ]
        if missing_sources:
            return {
                "success": False,
                "status": "error",
                "files_written": [],
                "files_copied": [],
                "files_skipped": [],
                "files_protected": [],
                "sentinel_present": sentinel.is_file(),
                "message": f"Bootstrap sources missing from engine repository: {missing_sources}",
                "preserved": [],
                "workspace": str(ctx.workspace_root),
                "install_base_requested": install_base,
                "note": f"Bootstrap sources missing from engine repository: {missing_sources}",
            }

        files_written: list[str] = []
        files_copied: list[str] = []
        files_skipped: list[str] = []
        files_protected: list[str] = []
        preserved: list[str] = []
        written_paths: list[Path] = []
        identical_paths: list[Path] = []
        files_conflict_non_spark: list[str] = []
        files_conflict_spark_outdated: list[str] = []
        spark_outdated_details: list[dict[str, Any]] = []
        files_updated_frontmatter_only: list[str] = []

        try:
            for source_path, dest_path in bootstrap_targets:
                rel_path = dest_path.relative_to(ctx.workspace_root).as_posix()
                github_rel = dest_path.relative_to(workspace_github_root).as_posix()
                if dest_path.is_file():
                    if manifest._sha256(dest_path) == manifest._sha256(source_path):
                        _log.info("Bootstrap file already matches source: %s", rel_path)
                        identical_paths.append(dest_path)
                        files_skipped.append(rel_path)
                        continue
                    if not force:
                        conflict_type = _classify_bootstrap_conflict(dest_path)
                        if conflict_type == "spark_outdated":
                            try:
                                fm = parse_markdown_frontmatter(
                                    dest_path.read_text(encoding="utf-8", errors="replace")
                                )
                                existing_version = str(fm.get("version", "unknown"))
                            except OSError:
                                existing_version = "unknown"
                            files_conflict_spark_outdated.append(rel_path)
                            spark_outdated_details.append(
                                {"file": rel_path, "existing_version": existing_version}
                            )
                            _log.warning(
                                "Bootstrap file preserved (spark_outdated v%s): %s",
                                existing_version,
                                rel_path,
                            )
                        else:
                            files_conflict_non_spark.append(rel_path)
                            _log.warning(
                                "Bootstrap file preserved (non_spark conflict): %s", rel_path
                            )
                        preserved.append(rel_path)
                        files_protected.append(rel_path)
                        continue
                    # force=True: apply frontmatter-only update for SPARK outdated files.
                    fm_conflict_type = _classify_bootstrap_conflict(dest_path)
                    if fm_conflict_type == "spark_outdated":
                        updated_content = _apply_frontmatter_only_update(source_path, dest_path)
                        if updated_content is not None:
                            if not dry_run:
                                dest_path.write_text(updated_content, encoding="utf-8")
                                written_paths.append(dest_path)
                                files_written.append(rel_path)
                            files_updated_frontmatter_only.append(rel_path)
                            files_copied.append(rel_path)
                            _log.info(
                                "[SPARK-ENGINE][INFO] %s (frontmatter-only): %s",
                                "dry_run" if dry_run else "Updated",
                                github_rel,
                            )
                        else:
                            files_conflict_non_spark.append(rel_path)
                            preserved.append(rel_path)
                            files_protected.append(rel_path)
                            _log.warning(
                                "[SPARK-ENGINE][WARNING] Bootstrap file preserved "
                                "(frontmatter-only update failed, fallback): %s",
                                rel_path,
                            )
                        continue  # Do not fall through to the full write block.
                    # Non-SPARK file with force=True: apply full overwrite (unchanged behavior).
                    _log.warning(
                        "Bootstrap file force-overwritten (force=True): %s", rel_path,
                    )

                dest_path.parent.mkdir(parents=True, exist_ok=True)
                cross_owner = any(
                    owner != _BOOTSTRAP_PACKAGE_ID
                    for owner in manifest.get_file_owners(github_rel)
                )
                if cross_owner:
                    _log.warning(
                        "Bootstrap file preserved (owned by another package): %s",
                        rel_path,
                    )
                    preserved.append(rel_path)
                    continue
                if not dry_run:
                    _gateway_write_bytes(
                        ctx.workspace_root,
                        github_rel,
                        source_path.read_bytes(),
                        manifest,
                        _BOOTSTRAP_PACKAGE_ID,
                        ENGINE_VERSION,
                    )
                    written_paths.append(dest_path)
                    files_written.append(rel_path)
                files_copied.append(rel_path)
                _log.info(
                    "[SPARK-ENGINE][INFO] %s: %s",
                    "dry_run" if dry_run else "Bootstrapped",
                    github_rel,
                )
        except OSError as exc:
            rollback_errors: list[str] = []
            for written_path in reversed(written_paths):
                try:
                    if written_path.is_file():
                        written_path.unlink()
                except OSError as rollback_exc:
                    rollback_errors.append(f"{written_path}: {rollback_exc}")

            rollback_note = ""
            if rollback_errors:
                rollback_note = f" Rollback issues: {rollback_errors}"
            return {
                "success": False,
                "status": "error",
                "files_written": [],
                "files_copied": files_copied,
                "files_skipped": files_skipped,
                "files_protected": files_protected,
                "files_conflict_non_spark": files_conflict_non_spark,
                "files_conflict_spark_outdated": files_conflict_spark_outdated,
                "spark_outdated_details": spark_outdated_details,
                "files_updated_frontmatter_only": files_updated_frontmatter_only,
                "sentinel_present": sentinel.is_file(),
                "message": f"Bootstrap failed while copying files: {exc}.{rollback_note}",
                "preserved": preserved,
                "workspace": str(ctx.workspace_root),
                "install_base_requested": install_base,
                "note": f"Bootstrap failed while copying files: {exc}.{rollback_note}",
            }

        if not dry_run and (written_paths or identical_paths):
            bootstrap_manifest_targets = [
                (dest_path.relative_to(workspace_github_root).as_posix(), dest_path)
                for dest_path in written_paths + identical_paths
                if not any(
                    owner != _BOOTSTRAP_PACKAGE_ID
                    for owner in manifest.get_file_owners(
                        dest_path.relative_to(workspace_github_root).as_posix()
                    )
                )
            ]
            if bootstrap_manifest_targets:
                manifest.upsert_many(
                    _BOOTSTRAP_PACKAGE_ID,
                    ENGINE_VERSION,
                    bootstrap_manifest_targets,
                )
                _save_snapshots(
                    _BOOTSTRAP_PACKAGE_ID,
                    bootstrap_manifest_targets,
                )

        return await _finalize_bootstrap_result({
            "success": True,
            "status": "bootstrapped",
            "files_written": files_written,
            "files_copied": files_copied,
            "files_skipped": files_skipped,
            "files_protected": files_protected,
            "files_conflict_non_spark": files_conflict_non_spark,
            "files_conflict_spark_outdated": files_conflict_spark_outdated,
            "spark_outdated_details": spark_outdated_details,
            "files_updated_frontmatter_only": files_updated_frontmatter_only,
            "sentinel_present": sentinel.is_file(),
            "message": (
                "Bootstrap simulated (dry_run=True). No files were written."
                if dry_run
                else "Bootstrap completed. Run /scf-list-available to inspect the package catalog."
            ),
            "preserved": preserved,
            "workspace": str(ctx.workspace_root),
            "note": "Bootstrap completed. Run /scf-list-available to inspect the package catalog.",
        })

    # D.3: inietta il tool come callback nell'engine per ensure_minimal_bootstrap().
    engine._bootstrap_workspace_tool = scf_bootstrap_workspace

    # ------------------------------------------------------------------
    # Tool: scf_migrate_workspace
    # ------------------------------------------------------------------

    @_register_tool("scf_migrate_workspace")
    async def scf_migrate_workspace(
        dry_run: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        """Migrate a v2.x workspace `.github/` layout to the v3.0 schema.

        Two-step flow: analyse first, then optionally execute.
        With dry_run=True (default) only the migration plan is returned.
        With dry_run=False and force=True, the plan is applied with a
        timestamped backup and rollback on error.
        """
        workspace_root = ctx.workspace_root
        engine_cache = ctx.engine_root / "cache"
        planner = MigrationPlanner(workspace_root, engine_cache)
        plan = planner.analyze()

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "migration_plan": plan.to_dict(),
                "requires_confirmation": not plan.is_empty(),
                "workspace": str(workspace_root),
            }

        if not force and not plan.is_empty():
            return {
                "success": False,
                "dry_run": False,
                "error": "force=True required to apply a non-empty migration plan",
                "migration_plan": plan.to_dict(),
                "workspace": str(workspace_root),
            }

        if plan.is_empty():
            return {
                "success": True,
                "dry_run": False,
                "status": "no_op",
                "migration_plan": plan.to_dict(),
                "workspace": str(workspace_root),
            }

        report = planner.apply(plan)
        return {
            "success": not report["rolled_back"],
            "dry_run": False,
            "status": "rolled_back" if report["rolled_back"] else "migrated",
            "migration_plan": plan.to_dict(),
            "report": report,
            "workspace": str(workspace_root),
        }
