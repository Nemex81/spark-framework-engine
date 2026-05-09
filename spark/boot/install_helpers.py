"""Install and update flow helpers for SparkFrameworkEngine.

Extracted from spark.boot.engine during Phase 1 modular refactoring.
All functions are stateless with respect to SparkFrameworkEngine
instance state — dependencies are passed explicitly as parameters.

Functions that previously captured variables from ``register_tools()``
closure scope now receive those dependencies as trailing keyword-style
positional parameters.  The thin shim wrappers inside ``register_tools()``
inject the closure captures transparently so all existing call sites
remain unchanged.
"""
from __future__ import annotations

import logging
import urllib.error
from pathlib import Path
from typing import Any

from spark.core.constants import ENGINE_VERSION, _BOOTSTRAP_PACKAGE_ID
from spark.core.utils import (
    _infer_scf_file_role,
    _is_engine_version_compatible,
    _normalize_dependency_ids,
    _normalize_manifest_relative_path,
    _normalize_string_list,
    _sha256_text,
)
from spark.inventory import FrameworkInventory
from spark.manifest import ManifestManager, SnapshotManager
from spark.merge import MergeEngine, MergeSessionManager, run_post_merge_validators
from spark.merge.sections import _classify_copilot_instructions_format
from spark.merge.validators import (
    _extract_frontmatter_block,
    _normalize_merge_text,
    _resolve_disjoint_line_additions,
)
from spark.packages import _get_registry_min_engine_version, _resolve_package_version
from spark.registry import RegistryClient
from spark.workspace import (
    _default_update_policy,
    _read_update_policy_payload,
    _update_policy_path,
    _validate_update_mode,
)

_log: logging.Logger = logging.getLogger("spark-framework-engine")

# ============================================================================ #
# Group B — session / merge helpers                                             #
# ============================================================================ #


def _save_snapshots(
    package_id: str,
    files: list[tuple[str, Path]],
    snapshots: SnapshotManager,
) -> dict[str, list[str]]:
    """Persist BASE snapshots for written files without blocking the main operation.

    Args:
        package_id: ID del pacchetto.
        files: lista di tuple (rel_path, abs_path).
        snapshots: SnapshotManager attivo.

    Returns:
        Dict con ``written`` e ``skipped``.
    """
    written: list[str] = []
    skipped: list[str] = []
    for file_rel, file_abs in files:
        public_path = f".github/{file_rel}"
        if snapshots.save_snapshot(package_id, file_rel, file_abs):
            written.append(public_path)
        else:
            skipped.append(public_path)
    return {"written": written, "skipped": skipped}


def _read_text_if_possible(path: Path) -> str | None:
    """Read a UTF-8 workspace file, returning None for undecodable content.

    Args:
        path: percorso del file.

    Returns:
        Contenuto testuale o None se non leggibile.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _log.warning("Cannot read text file %s: %s", path, exc)
        return None


def _supports_stateful_merge(conflict_mode: str) -> bool:
    """Return True for conflict modes that use a persistent merge session.

    Args:
        conflict_mode: modalità conflitti.
    """
    return conflict_mode in {"manual", "auto", "assisted"}


def _render_marker_text(file_entry: dict[str, Any], merge_engine: MergeEngine) -> str:
    """Render or reuse the persisted marker text for one conflicting file.

    Args:
        file_entry: entry di sessione per il file in conflitto.
        merge_engine: istanza MergeEngine.
    """
    existing = file_entry.get("marker_text")
    if isinstance(existing, str) and existing:
        return existing
    merge_result = merge_engine.diff3_merge(
        str(file_entry.get("base_text", "") or ""),
        str(file_entry.get("ours_text", "") or ""),
        str(file_entry.get("theirs_text", "") or ""),
    )
    return merge_engine.render_with_markers(merge_result)


def _build_session_entry(
    file_path: str,
    rel: str,
    base_text: str,
    ours_text: str,
    theirs_text: str,
    marker_text: str,
) -> dict[str, Any]:
    """Build the persisted session payload for one conflicting file.

    Args:
        file_path: path completo del file.
        rel: path relativo nel manifest.
        base_text: testo base (versione comune).
        ours_text: testo workspace.
        theirs_text: testo remoto.
        marker_text: testo con marker di conflitto.
    """
    return {
        "file": file_path,
        "workspace_path": file_path,
        "manifest_rel": rel,
        "conflict_id": rel,
        "base_text": base_text,
        "ours_text": ours_text,
        "theirs_text": theirs_text,
        "proposed_text": None,
        "resolution_status": "pending",
        "validator_results": None,
        "marker_text": marker_text,
        "original_sha_at_session_open": _sha256_text(ours_text),
    }


def _replace_session_entry(
    session: dict[str, Any],
    index: int,
    file_entry: dict[str, Any],
) -> None:
    """Replace one normalized file entry inside an in-memory session payload.

    Args:
        session: payload di sessione merge.
        index: indice dell'entry da sostituire.
        file_entry: nuovo valore normalizzato.
    """
    files = list(session.get("files", []))
    files[index] = MergeSessionManager._normalize_session_file_entry(file_entry)
    session["files"] = files


def _find_session_entry(
    session: dict[str, Any],
    conflict_id: str,
) -> tuple[int, dict[str, Any]] | None:
    """Find one conflict entry in a session by its stable conflict id.

    Args:
        session: payload di sessione merge.
        conflict_id: ID del conflitto cercato.

    Returns:
        Tuple (index, entry) oppure None.
    """
    for index, file_entry in enumerate(list(session.get("files", []))):
        if str(file_entry.get("conflict_id", "")).strip() == conflict_id:
            return (index, dict(file_entry))
    return None


def _count_remaining_conflicts(session: dict[str, Any]) -> int:
    """Count session entries that still need approval or manual resolution.

    Args:
        session: payload di sessione merge.
    """
    return sum(
        1
        for file_entry in list(session.get("files", []))
        if str(file_entry.get("resolution_status", "pending")).strip() != "approved"
    )


def _resolve_conflict_automatically(file_entry: dict[str, Any]) -> str | None:
    """Return a safe automatic merge proposal only for clearly unambiguous cases.

    Args:
        file_entry: entry di sessione per il file in conflitto.

    Returns:
        Testo proposto oppure None se la risoluzione automatica non è sicura.
    """
    base_text = _normalize_merge_text(str(file_entry.get("base_text", "") or ""))
    ours_text = _normalize_merge_text(str(file_entry.get("ours_text", "") or ""))
    theirs_text = _normalize_merge_text(str(file_entry.get("theirs_text", "") or ""))

    frontmatter_blocks = {
        frontmatter
        for frontmatter in (
            _extract_frontmatter_block(base_text),
            _extract_frontmatter_block(ours_text),
            _extract_frontmatter_block(theirs_text),
        )
        if frontmatter is not None
    }
    if len(frontmatter_blocks) > 1:
        return None

    if ours_text == theirs_text:
        return ours_text
    if base_text == ours_text:
        return theirs_text
    if base_text == theirs_text:
        return ours_text
    if ours_text and ours_text in theirs_text:
        return theirs_text
    if theirs_text and theirs_text in ours_text:
        return ours_text
    return _resolve_disjoint_line_additions(base_text, ours_text, theirs_text)


def _propose_conflict_resolution(
    session: dict[str, Any],
    conflict_id: str,
    sessions: MergeSessionManager,
    persist: bool = True,
) -> dict[str, Any]:
    """Populate proposed_text and validator results for one conflict when safe.

    Args:
        session: payload di sessione merge (in-memory).
        conflict_id: ID del conflitto da risolvere.
        sessions: MergeSessionManager per la persistenza.
        persist: se True salva la sessione dopo la modifica.

    Returns:
        Dict MCP con ``success``, ``conflict_id``, ``proposed_text``.
    """
    found = _find_session_entry(session, conflict_id)
    if found is None:
        return {
            "success": False,
            "error": "conflict_not_found",
            "conflict_id": conflict_id,
        }

    index, file_entry = found
    proposed_text = _resolve_conflict_automatically(file_entry)
    if proposed_text is None:
        file_entry["proposed_text"] = None
        file_entry["validator_results"] = None
        file_entry["resolution_status"] = "manual"
        _replace_session_entry(session, index, file_entry)
        if persist:
            sessions.save_session(session)
        return {
            "success": False,
            "conflict_id": conflict_id,
            "fallback": "manual",
            "reason": "best_effort_auto_resolution_not_safe",
            "validator_results": None,
        }

    validator_results = run_post_merge_validators(
        proposed_text,
        str(file_entry.get("base_text", "") or ""),
        str(file_entry.get("ours_text", "") or ""),
        str(file_entry.get("file", file_entry.get("workspace_path", "")) or ""),
    )
    file_entry["validator_results"] = validator_results
    if not validator_results.get("passed", False):
        file_entry["proposed_text"] = None
        file_entry["resolution_status"] = "manual"
        _replace_session_entry(session, index, file_entry)
        if persist:
            sessions.save_session(session)
        return {
            "success": False,
            "conflict_id": conflict_id,
            "fallback": "manual",
            "reason": "post_merge_validation_failed",
            "validator_results": validator_results,
        }

    file_entry["proposed_text"] = proposed_text
    file_entry["resolution_status"] = "auto_resolved"
    _replace_session_entry(session, index, file_entry)
    if persist:
        sessions.save_session(session)
    return {
        "success": True,
        "conflict_id": conflict_id,
        "proposed_text": proposed_text,
        "validator_results": validator_results,
        "resolution_status": "auto_resolved",
    }


# ============================================================================ #
# Group A — install / diff helpers                                              #
# ============================================================================ #


def _build_install_result(
    success: bool, error: str | None = None, **extras: Any
) -> dict[str, Any]:
    """Build a stable install/update payload with conflict metadata.

    Args:
        success: esito dell'operazione.
        error: messaggio di errore opzionale.
        **extras: campi aggiuntivi da includere nel payload.

    Returns:
        Dict MCP con tutti i campi standard.
    """
    result: dict[str, Any] = {
        "success": success,
        "installed": [],
        "extended_files": [],
        "delegated_files": [],
        "preserved": [],
        "removed_obsolete_files": [],
        "preserved_obsolete_files": [],
        "conflicts_detected": [],
        "blocked_files": [],
        "replaced_files": [],
        "merged_files": [],
        "merge_clean": [],
        "merge_conflict": [],
        "session_id": None,
        "session_status": None,
        "session_expires_at": None,
        "snapshot_written": [],
        "snapshot_skipped": [],
        "requires_user_resolution": False,
        "resolution_applied": "none",
    }
    if error is not None:
        result["error"] = error
    result.update(extras)
    return result


def _build_remote_file_records(
    package_id: str,
    pkg_version: str,
    pkg: dict[str, Any],
    pkg_manifest: dict[str, Any],
    files: list[str],
    file_policies: dict[str, str],
    registry: RegistryClient,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Fetch remote package files and attach SCF metadata for diffing and writes.

    Args:
        package_id: ID del pacchetto.
        pkg_version: versione risolta.
        pkg: entry registry.
        pkg_manifest: manifest del pacchetto.
        files: lista di path relativi.
        file_policies: policy per file.
        registry: RegistryClient per il fetch dei contenuti.

    Returns:
        Tuple (remote_files, fetch_errors).
    """
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

    remote_files: list[dict[str, Any]] = []
    fetch_errors: list[str] = []
    base_raw_url = pkg["repo_url"].replace(
        "https://github.com/", "https://raw.githubusercontent.com/"
    ) + "/main/"

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
                _log.info(
                    "Legacy file without SCF metadata treated with strategy replace: %s",
                    file_path,
                )

        try:
            merge_priority = int(metadata.get("scf_merge_priority", 0) or 0)
        except (TypeError, ValueError):
            merge_priority = 0

        try:
            content = registry.fetch_raw_file(base_raw_url + file_path)
        except (urllib.error.URLError, OSError) as exc:
            fetch_errors.append(f"{file_path}: {exc}")
            continue

        remote_files.append(
            {
                "path": file_path,
                "content": content,
                "sha256": _sha256_text(content),
                "scf_owner": str(metadata.get("scf_owner", package_id)).strip() or package_id,
                "scf_version": str(metadata.get("scf_version", pkg_version)).strip() or pkg_version,
                "scf_file_role": str(
                    metadata.get(
                        "scf_file_role",
                        _infer_scf_file_role(file_path.removeprefix(".github/")),
                    )
                ).strip()
                or _infer_scf_file_role(file_path.removeprefix(".github/")),
                "scf_merge_strategy": merge_strategy,
                "scf_merge_priority": merge_priority,
                "scf_protected": bool(metadata.get("scf_protected", False)),
            }
        )

    return remote_files, fetch_errors


def _build_diff_summary(diff_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a compact diff summary excluding unchanged files.

    Args:
        diff_records: lista di record diff da ``_scf_diff_workspace``.

    Returns:
        Dict con ``total``, ``counts`` e ``files``.
    """
    counts: dict[str, int] = {}
    files_summary: list[dict[str, Any]] = []
    for item in diff_records:
        status = str(item.get("status", "")).strip()
        if status == "unchanged":
            continue
        counts[status] = counts.get(status, 0) + 1
        files_summary.append(
            {
                "file": item.get("file", ""),
                "status": status,
                "scf_file_role": item.get("scf_file_role", "config"),
                "scf_merge_strategy": item.get("scf_merge_strategy", "replace"),
                "scf_protected": bool(item.get("scf_protected", False)),
            }
        )
    return {
        "total": len(files_summary),
        "counts": counts,
        "files": files_summary,
    }


def _resolve_effective_update_mode(
    package_id: str,
    requested_update_mode: str,
    diff_records: list[dict[str, Any]],
    policy_payload: dict[str, Any],
    policy_source: str,
) -> dict[str, Any]:
    """Resolve the package-level update mode from request and workspace policy.

    Args:
        package_id: ID del pacchetto.
        requested_update_mode: modalità richiesta esplicitamente.
        diff_records: record diff per il pacchetto.
        policy_payload: payload policy workspace.
        policy_source: sorgente della policy (``file`` / ``default``).

    Returns:
        Dict con ``mode``, ``source``, ``auto_update``, ``policy_source``.
    """
    policy = policy_payload.get("update_policy", _default_update_policy())
    auto_update = bool(policy.get("auto_update", False))
    if requested_update_mode:
        return {
            "mode": requested_update_mode,
            "source": "explicit",
            "auto_update": auto_update,
            "policy_source": policy_source,
        }

    mode_per_package = policy.get("mode_per_package", {})
    if isinstance(mode_per_package, dict):
        package_mode = _validate_update_mode(
            str(mode_per_package.get(package_id, "")),
            allow_selective=True,
        )
        if package_mode is not None:
            return {
                "mode": package_mode,
                "source": "policy_package",
                "auto_update": auto_update,
                "policy_source": policy_source,
            }

    default_mode = str(policy.get("default_mode", "ask")).strip() or "ask"
    mode_per_file_role = policy.get("mode_per_file_role", {})
    role_modes: set[str] = set()
    matched_role_override = False
    if isinstance(mode_per_file_role, dict):
        for item in diff_records:
            if str(item.get("status", "")).strip() == "unchanged":
                continue
            role = str(item.get("scf_file_role", "config")).strip() or "config"
            candidate_mode = _validate_update_mode(
                str(mode_per_file_role.get(role, default_mode)),
                allow_selective=True,
            )
            if role in mode_per_file_role:
                matched_role_override = True
            if candidate_mode is not None:
                role_modes.add(candidate_mode)

    if len(role_modes) == 1:
        return {
            "mode": next(iter(role_modes)),
            "source": "policy_file_role" if matched_role_override else "policy_default",
            "auto_update": auto_update,
            "policy_source": policy_source,
        }
    if len(role_modes) > 1:
        return {
            "mode": "selective",
            "source": "policy_file_role",
            "auto_update": auto_update,
            "policy_source": policy_source,
        }

    return {
        "mode": default_mode,
        "source": "policy_default",
        "auto_update": auto_update,
        "policy_source": policy_source,
    }


def _build_update_flow_payload(
    package_id: str,
    pkg_version: str,
    conflict_mode: str,
    requested_update_mode: str,
    effective_update_mode: dict[str, Any],
    diff_summary: dict[str, Any],
    inventory: FrameworkInventory,
) -> dict[str, Any]:
    """Return the common OWN-D flow metadata for install/update responses.

    Args:
        package_id: ID del pacchetto.
        pkg_version: versione del pacchetto.
        conflict_mode: modalità conflitti.
        requested_update_mode: modalità richiesta esplicitamente.
        effective_update_mode: dict risolto da ``_resolve_effective_update_mode``.
        diff_summary: riepilogo diff.
        inventory: FrameworkInventory per lo stato orchestrator.

    Returns:
        Dict con i campi OWN-D standard.
    """
    orchestrator_state = inventory.get_orchestrator_state()
    auto_update = bool(effective_update_mode.get("auto_update", False))
    authorized = bool(orchestrator_state.get("github_write_authorized", False))
    policy_source = str(effective_update_mode.get("policy_source", "default_missing")).strip()
    policy_enforced = policy_source == "file" or bool(requested_update_mode)
    return {
        "update_mode_requested": requested_update_mode or None,
        "resolved_update_mode": effective_update_mode.get("mode", "ask"),
        "update_mode_source": effective_update_mode.get("source", "policy_default"),
        "policy_source": policy_source,
        "policy_enforced": policy_enforced,
        "auto_update": auto_update,
        "authorization_required": policy_enforced and not auto_update,
        "github_write_authorized": authorized,
        "diff_summary": diff_summary,
        "supported_update_modes": [
            "integrative",
            "replace",
            "conservative",
            "selective",
        ],
    }


def _detect_workspace_migration_state(
    github_root: Path,
    manifest: ManifestManager,
) -> dict[str, Any]:
    """Return the current migration state for a legacy SCF workspace.

    Args:
        github_root: percorso ``.github/`` del workspace.
        manifest: ManifestManager attivo.

    Returns:
        Dict con ``legacy_workspace``, ``policy_source``, ``missing_steps``.
    """
    policy_payload, policy_source = _read_update_policy_payload(github_root)
    manifest_entries = manifest.load()
    sentinel_path = github_root / "agents" / "spark-assistant.agent.md"
    copilot_path = github_root / "copilot-instructions.md"
    copilot_exists = copilot_path.is_file()
    copilot_content = _read_text_if_possible(copilot_path) if copilot_exists else None
    copilot_format = (
        "unreadable"
        if copilot_exists and copilot_content is None
        else _classify_copilot_instructions_format(copilot_content or "")
        if copilot_exists
        else "missing"
    )
    missing_steps: list[str] = []
    legacy_workspace = bool(manifest_entries or sentinel_path.is_file() or copilot_exists)
    if legacy_workspace and policy_source != "file":
        missing_steps.append("configure_update_policy")
    if copilot_format in {"plain", "scf_markers_partial"}:
        missing_steps.append("migrate_copilot_instructions")
    return {
        "legacy_workspace": legacy_workspace,
        "policy_source": policy_source,
        "policy_path": str(_update_policy_path(github_root)),
        "copilot_instructions": {
            "path": str(copilot_path),
            "exists": copilot_exists,
            "current_format": copilot_format,
            "proposed_format": (
                "scf_markers_complete"
                if copilot_format == "scf_markers_partial"
                else "scf_markers"
                if copilot_format == "plain"
                else None
            ),
        },
        "missing_steps": missing_steps,
    }


def _normalize_file_policies(
    raw_policies: Any,
    raw_files_metadata: Any = None,
) -> dict[str, str]:
    """Normalize install policies from legacy file_policies and schema 2.1 files_metadata.

    Args:
        raw_policies: dizionario ``file_policies`` dal manifest.
        raw_files_metadata: lista ``files_metadata`` dal manifest (schema 3.x).

    Returns:
        Dict normalizzato ``{".github/path": "extend|delegate|error"}``.
    """
    normalized: dict[str, str] = {}
    if isinstance(raw_files_metadata, list):
        for item in raw_files_metadata:
            if not isinstance(item, dict):
                continue
            raw_path = item.get("path")
            raw_strategy = item.get("scf_merge_strategy")
            if not isinstance(raw_path, str) or not isinstance(raw_strategy, str):
                continue
            path = raw_path.replace("\\", "/").strip()
            strategy = raw_strategy.strip().lower()
            if not path.startswith(".github/"):
                continue
            if strategy == "merge_sections":
                normalized[path] = "extend"
            elif strategy == "user_protected":
                normalized[path] = "delegate"

    if not isinstance(raw_policies, dict):
        return normalized

    # Deprecation hint: manifest puramente schema 2.x (file_policies senza
    # files_metadata) — sarà rimosso in v4.0.
    if not raw_files_metadata and raw_policies:
        _log.warning(
            "[SPARK-ENGINE][WARNING] package-manifest schema 2.x rilevato "
            "(files/file_policies senza files_metadata): "
            "aggiornare a schema 3.x con workspace_files + files_metadata."
        )

    for raw_path, raw_policy in raw_policies.items():
        if not isinstance(raw_path, str) or not isinstance(raw_policy, str):
            continue
        path = raw_path.replace("\\", "/").strip()
        policy = raw_policy.strip().lower()
        if not path.startswith(".github/") or policy not in {"error", "extend", "delegate"}:
            continue
        normalized[path] = policy
    return normalized


def _validate_extend_policy_target(file_path: str) -> None:
    """Reject extend on file types that cannot safely host SCF section markers.

    Args:
        file_path: path del file da validare.

    Raises:
        ValueError: se il path non supporta la policy ``extend``.
    """
    if file_path.endswith(".agent.md"):
        raise ValueError(
            f"Policy 'extend' is not supported for files ending with '.agent.md': {file_path}"
        )


def _get_package_install_context(
    package_id: str,
    registry: RegistryClient,
    manifest: ManifestManager,
) -> dict[str, Any]:
    """Return package installation context or a structured failure result.

    Args:
        package_id: ID del pacchetto.
        registry: RegistryClient per il fetch dal registry.
        manifest: ManifestManager del workspace.

    Returns:
        Dict con i dati di contesto o un payload di errore
        compatibile con ``_build_install_result``.
    """
    try:
        packages = registry.list_packages()
    except Exception as exc:  # noqa: BLE001
        return _build_install_result(False, error=f"Registry unavailable: {exc}")

    pkg = next((p for p in packages if p.get("id") == package_id), None)
    if pkg is None:
        return _build_install_result(
            False,
            error=f"Package '{package_id}' not found in registry.",
            available=[p.get("id") for p in packages],
        )
    if pkg.get("status") == "deprecated":
        return _build_install_result(
            False,
            error=(
                f"Package '{package_id}' is deprecated. "
                "Check the registry for its successor."
            ),
        )

    try:
        pkg_manifest = registry.fetch_package_manifest(pkg["repo_url"])
    except Exception as exc:  # noqa: BLE001
        return _build_install_result(
            False,
            error=f"Cannot fetch package manifest: {exc}",
        )

    files: list[str] = pkg_manifest.get("files", [])
    if not files:
        return _build_install_result(
            False,
            error=f"Package '{package_id}' has no files in its manifest.",
        )

    pkg_version = _resolve_package_version(
        pkg_manifest.get("version", ""),
        pkg.get("latest_version", "unknown"),
    )
    min_engine_version = str(
        pkg_manifest.get("min_engine_version", _get_registry_min_engine_version(pkg))
    ).strip()
    # Usa _normalize_dependency_ids (non _normalize_string_list) perché i manifest
    # schema 3.1 dichiarano le dipendenze come oggetti {"id": ..., "min_version": ...}
    # invece che come semplici stringhe. Il normalizzatore estrae il campo "id".
    dependencies = _normalize_dependency_ids(pkg_manifest.get("dependencies", []))
    declared_conflicts = _normalize_string_list(pkg_manifest.get("conflicts", []))
    file_ownership_policy = (
        str(pkg_manifest.get("file_ownership_policy", "error")).strip() or "error"
    )
    file_policies = _normalize_file_policies(
        pkg_manifest.get("file_policies", {}),
        pkg_manifest.get("files_metadata", []),
    )
    installed_versions = manifest.get_installed_versions()
    missing_dependencies = [
        dependency for dependency in dependencies if dependency not in installed_versions
    ]
    present_conflicts = [
        conflict for conflict in declared_conflicts if conflict in installed_versions
    ]

    return {
        "success": True,
        "pkg": pkg,
        "pkg_manifest": pkg_manifest,
        "files": files,
        "pkg_version": pkg_version,
        "min_engine_version": min_engine_version,
        "dependencies": dependencies,
        "declared_conflicts": declared_conflicts,
        "file_ownership_policy": file_ownership_policy,
        "file_policies": file_policies,
        "installed_versions": installed_versions,
        "missing_dependencies": missing_dependencies,
        "present_conflicts": present_conflicts,
        "engine_compatible": _is_engine_version_compatible(
            ENGINE_VERSION,
            min_engine_version,
        ),
    }


def _classify_install_files(
    package_id: str,
    files: list[str],
    manifest: ManifestManager,
    workspace_root: Path,
    snapshots: SnapshotManager,
    file_policies: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Classify package targets before any install or update writes.

    ``file_policies`` uses the simple manifest shape
    ``{".github/path.md": "extend|delegate|error"}``.

    Args:
        package_id: ID del pacchetto.
        files: lista path relativi dichiarati nel manifest.
        manifest: ManifestManager attivo.
        workspace_root: root del workspace utente.
        snapshots: SnapshotManager per i file merge.
        file_policies: policy per file (opzionale).

    Returns:
        Dict con record, write_plan, extend_plan, conflict_plan, ecc.
    """
    records: list[dict[str, Any]] = []
    write_plan: list[dict[str, Any]] = []
    extend_plan: list[dict[str, Any]] = []
    delegate_plan: list[dict[str, Any]] = []
    preserve_plan: list[dict[str, Any]] = []
    conflict_plan: list[dict[str, Any]] = []
    merge_plan: list[dict[str, Any]] = []
    ownership_issues: list[dict[str, Any]] = []
    normalized_file_policies = file_policies or {}

    for file_path in files:
        rel = file_path.removeprefix(".github/")
        dest = workspace_root / file_path
        owners = [owner for owner in manifest.get_file_owners(rel) if owner != package_id]
        bootstrap_adoption = package_id == "spark-base" and owners == [_BOOTSTRAP_PACKAGE_ID]
        per_file_policy = normalized_file_policies.get(file_path, "error")
        if owners and not bootstrap_adoption:
            if per_file_policy == "extend":
                _validate_extend_policy_target(file_path)
                item = {
                    "file": file_path,
                    "classification": "extend_section",
                    "owners": owners,
                    "policy": "extend",
                    "file_exists": dest.exists(),
                }
                records.append(item)
                extend_plan.append(item)
                continue
            if per_file_policy == "delegate":
                item = {
                    "file": file_path,
                    "classification": "delegate_skip",
                    "owners": owners,
                    "policy": "delegate",
                }
                records.append(item)
                delegate_plan.append(item)
                continue
            item = {
                "file": file_path,
                "classification": "conflict_cross_owner",
                "owners": owners,
            }
            records.append(item)
            conflict_plan.append(item)
            ownership_issues.append({"file": file_path, "owners": owners})
            continue

        tracked_state = manifest.is_user_modified(rel)
        if not dest.exists():
            item = {"file": file_path, "classification": "create_new"}
            records.append(item)
            write_plan.append(item)
            continue
        if tracked_state is True:
            if snapshots.snapshot_exists(package_id, rel):
                item = {
                    "file": file_path,
                    "classification": "merge_candidate",
                }
                records.append(item)
                merge_plan.append(item)
                continue
            item = {
                "file": file_path,
                "classification": "preserve_tracked_modified",
                "base_unavailable": True,
            }
            records.append(item)
            preserve_plan.append(item)
            continue
        if tracked_state is False:
            item = {
                "file": file_path,
                "classification": "update_tracked_clean",
            }
            if bootstrap_adoption:
                item["adopt_bootstrap_owner"] = True
            records.append(item)
            write_plan.append(item)
            continue

        item = {
            "file": file_path,
            "classification": "conflict_untracked_existing",
        }
        records.append(item)
        conflict_plan.append(item)

    return {
        "records": records,
        "write_plan": write_plan,
        "extend_plan": extend_plan,
        "delegate_plan": delegate_plan,
        "preserve_plan": preserve_plan,
        "conflict_plan": conflict_plan,
        "merge_plan": merge_plan,
        "ownership_issues": ownership_issues,
        "conflict_mode_required": len(conflict_plan) > 0,
        "can_install_with_replace": len(ownership_issues) == 0,
    }


def _summarize_available_updates(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract only updatable packages from the update planner report.

    Args:
        report: output di ``_plan_package_updates``.

    Returns:
        Lista di dict ``{package, installed, latest}`` per i soli pacchetti
        con aggiornamento disponibile.
    """
    return [
        {
            "package": item.get("package", ""),
            "installed": item.get("installed", ""),
            "latest": item.get("latest", ""),
        }
        for item in report.get("updates", [])
        if item.get("status") == "update_available"
    ]
