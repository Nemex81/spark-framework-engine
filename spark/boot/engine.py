"""SparkFrameworkEngine — SPARK Framework Engine.

Extracted to ``spark.boot.engine`` during Phase 0 modular refactoring.
Re-exported from ``spark.boot``.

Surgical changes vs. original hub (all logically equivalent at runtime):
1. ``_v3_runtime_state``: ``EngineInventory()`` → ``EngineInventory(engine_root=self._ctx.engine_root)``
2. ``_v3_repopulate_registry``: same
3. ``register_resources``: same (``engine_inventory = EngineInventory()``)
4. ``_ensure_registry`` closure: same
5+6. ``scf_bootstrap_workspace`` (×2): ``Path(__file__).resolve().parent / ".github"``
     → ``self._ctx.engine_root / ".github"`` (identical value since ctx.engine_root
     is set by WorkspaceLocator which receives Path(__file__).resolve().parent from hub)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar

from spark.core.constants import (
    ENGINE_VERSION,
    _ALLOWED_UPDATE_MODES,
    _BACKUPS_SUBDIR,
    _BOOTSTRAP_PACKAGE_ID,
    _CHANGELOGS_SUBDIR,
    _LEGACY_MANIFEST_SCHEMA_VERSIONS,
    _MANIFEST_FILENAME,
    _MANIFEST_SCHEMA_VERSION,
    _MERGE_SESSIONS_SUBDIR,
    _REGISTRY_CACHE_FILENAME,
    _REGISTRY_TIMEOUT_SECONDS,
    _REGISTRY_URL,
    _RESOURCE_TYPES,
    _SNAPSHOTS_SUBDIR,
    _SUPPORTED_MANIFEST_SCHEMA_VERSIONS,
    _USER_PREFS_FILENAME,
)
from spark.core.models import (
    MERGE_STATUS_CLEAN,
    MERGE_STATUS_CONFLICT,
    MERGE_STATUS_IDENTICAL,
    FrameworkFile,
    MergeConflict,
    MergeResult,
    WorkspaceContext,
)
from spark.core.utils import (
    _V3_LIFECYCLE_MIN_ENGINE_VERSION,
    _extract_version_from_changelog,
    _format_utc_timestamp,
    _infer_scf_file_role,
    _is_engine_version_compatible,
    _is_v3_package,
    _normalize_manifest_relative_path,
    _normalize_string_list,
    _parse_semver_triplet,
    _parse_utc_timestamp,
    _resolve_dependency_update_order,
    _sha256_text,
    _utc_now,
    parse_markdown_frontmatter,
)
from spark.merge import (
    MergeEngine,
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
from spark.manifest import (
    ManifestManager,
    SnapshotManager,
    WorkspaceWriteGateway,
    _normalize_remote_file_record,
    _scf_backup_workspace,
    _scf_diff_workspace,
)
from spark.registry import (
    McpResourceRegistry,
    PackageResourceStore,
    RegistryClient,
    _V3_STORE_INSTALLATION_MODE,
    _build_package_raw_url_base,
    _resource_filename_candidates,
    _v3_store_sentinel_file,
)
from spark.workspace import (
    MigrationPlan,
    MigrationPlanner,
    WorkspaceLocator,
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
from spark.packages import (
    _build_registry_package_summary,
    _get_registry_min_engine_version,
    _install_package_v3_into_store,
    _list_orphan_overrides_for_package,
    _remove_package_v3_from_store,
    _resolve_package_version,
    _v3_overrides_blocking_update,
)
from spark.assets import (
    _AGENTS_INDEX_BEGIN,
    _AGENTS_INDEX_END,
    _CLINERULES_TEMPLATE_HEADER,
    _PROJECT_PROFILE_TEMPLATE,
    _agents_index_section_text,
    _apply_phase6_assets,
    _collect_engine_agents,
    _collect_package_agents,
    _extract_profile_summary,
    _read_agent_summary,
    _render_agents_md,
    _render_clinerules,
    _render_plugin_agents_md,
    _render_project_profile_template,
)
from spark.inventory import EngineInventory, FrameworkInventory

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as _import_exc:
    import logging as _logging
    _logging.getLogger("spark-framework-engine").critical(
        "mcp library not installed. Run: pip install mcp"
    )
    raise SystemExit(1) from _import_exc

_log: logging.Logger = logging.getLogger("spark-framework-engine")


def _gateway_write_text(
    workspace_root: Path,
    github_rel: str,
    content: str,
    manifest_manager: ManifestManager,
    owner: str,
    version: str,
    merge_strategy: str | None = None,
) -> Path:
    """Route text writes under ``.github/`` through ``WorkspaceWriteGateway``.

    Centralizza la scrittura ``write_text`` su ``<workspace>/.github/{github_rel}``
    e l'aggiornamento del manifest entry corrispondente (INVARIANTE-4).

    Args:
        workspace_root: root assoluto del workspace utente.
        github_rel: path relativo a ``.github/`` (senza prefisso).
        content: testo UTF-8 da scrivere.
        manifest_manager: manager del manifest da aggiornare.
        owner: package id proprietario del file.
        version: versione del pacchetto proprietario.
        merge_strategy: strategia di merge opzionale (passata al manifest entry).

    Returns:
        Path assoluto del file scritto.
    """
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
    """Route binary writes under ``.github/`` through ``WorkspaceWriteGateway``.

    Variante binaria di :func:`_gateway_write_text`. Usata per file non testuali
    (es. asset copiati durante install).

    Args:
        workspace_root: root assoluto del workspace utente.
        github_rel: path relativo a ``.github/`` (senza prefisso).
        content: bytes da scrivere.
        manifest_manager: manager del manifest da aggiornare.
        owner: package id proprietario del file.
        version: versione del pacchetto proprietario.

    Returns:
        Path assoluto del file scritto.
    """
    gateway = WorkspaceWriteGateway(workspace_root, manifest_manager)
    return gateway.write_bytes(github_rel, content, owner, version)


class SparkFrameworkEngine:

    def __init__(
        self,
        mcp: FastMCP,
        context: WorkspaceContext,
        inventory: FrameworkInventory,
        *,
        runtime_dir: Path | None = None,
    ) -> None:
        self._mcp = mcp
        self._ctx = context
        self._inventory = inventory
        self._bootstrap_workspace_tool: Callable[..., Any] | None = None
        # Fase 3: directory di runtime isolata per workspace (engine-local).
        # Fallback: calcola in-process se non passata dal sequence builder.
        if runtime_dir is not None:
            self._runtime_dir: Path = runtime_dir
        else:
            from spark.boot.validation import resolve_runtime_dir  # noqa: PLC0415
            self._runtime_dir = resolve_runtime_dir(context.engine_root, context.workspace_root)
        # v3.0: traccia URI alias deprecati gia' loggati per evitare spam.
        self._logged_alias_uris: set[str] = set()

    def _minimal_bootstrap_required_paths(self) -> tuple[Path, ...]:
        """Return the minimal workspace files required for SPARK agent discovery."""
        github_root = self._ctx.github_root
        return (
            github_root / "agents" / "spark-assistant.agent.md",
            github_root / "agents" / "spark-guide.agent.md",
            github_root / "AGENTS.md",
            github_root / "copilot-instructions.md",
            github_root / "project-profile.md",
        )

    def ensure_minimal_bootstrap(self) -> dict[str, Any]:
        """Bootstrap the minimal Layer 0 assets when the workspace is still empty."""
        if self._ctx.workspace_root == self._ctx.engine_root:
            _log.info(
                "Skipping auto-bootstrap because workspace_root matches engine_root: %s",
                self._ctx.workspace_root,
            )
            return {"success": True, "status": "skipped_engine_workspace"}

        if self._bootstrap_workspace_tool is None:
            return {"success": False, "status": "bootstrap_tool_unavailable"}

        if all(path.is_file() for path in self._minimal_bootstrap_required_paths()):
            return {"success": True, "status": "already_present"}

        try:
            return asyncio.run(self._bootstrap_workspace_tool())
        except RuntimeError as exc:
            _log.warning("Auto-bootstrap skipped: %s", exc)
            return {
                "success": False,
                "status": "auto_bootstrap_skipped",
                "error": str(exc),
            }

    # ------------------------------------------------------------------
    # v3 lifecycle methods (install / update / remove store-based)
    # ------------------------------------------------------------------

    def _v3_runtime_state(self) -> tuple[ManifestManager, "McpResourceRegistry", Path]:
        """Comodità: ritorna (manifest, registry, engine_root) del contesto attivo."""
        manifest = ManifestManager(self._ctx.github_root)
        registry = self._inventory.mcp_registry
        if registry is None:
            # Inizializzazione lazy in caso il registry non sia stato popolato.
            registry = self._inventory.populate_mcp_registry(
                EngineInventory(engine_root=self._ctx.engine_root).engine_manifest, {}
            )
        return manifest, registry, self._ctx.engine_root

    def _is_github_write_authorized_v3(self) -> bool:
        """Legge ``github_write_authorized`` dallo state file dell'orchestrator.

        Wrapper minimale per i metodi v3 che vivono fuori dalla closure
        ``register_tools`` dove la stessa logica è già inline.
        """
        state_path = (
            self._ctx.github_root / "runtime" / "orchestrator-state.json"
        )
        if not state_path.is_file():
            return False
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return bool(payload.get("github_write_authorized", False))

    def _v3_repopulate_registry(self) -> None:
        """Ricostruisce il registry MCP dopo install/remove/update v3."""
        engine_manifest = EngineInventory(engine_root=self._ctx.engine_root).engine_manifest
        manifest = ManifestManager(self._ctx.github_root)
        store = PackageResourceStore(self._ctx.engine_root)
        installed = manifest.get_installed_versions()
        package_manifests: dict[str, dict[str, Any]] = {}
        for pkg_id in installed:
            pkg_manifest_path = store.packages_root / pkg_id / "package-manifest.json"
            if pkg_manifest_path.is_file():
                try:
                    package_manifests[pkg_id] = json.loads(
                        pkg_manifest_path.read_text(encoding="utf-8")
                    )
                except (OSError, json.JSONDecodeError) as exc:
                    _log.warning(
                        "[SPARK-ENGINE][WARNING] Cannot reload manifest for %s: %s",
                        pkg_id,
                        exc,
                    )
        self._inventory.populate_mcp_registry(engine_manifest, package_manifests)

    async def _install_package_v3(
        self,
        package_id: str,
        pkg: Mapping[str, Any],
        pkg_manifest: Mapping[str, Any],
        pkg_version: str,
        min_engine_version: str,
        dependencies: list[str],
        conflict_mode: str,
        build_install_result: Callable[..., dict[str, Any]],
    ) -> dict[str, Any]:
        """Install a v3 package into the engine store and update workspace manifest.

        Args:
            package_id: ID del pacchetto.
            pkg: entry registry (con repo_url).
            pkg_manifest: manifest scaricato.
            pkg_version: versione risolta.
            min_engine_version: versione minima dichiarata.
            dependencies: dipendenze già validate.
            conflict_mode: modalità conflitti propagata dal chiamante.
            build_install_result: factory per result dict consistenti.

        Returns:
            Dict MCP-friendly con ``success`` + ``installation_mode == "v3_store"``.
            Idempotente: re-install della stessa versione = no-op success.
        """
        if not self._is_github_write_authorized_v3():
            return build_install_result(
                False,
                error="Writing under .github/ is not authorized in this workspace.",
                package=package_id,
                version=pkg_version,
            )

        manifest, registry, engine_root = self._v3_runtime_state()
        store = PackageResourceStore(engine_root)
        existing_entries = manifest.load()
        # Cerchiamo entry sentinella v3_store esistente per detection idempotenza.
        existing_v3_entry = next(
            (
                e
                for e in existing_entries
                if str(e.get("installation_mode", "")).strip() == "v3_store"
                and str(e.get("package", "")).strip() == package_id
            ),
            None,
        )
        if (
            existing_v3_entry is not None
            and str(existing_v3_entry.get("package_version", "")).strip() == pkg_version
            and (store.packages_root / package_id / "package-manifest.json").is_file()
        ):
            _log.info(
                "[SPARK-ENGINE][INFO] Package %s@%s already installed (v3_store).",
                package_id,
                pkg_version,
            )
            return build_install_result(
                True,
                package=package_id,
                version=pkg_version,
                installation_mode="v3_store",
                store_path=str(store.packages_root / package_id),
                files_installed=list(existing_v3_entry.get("files", []) or []),
                idempotent=True,
                message=f"Package {package_id}@{pkg_version} already installed.",
            )

        # Scarichiamo i file nello store. In caso di errore non scriviamo nulla.
        store_result = _install_package_v3_into_store(
            engine_root=engine_root,
            package_id=package_id,
            pkg=pkg,
            pkg_manifest=pkg_manifest,
            fetch_raw_file=RegistryClient(self._ctx.github_root).fetch_raw_file,
        )
        if not store_result["success"]:
            return build_install_result(
                False,
                error="Cannot fetch v3 package files: " + "; ".join(store_result["errors"]),
                package=package_id,
                version=pkg_version,
                installation_mode="v3_store",
                store_path=store_result.get("store_path"),
            )

        # Aggiorniamo il manifest workspace con la sola entry sentinella v3_store.
        new_entries = [
            e
            for e in existing_entries
            if not (
                str(e.get("installation_mode", "")).strip() == "v3_store"
                and str(e.get("package", "")).strip() == package_id
            )
        ]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_entries.append(
            {
                "file": _v3_store_sentinel_file(package_id),
                "package": package_id,
                "package_version": pkg_version,
                "min_engine_version": min_engine_version,
                "installed_at": now,
                "installation_mode": "v3_store",
                "store_path": store_result["store_path"],
                "files": store_result["files"],
                "dependencies": list(dependencies),
            }
        )
        manifest.save(new_entries)

        # Re-popoliamo il registry MCP per esporre subito le risorse
        # del pacchetto appena installato (idempotente).
        self._v3_repopulate_registry()

        # Rigeneriamo gli asset Phase 6 (AGENTS.md, AGENTS-{pkg}.md, ecc.).
        try:
            installed_ids = list(manifest.get_installed_versions().keys())
            _phase6_gateway = WorkspaceWriteGateway(self._ctx.workspace_root, manifest)
            phase6_report = _apply_phase6_assets(
                self._ctx.workspace_root,
                self._ctx.engine_root,
                installed_ids,
                github_write_authorized=True,
                gateway=_phase6_gateway,
                engine_version=ENGINE_VERSION,
            )
        except OSError as exc:
            _log.warning(
                "[SPARK-ENGINE][WARNING] Phase 6 regeneration after v3 install failed: %s",
                exc,
            )
            phase6_report = {"error": str(exc)}

        return build_install_result(
            True,
            package=package_id,
            version=pkg_version,
            installation_mode="v3_store",
            store_path=store_result["store_path"],
            files_installed=store_result["files"],
            phase6_report=phase6_report,
            conflict_mode=conflict_mode,
        )

    async def _remove_package_v3(
        self,
        package_id: str,
        manifest: ManifestManager,
        v3_entry: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Rimuove un pacchetto v3 dallo store + manifest + registry.

        Args:
            package_id: ID del pacchetto.
            manifest: ManifestManager attivo.
            v3_entry: entry sentinella v3_store letta dal manifest.

        Returns:
            Dict con ``success``, ``removed_files``, ``orphan_overrides``,
            ``store_path`` e report Phase 6.
        """
        registry = self._inventory.mcp_registry
        # Lista override orfani PRIMA di toccare il registry, così possiamo
        # restituire all'utente i path pertinenti.
        orphan_overrides = _list_orphan_overrides_for_package(registry, package_id)

        # Rimuoviamo dallo store fisico.
        store_result = _remove_package_v3_from_store(self._ctx.engine_root, package_id)

        # Rimuoviamo manualmente la sola entry v3 dal manifest (le legacy
        # remain intoccate nel caso esistessero, ma per v3 puro non esistono).
        entries = manifest.load()
        remaining = [
            e
            for e in entries
            if not (
                str(e.get("installation_mode", "")).strip() == "v3_store"
                and str(e.get("package", "")).strip() == package_id
            )
        ]
        manifest.save(remaining)

        # Deregistra le URI del pacchetto dal registry MCP.
        unregistered = registry.unregister_package(package_id)

        # Re-popoliamo per garantire stato consistente con altri pacchetti.
        self._v3_repopulate_registry()

        # Phase 6 regen senza il pacchetto.
        installed_ids = list(manifest.get_installed_versions().keys())
        try:
            _phase6_gateway = WorkspaceWriteGateway(self._ctx.workspace_root, manifest)
            phase6_report = _apply_phase6_assets(
                self._ctx.workspace_root,
                self._ctx.engine_root,
                installed_ids,
                github_write_authorized=self._is_github_write_authorized_v3(),
                gateway=_phase6_gateway,
                engine_version=ENGINE_VERSION,
            )
        except OSError as exc:
            _log.warning(
                "[SPARK-ENGINE][WARNING] Phase 6 regeneration after v3 remove failed: %s",
                exc,
            )
            phase6_report = {"error": str(exc)}

        return {
            "success": True,
            "package": package_id,
            "installation_mode": "v3_store",
            "store_path": store_result.get("store_path"),
            "store_removed": store_result.get("removed", False),
            "files_removed_from_manifest": list(v3_entry.get("files", []) or []),
            "registry_uris_unregistered": unregistered,
            "orphan_overrides": orphan_overrides,
            "phase6_report": phase6_report,
        }

    async def _update_package_v3(
        self,
        package_id: str,
        pkg: Mapping[str, Any],
        pkg_manifest: Mapping[str, Any],
        pkg_version: str,
        min_engine_version: str,
        dependencies: list[str],
        conflict_mode: str,
        build_install_result: Callable[..., dict[str, Any]],
    ) -> dict[str, Any]:
        """Aggiorna un pacchetto v3 nello store, preservando gli override workspace.

        Args:
            stessi argomenti di ``_install_package_v3``.

        Returns:
            Dict con ``success``, ``override_blocked`` (lista URI risorse non
            sovrascritte) e ``files_updated``.
        """
        registry = self._inventory.mcp_registry
        # Re-popoliamo per allineare il registry con eventuali override
        # workspace creati dopo l'install (necessario per has_override()).
        self._v3_repopulate_registry()
        registry = self._inventory.mcp_registry
        # Risorse con override attivo: NON le sovrascriveremo nello store?
        # NOTA: nello v3 store le risorse del pacchetto sono "canoniche".
        # L'override workspace ha priorità di lettura via McpResourceRegistry,
        # quindi anche aggiornando lo store l'utente continua a vedere il
        # proprio override. Mantenere lo store aggiornato è corretto e
        # raccomandato. Riportiamo comunque all'utente la lista override
        # bloccanti come informazione diagnostica.
        override_blocked = _v3_overrides_blocking_update(registry, package_id, pkg_manifest)

        # Riusiamo il path di install (idempotente: se versione uguale → no-op).
        result = await self._install_package_v3(
            package_id=package_id,
            pkg=pkg,
            pkg_manifest=pkg_manifest,
            pkg_version=pkg_version,
            min_engine_version=min_engine_version,
            dependencies=dependencies,
            conflict_mode=conflict_mode,
            build_install_result=build_install_result,
        )
        if isinstance(result, dict):
            result["override_blocked"] = override_blocked
            result["update_mode"] = "v3_store"
        return result

    def register_resources(self) -> None:
        """Register all MCP resources.

        Portability note: MCP Prompts are intentionally not registered here.
        VS Code handles .github/prompts/ natively as slash commands; alternative
        MCP clients will see prompts only as text resources, not as native MCP
        Prompt artefacts. Known v1 constraint, correct by design.
        """
        inventory = self._inventory
        ctx = self._ctx
        manifest = ManifestManager(ctx.github_root)
        resource_uris: list[str] = []

        def _register_resource(uri: str) -> Any:
            resource_uris.append(uri)
            return self._mcp.resource(uri)

        def _fmt_list(items: list[FrameworkFile], title: str) -> str:
            if not items:
                return f"# {title}\n\nNone found."
            lines = [f"# {title} ({len(items)} total)\n"]
            for ff in items:
                desc = str(ff.summary)[:120] if ff.summary else "(no description)"
                lines.append(f"- {ff.name}: {desc}")
            return "\n".join(lines)

        def _fmt_workspace_info(info: dict[str, Any]) -> str:
            lines = ["# SPARK Framework Engine — Workspace Info\n"]
            for key, val in info.items():
                lines.append(f"{key}: {val}")
            return "\n".join(lines)

        @_register_resource("agents://list")
        async def resource_agents_list() -> str:
            return _fmt_list(inventory.list_agents(), "SCF Agents")

        # v3.0: helper di lettura via registry con fallback all'inventory locale.
        def _registry_read(resource_type: str, name: str) -> str | None:
            registry = inventory.mcp_registry
            if registry is None:
                return None
            uri = McpResourceRegistry.make_uri(resource_type, name)
            target = registry.resolve(uri)
            if target is None or not target.is_file():
                # Fallback case-insensitive sui nomi registrati.
                lower = name.lower()
                for candidate_uri in registry.list_by_type(resource_type):
                    _, _, candidate_name = candidate_uri.partition("://")
                    if candidate_name.lower() == lower:
                        target = registry.resolve(candidate_uri)
                        break
            if target is None or not target.is_file():
                return None
            try:
                return target.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None

        @_register_resource("agents://{name}")
        async def resource_agent_by_name(name: str) -> str:
            content = _registry_read("agents", name)
            if content is not None:
                return content
            for ff in inventory.list_agents():
                if ff.name.lower() == name.lower():
                    return ff.path.read_text(encoding="utf-8", errors="replace")
            return f"Agent '{name}' not found. Use agents://list to see available agents."


        @_register_resource("skills://list")
        async def resource_skills_list() -> str:
            return _fmt_list(inventory.list_skills(), "SCF Skills")

        @_register_resource("skills://{name}")
        async def resource_skill_by_name(name: str) -> str:
            query = name.removesuffix(".skill")
            content = _registry_read("skills", query)
            if content is not None:
                return content
            qlow = query.lower()
            for ff in inventory.list_skills():
                if ff.name.lower().removesuffix(".skill") == qlow:
                    return ff.path.read_text(encoding="utf-8", errors="replace")
            return f"Skill '{name}' not found. Use skills://list to see available skills."

        # --- MCP Resource Handler: agents://{name} ---
        @_register_resource("agents://{name}")
        async def resource_agent_by_name(name: str) -> str:
            query = name.removesuffix(".agent")
            content = _registry_read("agents", query)
            if content is not None:
                return content
            qlow = query.lower()
            for ff in inventory.list_agents():
                if ff.name.lower().removesuffix(".agent") == qlow:
                    return ff.path.read_text(encoding="utf-8", errors="replace")
            return f"Agent '{name}' not found. Use agents://list to see available agents."

        # --- MCP Resource Handler: prompts://{name} ---
        @_register_resource("prompts://{name}")
        async def resource_prompt_by_name(name: str) -> str:
            query = name.removesuffix(".prompt")
            content = _registry_read("prompts", query)
            if content is not None:
                return content
            qlow = query.lower()
            for ff in inventory.list_prompts():
                if ff.name.lower().removesuffix(".prompt") == qlow:
                    return ff.path.read_text(encoding="utf-8", errors="replace")
            return f"Prompt '{name}' not found. Use prompts://list."

        @_register_resource("instructions://list")
        async def resource_instructions_list() -> str:
            return _fmt_list(inventory.list_instructions(), "SCF Instructions")

        @_register_resource("instructions://{name}")
        async def resource_instruction_by_name(name: str) -> str:
            query = name.removesuffix(".instructions")
            content = _registry_read("instructions", query)
            if content is not None:
                return content
            qlow = query.lower()
            for ff in inventory.list_instructions():
                if ff.name.lower().removesuffix(".instructions") == qlow:
                    return ff.path.read_text(encoding="utf-8", errors="replace")
            return f"Instruction '{name}' not found. Use instructions://list."

        # ---- v2.4.0: engine-hosted skills and instructions ----
        engine_inventory = EngineInventory(engine_root=self._ctx.engine_root)

        def _log_alias_once(alias_uri: str, canonical_uri: str) -> None:
            if alias_uri in self._logged_alias_uris:
                return
            self._logged_alias_uris.add(alias_uri)
            _log.warning(
                "[SPARK-ENGINE][WARN] URI deprecato %s -> usare %s. "
                "Alias rimosso in v4.0.",
                alias_uri,
                canonical_uri,
            )

        @_register_resource("engine-skills://list")
        async def resource_engine_skills_list() -> str:
            return _fmt_list(engine_inventory.list_skills(), "SCF Engine-Hosted Skills")

        @_register_resource("engine-skills://{name}")
        async def resource_engine_skill_by_name(name: str) -> str:
            _log_alias_once(f"engine-skills://{name}", f"skills://{name}")
            return await resource_skill_by_name(name)

        @_register_resource("engine-instructions://list")
        async def resource_engine_instructions_list() -> str:
            return _fmt_list(
                engine_inventory.list_instructions(), "SCF Engine-Hosted Instructions"
            )

        @_register_resource("engine-instructions://{name}")
        async def resource_engine_instruction_by_name(name: str) -> str:
            _log_alias_once(
                f"engine-instructions://{name}", f"instructions://{name}"
            )
            return await resource_instruction_by_name(name)

        @_register_resource("prompts://list")
        async def resource_prompts_list() -> str:
            return _fmt_list(inventory.list_prompts(), "SCF Prompts")

        @_register_resource("prompts://{name}")
        async def resource_prompt_by_name(name: str) -> str:
            query = name.removesuffix(".prompt")
            content = _registry_read("prompts", query)
            if content is not None:
                return content
            qlow = query.lower()
            for ff in inventory.list_prompts():
                if ff.name.lower().removesuffix(".prompt") == qlow:
                    return ff.path.read_text(encoding="utf-8", errors="replace")
            return f"Prompt '{name}' not found. Use prompts://list."

        @_register_resource("scf://global-instructions")
        async def resource_global_instructions() -> str:
            ff = inventory.get_global_instructions()
            return ff.path.read_text(encoding="utf-8", errors="replace") if ff else "copilot-instructions.md not found."

        @_register_resource("scf://project-profile")
        async def resource_project_profile() -> str:
            ff = inventory.get_project_profile()
            if ff is None:
                return "project-profile.md not found in .github/."
            content = ff.path.read_text(encoding="utf-8", errors="replace")
            if not ff.metadata.get("initialized", False):
                return "# WARNING: project not initialized (initialized: false)\nRun #project-setup to configure this workspace.\n\n" + content
            return content

        @_register_resource("scf://model-policy")
        async def resource_model_policy() -> str:
            ff = inventory.get_model_policy()
            return ff.path.read_text(encoding="utf-8", errors="replace") if ff else "model-policy.instructions.md not found."

        @_register_resource("scf://agents-index")
        async def resource_agents_index() -> str:
            indexes = inventory.list_agents_indexes()
            if not indexes:
                return "AGENTS.md not found."
            return "\n\n---\n\n".join(
                ff.path.read_text(encoding="utf-8", errors="replace")
                for ff in indexes
            )

        @_register_resource("scf://framework-version")
        async def resource_framework_version() -> str:
            installed_versions = manifest.get_installed_versions()
            lines = [
                f"SPARK Framework Engine version: {ENGINE_VERSION}",
                "",
                "Installed SCF packages:",
            ]
            if installed_versions:
                for package_id, package_version in installed_versions.items():
                    lines.append(f"- {package_id}: {package_version}")
            else:
                lines.append("- none")
            return "\n".join(lines)

        @_register_resource("scf://workspace-info")
        async def resource_workspace_info_res() -> str:
            info = build_workspace_info(ctx, inventory)
            return _fmt_workspace_info(info)

        @_register_resource("scf://runtime-state")
        async def resource_runtime_state() -> str:
            """Stato runtime orchestratore come JSON formattato."""
            state = inventory.get_orchestrator_state()
            return json.dumps(state, indent=2, ensure_ascii=False)

        _log.info("[SPARK-ENGINE][INFO] Resources registrate: %d", len(resource_uris))

    def register_tools(self) -> None:  # noqa: C901
        """Register all MCP tools. Resources (15) and Tools (44)."""
        inventory = self._inventory
        tool_names: list[str] = []

        def _register_tool(name: str) -> Any:
            tool_names.append(name)
            return self._mcp.tool()

        def _ff_to_dict(ff: FrameworkFile) -> dict[str, Any]:
            return {"name": ff.name, "path": str(ff.path), "category": ff.category, "summary": ff.summary, "metadata": ff.metadata}

        # ------------------------------------------------------------------
        # v3.0 Override tools (scf_list_overrides, scf_read_resource,
        # scf_override_resource, scf_drop_override)
        # ------------------------------------------------------------------

        def _parse_resource_uri(uri: str) -> tuple[str, str] | None:
            if not isinstance(uri, str) or "://" not in uri:
                return None
            scheme, _, name = uri.partition("://")
            if scheme not in _RESOURCE_TYPES:
                return None
            if not name:
                return None
            return scheme, name

        def _ensure_registry() -> McpResourceRegistry:
            if inventory.mcp_registry is None:
                # Boot tardivo: popola con engine-manifest se possibile.
                try:
                    engine_manifest = EngineInventory(engine_root=self._ctx.engine_root).engine_manifest
                except Exception:  # pragma: no cover - difensivo
                    engine_manifest = {}
                inventory.populate_mcp_registry(engine_manifest=engine_manifest)
            assert inventory.mcp_registry is not None  # noqa: S101
            return inventory.mcp_registry

        @_register_tool("scf_list_overrides")
        async def scf_list_overrides(
            resource_type: str | None = None,
        ) -> dict[str, Any]:
            """Lista override workspace registrati nel McpResourceRegistry.

            Args:
                resource_type: filtro opzionale (agents|prompts|skills|instructions).
            """
            registry = _ensure_registry()
            if resource_type is not None and resource_type not in _RESOURCE_TYPES:
                return {
                    "success": False,
                    "error": f"resource_type non valido: {resource_type}",
                    "supported": list(_RESOURCE_TYPES),
                }
            items: list[dict[str, Any]] = []
            for uri in registry.list_all():
                if not registry.has_override(uri):
                    continue
                meta = registry.get_metadata(uri) or {}
                rtype = str(meta.get("resource_type", ""))
                if resource_type is not None and rtype != resource_type:
                    continue
                override_path = meta.get("override")
                sha = ""
                if override_path:
                    try:
                        sha = _sha256_text(
                            Path(override_path).read_text(encoding="utf-8")
                        )
                    except OSError:
                        sha = ""
                _, _, name = uri.partition("://")
                items.append({
                    "uri": uri,
                    "type": rtype,
                    "name": name,
                    "path": str(override_path) if override_path else None,
                    "sha256": sha,
                })
            return {"count": len(items), "items": items}

        @_register_tool("scf_read_resource")
        async def scf_read_resource(
            uri: str, source: str = "auto"
        ) -> dict[str, Any]:
            """Legge il contenuto di una risorsa MCP (engine o override).

            Args:
                uri: URI nel formato ``{type}://{name}``.
                source: ``auto`` (override > engine), ``engine``, ``override``.
            """
            parsed = _parse_resource_uri(uri)
            if parsed is None:
                return {
                    "success": False,
                    "error": f"URI non valido: {uri}",
                }
            if source not in ("auto", "engine", "override"):
                return {
                    "success": False,
                    "error": f"source non valido: {source}",
                }
            registry = _ensure_registry()
            target: Path | None
            actual_source: str
            if source == "engine":
                target = registry.resolve_engine(uri)
                actual_source = "engine"
            elif source == "override":
                if not registry.has_override(uri):
                    return {
                        "success": False,
                        "error": f"Override non presente per {uri}",
                    }
                meta = registry.get_metadata(uri) or {}
                ov = meta.get("override")
                target = Path(ov) if ov else None
                actual_source = "override"
            else:  # auto
                target = registry.resolve(uri)
                actual_source = "override" if registry.has_override(uri) else "engine"
            if target is None or not target.is_file():
                return {
                    "success": False,
                    "error": f"Risorsa non trovata: {uri} (source={source})",
                }
            try:
                content = target.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                return {
                    "success": False,
                    "error": f"Errore lettura {target}: {exc}",
                }
            return {
                "success": True,
                "uri": uri,
                "source": actual_source,
                "path": str(target),
                "content": content,
            }

        @_register_tool("scf_get_skill_resource")
        async def scf_get_skill_resource(name: str) -> dict[str, Any]:
            """Return full content and metadata for a single SCF skill by name via skills:// URI."""
            uri = McpResourceRegistry.make_uri("skills", name)
            ff = inventory.mcp_registry.resolve(uri)
            if ff is None:
                return {
                    "success": False,
                    "error": f"Skill resource URI not found: {uri}",
                    "available": [ff.name for ff in inventory.list_skills()],
                }
            result = _ff_to_dict(ff)
            result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
            result["mcp_uri"] = uri
            result["mime_type"] = "text/markdown"
            return result

        @_register_tool("scf_get_instruction_resource")
        async def scf_get_instruction_resource(name: str) -> dict[str, Any]:
            """Return full content and metadata for a single SCF instruction by name via instructions:// URI."""
            uri = McpResourceRegistry.make_uri("instructions", name)
            ff = inventory.mcp_registry.resolve(uri)
            if ff is None:
                return {
                    "success": False,
                    "error": f"Instruction resource URI not found: {uri}",
                    "available": [ff.name for ff in inventory.list_instructions()],
                }
            result = _ff_to_dict(ff)
            result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
            result["mcp_uri"] = uri
            result["mime_type"] = "text/markdown"
            return result

        @_register_tool("scf_get_agent_resource")
        async def scf_get_agent_resource(name: str) -> dict[str, Any]:
            """Return full content and metadata for a single SCF agent by name via agents:// URI."""
            uri = McpResourceRegistry.make_uri("agents", name)
            ff = inventory.mcp_registry.resolve(uri)
            if ff is None:
                return {
                    "success": False,
                    "error": f"Agent resource URI not found: {uri}",
                    "available": [ff.name for ff in inventory.list_agents()],
                }
            result = _ff_to_dict(ff)
            result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
            result["mcp_uri"] = uri
            result["mime_type"] = "text/markdown"
            return result

        @_register_tool("scf_get_prompt_resource")
        async def scf_get_prompt_resource(name: str) -> dict[str, Any]:
            """Return full content and metadata for a single SCF prompt by name via prompts:// URI."""
            uri = McpResourceRegistry.make_uri("prompts", name)
            ff = inventory.mcp_registry.resolve(uri)
            if ff is None:
                return {
                    "success": False,
                    "error": f"Prompt resource URI not found: {uri}",
                    "available": [ff.name for ff in inventory.list_prompts()],
                }
            result = _ff_to_dict(ff)
            result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
            result["mcp_uri"] = uri
            result["mime_type"] = "text/markdown"
            return result

        @_register_tool("scf_override_resource")
        async def scf_override_resource(
            uri: str, content: str
        ) -> dict[str, Any]:
            """Crea/aggiorna un override workspace per la risorsa indicata.

            Args:
                uri: URI nel formato ``{type}://{name}``.
                content: nuovo contenuto del file di override.
            """
            parsed = _parse_resource_uri(uri)
            if parsed is None:
                return {
                    "success": False,
                    "error": f"URI non valido: {uri}",
                }
            resource_type, name = parsed
            registry = _ensure_registry()
            if registry.resolve_engine(uri) is None and not registry.has_override(uri):
                return {
                    "success": False,
                    "error": (
                        f"Risorsa {uri} non registrata: l'override richiede una "
                        "risorsa engine o un override preesistente."
                    ),
                }
            orchestrator_state = inventory.get_orchestrator_state()
            if not bool(orchestrator_state.get("github_write_authorized", False)):
                return {
                    "success": False,
                    "error": "github_write_authorized=False: scrittura su .github/ non autorizzata.",
                    "authorization_required": True,
                }
            manifest_mgr = ManifestManager(self._ctx.github_root)
            try:
                target = manifest_mgr.write_override(resource_type, name, content)
            except (ValueError, OSError) as exc:
                return {"success": False, "error": str(exc)}
            registry.register_override(uri, target)
            return {
                "success": True,
                "uri": uri,
                "path": str(target),
                "sha256": _sha256_text(content),
            }

        @_register_tool("scf_drop_override")
        async def scf_drop_override(uri: str) -> dict[str, Any]:
            """Rimuove un override workspace e deregistra dal registry.

            Args:
                uri: URI nel formato ``{type}://{name}``.
            """
            parsed = _parse_resource_uri(uri)
            if parsed is None:
                return {
                    "success": False,
                    "error": f"URI non valido: {uri}",
                }
            resource_type, name = parsed
            registry = _ensure_registry()
            if not registry.has_override(uri):
                return {
                    "success": False,
                    "error": f"Nessun override registrato per {uri}",
                }
            orchestrator_state = inventory.get_orchestrator_state()
            if not bool(orchestrator_state.get("github_write_authorized", False)):
                return {
                    "success": False,
                    "error": "github_write_authorized=False: rimozione non autorizzata.",
                    "authorization_required": True,
                }
            manifest_mgr = ManifestManager(self._ctx.github_root)
            try:
                removed = manifest_mgr.drop_override(resource_type, name)
            except OSError as exc:
                return {"success": False, "error": str(exc)}
            registry.drop_override(uri)
            return {"success": True, "uri": uri, "file_removed": removed}

        @_register_tool("scf_list_agents")
        async def scf_list_agents() -> dict[str, Any]:
            """Return all discovered SCF agents with name, path and summary."""
            items = inventory.list_agents()
            return {"count": len(items), "agents": [_ff_to_dict(ff) for ff in items]}

        @_register_tool("scf_get_agent")
        async def scf_get_agent(name: str) -> dict[str, Any]:
            """Return full content and metadata for a single SCF agent by name."""
            for ff in inventory.list_agents():
                if ff.name.lower() == name.lower():
                    result = _ff_to_dict(ff)
                    result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
                    return result
            return {
                "success": False,
                "error": f"Agent '{name}' not found.",
                "available": [ff.name for ff in inventory.list_agents()],
            }

        @_register_tool("scf_list_skills")
        async def scf_list_skills() -> dict[str, Any]:
            """Return all discovered SCF skills with name, path and summary."""
            items = inventory.list_skills()
            return {"count": len(items), "skills": [_ff_to_dict(ff) for ff in items]}

        @_register_tool("scf_get_skill")
        async def scf_get_skill(name: str) -> dict[str, Any]:
            """Return full content and metadata for a single SCF skill by name."""
            query = name.lower().removesuffix(".skill")
            for ff in inventory.list_skills():
                if ff.name.lower().removesuffix(".skill") == query:
                    result = _ff_to_dict(ff)
                    result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
                    return result
            return {
                "success": False,
                "error": f"Skill '{name}' not found.",
                "available": [ff.name for ff in inventory.list_skills()],
            }

        @_register_tool("scf_list_instructions")
        async def scf_list_instructions() -> dict[str, Any]:
            """Return all discovered SCF instruction files with name, path and summary."""
            items = inventory.list_instructions()
            return {"count": len(items), "instructions": [_ff_to_dict(ff) for ff in items]}

        @_register_tool("scf_get_instruction")
        async def scf_get_instruction(name: str) -> dict[str, Any]:
            """Return full content and metadata for a single SCF instruction by name."""
            query = name.lower().removesuffix(".instructions")
            for ff in inventory.list_instructions():
                if ff.name.lower().removesuffix(".instructions") == query:
                    result = _ff_to_dict(ff)
                    result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
                    return result
            return {
                "success": False,
                "error": f"Instruction '{name}' not found.",
                "available": [ff.name for ff in inventory.list_instructions()],
            }

        @_register_tool("scf_list_prompts")
        async def scf_list_prompts() -> dict[str, Any]:
            """Return all SCF prompt files. Read-only — slash commands are handled natively by VS Code."""
            items = inventory.list_prompts()
            return {"count": len(items), "prompts": [_ff_to_dict(ff) for ff in items]}

        @_register_tool("scf_get_prompt")
        async def scf_get_prompt(name: str) -> dict[str, Any]:
            """Return full content of a SCF prompt file by stem name."""
            query = name.lower().removesuffix(".prompt")
            for ff in inventory.list_prompts():
                if ff.name.lower().removesuffix(".prompt") == query:
                    result = _ff_to_dict(ff)
                    result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
                    return result
            return {
                "success": False,
                "error": f"Prompt '{name}' not found.",
                "available": [ff.name for ff in inventory.list_prompts()],
            }

        @_register_tool("scf_get_project_profile")
        async def scf_get_project_profile() -> dict[str, Any]:
            """Return project-profile.md content, metadata and initialized state."""
            ff = inventory.get_project_profile()
            if ff is None:
                return {"success": False, "error": "project-profile.md not found in .github/."}
            result = _ff_to_dict(ff)
            result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
            result["initialized"] = bool(ff.metadata.get("initialized", False))
            if not result["initialized"]:
                result["warning"] = "Project not initialized. Run #project-setup to configure this workspace."
            return result

        @_register_tool("scf_get_global_instructions")
        async def scf_get_global_instructions() -> dict[str, Any]:
            """Return copilot-instructions.md content and metadata."""
            ff = inventory.get_global_instructions()
            if ff is None:
                return {"success": False, "error": "copilot-instructions.md not found in .github/."}
            result = _ff_to_dict(ff)
            result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
            return result

        @_register_tool("scf_get_model_policy")
        async def scf_get_model_policy() -> dict[str, Any]:
            """Return model-policy.instructions.md content and metadata."""
            ff = inventory.get_model_policy()
            if ff is None:
                return {
                    "success": False,
                    "error": "model-policy.instructions.md not found in .github/instructions/.",
                }
            result = _ff_to_dict(ff)
            result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
            return result

        @_register_tool("scf_get_framework_version")
        async def scf_get_framework_version() -> dict[str, Any]:
            """Return the engine version and installed SCF package versions."""
            return {
                "engine_version": ENGINE_VERSION,
                "packages": manifest.get_installed_versions(),
            }

        @_register_tool("scf_get_workspace_info")
        async def scf_get_workspace_info() -> dict[str, Any]:
            """Return workspace paths, initialization state and SCF asset counts."""
            return build_workspace_info(self._ctx, inventory)

        manifest = ManifestManager(self._ctx.github_root)
        registry = RegistryClient(self._ctx.github_root)
        merge_engine = MergeEngine()
        snapshots = SnapshotManager(self._runtime_dir / _SNAPSHOTS_SUBDIR)
        sessions = MergeSessionManager(self._runtime_dir / _MERGE_SESSIONS_SUBDIR)
        sessions.cleanup_expired_sessions()

        def _save_snapshots(package_id: str, files: list[tuple[str, Path]]) -> dict[str, list[str]]:
            """Persist BASE snapshots for written files without blocking the main operation."""
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
            """Read a UTF-8 workspace file, returning None for undecodable content."""
            try:
                return path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                _log.warning("Cannot read text file %s: %s", path, exc)
                return None

        def _supports_stateful_merge(conflict_mode: str) -> bool:
            """Return True for conflict modes that use a persistent merge session."""
            return conflict_mode in {"manual", "auto", "assisted"}

        def _render_marker_text(file_entry: dict[str, Any]) -> str:
            """Render or reuse the persisted marker text for one conflicting file."""
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
            """Build the persisted session payload for one conflicting file."""
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
            """Replace one normalized file entry inside an in-memory session payload."""
            files = list(session.get("files", []))
            files[index] = MergeSessionManager._normalize_session_file_entry(file_entry)
            session["files"] = files

        def _find_session_entry(
            session: dict[str, Any],
            conflict_id: str,
        ) -> tuple[int, dict[str, Any]] | None:
            """Find one conflict entry in a session by its stable conflict id."""
            for index, file_entry in enumerate(list(session.get("files", []))):
                if str(file_entry.get("conflict_id", "")).strip() == conflict_id:
                    return (index, dict(file_entry))
            return None

        def _count_remaining_conflicts(session: dict[str, Any]) -> int:
            """Count session entries that still need approval or manual resolution."""
            return sum(
                1
                for file_entry in list(session.get("files", []))
                if str(file_entry.get("resolution_status", "pending")).strip() != "approved"
            )

        def _resolve_conflict_automatically(file_entry: dict[str, Any]) -> str | None:
            """Return a safe automatic merge proposal only for clearly unambiguous cases."""
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
            persist: bool = True,
        ) -> dict[str, Any]:
            """Populate proposed_text and validator results for one conflict when safe."""
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

        def _build_install_result(success: bool, error: str | None = None, **extras: Any) -> dict[str, Any]:
            """Build a stable install/update payload with conflict metadata."""
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
        ) -> tuple[list[dict[str, Any]], list[str]]:
            """Fetch remote package files and attach SCF metadata for diffing and writes."""
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
            """Return a compact diff summary excluding unchanged files."""
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
            """Resolve the package-level update mode from request and workspace policy."""
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
        ) -> dict[str, Any]:
            """Return the common OWN-D flow metadata for install/update responses."""
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

        def _detect_workspace_migration_state() -> dict[str, Any]:
            """Return the current migration state for a legacy SCF workspace."""
            policy_payload, policy_source = _read_update_policy_payload(self._ctx.github_root)
            manifest_entries = manifest.load()
            sentinel_path = self._ctx.github_root / "agents" / "spark-assistant.agent.md"
            copilot_path = self._ctx.github_root / "copilot-instructions.md"
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
                "policy_path": str(_update_policy_path(self._ctx.github_root)),
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
            """Normalize install policies from legacy file_policies and schema 2.1 files_metadata."""
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
            """Reject extend on file types that cannot safely host SCF section markers."""
            if file_path.endswith(".agent.md"):
                raise ValueError(
                    f"Policy 'extend' is not supported for files ending with '.agent.md': {file_path}"
                )

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
            """Return package installation context or a structured failure result."""
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
            dependencies = _normalize_string_list(pkg_manifest.get("dependencies", []))
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
            file_policies: dict[str, str] | None = None,
        ) -> dict[str, Any]:
            """Classify package targets before any install or update writes.

            ``file_policies`` uses the simple manifest shape
            {".github/path.md": "extend|delegate|error"}.
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
                dest = self._ctx.workspace_root / file_path
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
            migrate_copilot_instructions: bool = False,
        ) -> dict[str, Any]:
            """Install an SCF package from the public registry into the active workspace .github/."""
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
                return await self._install_package_v3(
                    package_id=package_id,
                    pkg=pkg,
                    pkg_manifest=pkg_manifest,
                    pkg_version=pkg_version,
                    min_engine_version=min_engine_version,
                    dependencies=install_context["dependencies"],
                    conflict_mode=conflict_mode,
                    build_install_result=_build_install_result,
                )
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

            policy_payload, policy_source = _read_update_policy_payload(self._ctx.github_root)
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
                file_abs = self._ctx.github_root / rel_path
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
                    (rel, self._ctx.workspace_root / file_path)
                    for file_path, rel, _, _, _ in staged_files
                    if (self._ctx.workspace_root / file_path).is_file()
                ]
                if files_to_backup:
                    try:
                        backup_path = _scf_backup_workspace(
                            package_id,
                            files_to_backup,
                            backup_root=self._runtime_dir / _BACKUPS_SUBDIR,
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
                    dest = self._ctx.workspace_root / file_path
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
                            self._ctx.workspace_root,
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
                            self._ctx.workspace_root,
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
                                    self._ctx.workspace_root,
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
                                self._ctx.workspace_root,
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
                        self._ctx.workspace_root,
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
                            dest = self._ctx.workspace_root / workspace_path
                            validator_results = current_entry.get("validator_results")
                            if isinstance(validator_results, dict):
                                auto_validator_results[public_file] = validator_results

                            if resolution.get("success") is True:
                                proposed_text = str(current_entry.get("proposed_text", "") or "")
                                dest.parent.mkdir(parents=True, exist_ok=True)
                                _gateway_write_text(
                                    self._ctx.workspace_root,
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
                                self._ctx.workspace_root,
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
                                        (manifest_rel, self._ctx.workspace_root / workspace_path)
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

        def _summarize_available_updates(report: dict[str, Any]) -> list[dict[str, Any]]:
            """Extract only updatable packages from the update planner report."""
            return [
                {
                    "package": item.get("package", ""),
                    "installed": item.get("installed", ""),
                    "latest": item.get("latest", ""),
                }
                for item in report.get("updates", [])
                if item.get("status") == "update_available"
            ]

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
                v3_result = await self._update_package_v3(
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
                v3_result = await self._remove_package_v3(
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
            changelog_path = self._ctx.github_root / _CHANGELOGS_SUBDIR / f"{package_id}.md"
            return {
                "package": package_id,
                "path": str(changelog_path),
                "content": content,
                "version": _extract_version_from_changelog(changelog_path),
            }

        @_register_tool("scf_verify_workspace")
        async def scf_verify_workspace() -> dict[str, Any]:
            """Verify runtime manifest integrity against files currently present in .github/."""
            report = manifest.verify_integrity()
            summary = dict(report.get("summary", {}))
            issue_count = int(summary.get("issue_count", 0))
            summary["is_clean"] = issue_count == 0
            report["summary"] = summary
            return report

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

        @_register_tool("scf_get_runtime_state")
        async def scf_get_runtime_state() -> dict[str, Any]:
            """Leggi lo stato runtime dell'orchestratore dal workspace corrente."""
            return inventory.get_orchestrator_state()

        @_register_tool("scf_update_runtime_state")
        async def scf_update_runtime_state(patch: dict[str, Any]) -> dict[str, Any]:
            """Aggiorna selettivamente lo stato runtime dell'orchestratore nel workspace."""
            return inventory.set_orchestrator_state(patch)

        @_register_tool("scf_bootstrap_workspace")
        async def scf_bootstrap_workspace(
            install_base: bool = False,
            conflict_mode: str = "abort",
            update_mode: str = "",
            migrate_copilot_instructions: bool = False,
        ) -> dict[str, Any]:
            """Bootstrap only the Layer 0 gateway files into this workspace.

            Copies exactly the following files from the engine to the workspace:
            - agents/spark-assistant.agent.md
            - agents/spark-guide.agent.md
            - instructions/spark-assistant-guide.instructions.md (if present)
            - prompts/scf-*.prompt.md (all matching)

            If a file exists in the workspace and its sha256 differs from the engine source,
            it is NOT overwritten and a warning is logged to sys.stderr.
            Idempotence is guaranteed via the spark-assistant.agent.md sentinel.

            Returns a status-oriented payload with fields such as `status`,
            `files_written`, `preserved` and `note`, plus optional install and
            authorization metadata for extended flows.
            """
            if install_base and conflict_mode not in _SUPPORTED_CONFLICT_MODES:
                return {
                    "success": False,
                    "status": "error",
                    "files_written": [],
                    "preserved": [],
                    "workspace": str(self._ctx.workspace_root),
                    "install_base_requested": install_base,
                    "conflict_mode": conflict_mode,
                    "note": (
                        f"Unsupported conflict_mode '{conflict_mode}'. "
                        "Supported modes: abort, replace, manual, auto, assisted."
                    ),
                }
            normalized_bootstrap_mode = update_mode.strip().lower()
            allowed_bootstrap_modes = {"", "ask", "integrative", "conservative", "ask_later"}
            if normalized_bootstrap_mode not in allowed_bootstrap_modes:
                return {
                    "success": False,
                    "status": "error",
                    "files_written": [],
                    "preserved": [],
                    "workspace": str(self._ctx.workspace_root),
                    "install_base_requested": install_base,
                    "conflict_mode": conflict_mode,
                    "update_mode": update_mode,
                    "note": (
                        f"Unsupported update_mode '{update_mode}'. Supported modes: "
                        "ask, integrative, conservative, ask_later."
                    ),
                }
            bootstrap_source_root = self._ctx.engine_root / "packages" / "spark-base" / ".github"
            if not bootstrap_source_root.is_dir():
                bootstrap_source_root = self._ctx.engine_root / ".github"
            prompts_source_dir = bootstrap_source_root / "prompts"
            instructions_source_dir = bootstrap_source_root / "instructions"
            agents_source_dir = bootstrap_source_root / "agents"
            agent_source = agents_source_dir / "spark-assistant.agent.md"
            guide_agent_source = agents_source_dir / "spark-guide.agent.md"
            workspace_github_root = self._ctx.github_root
            sentinel = workspace_github_root / "agents" / "spark-assistant.agent.md"
            sentinel_rel = "agents/spark-assistant.agent.md"
            policy_payload, policy_source = _read_update_policy_payload(self._ctx.github_root)
            migration_state = _detect_workspace_migration_state()
            legacy_bootstrap_mode = normalized_bootstrap_mode == "" and policy_source != "file"

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
                policy_payload = _default_update_policy_payload()
                policy = policy_payload["update_policy"]
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
                return policy_payload, _write_update_policy_payload(self._ctx.github_root, policy_payload)

            diff_summary: dict[str, Any] = {"total": 0, "counts": {}, "files": []}
            effective_install_update_mode = "" if normalized_bootstrap_mode == "ask_later" else normalized_bootstrap_mode
            policy_created = False
            policy_path = _update_policy_path(self._ctx.github_root)

            if not legacy_bootstrap_mode:
                if policy_source != "file":
                    if normalized_bootstrap_mode == "":
                        return {
                            "success": True,
                            "status": "policy_configuration_required",
                            "files_written": [],
                            "preserved": [],
                            "workspace": str(self._ctx.workspace_root),
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
                                "success": True,
                                "status": "authorization_required",
                                "files_written": [],
                                "preserved": [],
                                "workspace": str(self._ctx.workspace_root),
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
                    policy_payload, policy_path = _configure_initial_bootstrap_policy(normalized_bootstrap_mode)
                    policy_source = "file"
                    policy_created = True

                if install_base:
                    install_context = _get_package_install_context("spark-base")
                    if install_context.get("success") is False:
                        return {
                            **install_context,
                            "status": "error",
                            "files_written": [],
                            "preserved": [],
                            "workspace": str(self._ctx.workspace_root),
                            "install_base_requested": install_base,
                            "conflict_mode": conflict_mode,
                            "update_mode": update_mode,
                            "policy_source": policy_source,
                        }
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
                            "success": False,
                            "status": "error",
                            "files_written": [],
                            "preserved": [],
                            "workspace": str(self._ctx.workspace_root),
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

                orchestrator_state_path = self._ctx.github_root / "runtime" / "orchestrator-state.json"
                if not orchestrator_state_path.is_file():
                    inventory.set_orchestrator_state({"github_write_authorized": False})
                orchestrator_state = inventory.get_orchestrator_state()
                github_write_authorized = bool(orchestrator_state.get("github_write_authorized", False))
                if not github_write_authorized:
                    return {
                        "success": True,
                        "status": "authorization_required",
                        "files_written": [],
                        "preserved": [],
                        "workspace": str(self._ctx.workspace_root),
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
                if not legacy_bootstrap_mode:
                    result["authorization_required"] = True
                    result["github_write_authorized"] = True
                    result["diff_summary"] = diff_summary

                # v3.0 — Phase 6 assets: AGENTS.md dinamico, .clinerules, profile.
                try:
                    orchestrator_state = inventory.get_orchestrator_state()
                    write_authorized = bool(
                        orchestrator_state.get("github_write_authorized", False)
                    )
                except Exception:  # pragma: no cover - defensive
                    write_authorized = False
                installed_for_phase6 = list(manifest.get_installed_versions().keys())
                try:
                    _phase6_gateway = WorkspaceWriteGateway(self._ctx.workspace_root, manifest)
                    phase6_report = _apply_phase6_assets(
                        self._ctx.workspace_root,
                        self._ctx.engine_root,
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

                base_install = await scf_install_package(
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

            prompt_sources = sorted(prompts_source_dir.glob("*.prompt.md"))
            instruction_sources = sorted(instructions_source_dir.glob("*.instructions.md"))
            root_sources = [
                bootstrap_source_root / "AGENTS.md",
                bootstrap_source_root / "copilot-instructions.md",
                bootstrap_source_root / "project-profile.md",
            ]
            bootstrap_targets: list[tuple[Path, Path]] = [
                (source_path, workspace_github_root / "prompts" / source_path.name)
                for source_path in prompt_sources
            ]
            bootstrap_targets.extend(
                (
                    source_path,
                    workspace_github_root / "instructions" / source_path.name,
                )
                for source_path in instruction_sources
            )
            bootstrap_targets.append(
                (guide_agent_source, workspace_github_root / "agents" / "spark-guide.agent.md")
            )
            bootstrap_targets.extend(
                (source_path, workspace_github_root / source_path.name)
                for source_path in root_sources
            )
            bootstrap_targets.append((agent_source, workspace_github_root / "agents" / "spark-assistant.agent.md"))

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
                    # Tracked with matching SHA — workspace already bootstrapped.
                    if all(
                        _bootstrap_target_is_satisfied(source_path, dest_path)
                        for source_path, dest_path in bootstrap_targets
                    ):
                        return await _finalize_bootstrap_result({
                            "success": True,
                            "status": "already_bootstrapped",
                            "files_written": [],
                            "preserved": [],
                            "workspace": str(self._ctx.workspace_root),
                            "note": "Bootstrap assets already present and verified. Run /scf-list-available to inspect the package catalog.",
                        })
                if user_mod is True:
                    # Sentinel tracked but modified by user — do not overwrite.
                    return {
                        "success": True,
                        "status": "user_modified",
                        "files_written": [],
                        "preserved": [sentinel_rel],
                        "workspace": str(self._ctx.workspace_root),
                        "install_base_requested": install_base,
                        "note": "Sentinel file has been modified by user. No files overwritten.",
                    }
                # user_mod is None → sentinel exists but not tracked; fall through to copy.

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
                    "preserved": [],
                    "workspace": str(self._ctx.workspace_root),
                    "install_base_requested": install_base,
                    "note": f"Bootstrap sources missing from engine repository: {missing_sources}",
                }

            files_written: list[str] = []
            preserved: list[str] = []
            written_paths: list[Path] = []
            identical_paths: list[Path] = []

            try:
                for source_path, dest_path in bootstrap_targets:
                    rel_path = dest_path.relative_to(self._ctx.workspace_root).as_posix()
                    github_rel = dest_path.relative_to(workspace_github_root).as_posix()
                    if dest_path.is_file():
                        if manifest._sha256(dest_path) == manifest._sha256(source_path):
                            _log.info("Bootstrap file already matches source: %s", rel_path)
                            identical_paths.append(dest_path)
                        else:
                            _log.warning("Bootstrap file preserved (existing different content): %s", rel_path)
                            preserved.append(rel_path)
                        continue

                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    # Preserve cross-owner ownership: skip gateway upsert if
                    # another package already owns this manifest entry.
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
                    _gateway_write_bytes(
                        self._ctx.workspace_root,
                        github_rel,
                        source_path.read_bytes(),
                        manifest,
                        _BOOTSTRAP_PACKAGE_ID,
                        ENGINE_VERSION,
                    )
                    written_paths.append(dest_path)
                    files_written.append(rel_path)
                    _log.info(
                        "[SPARK-ENGINE][INFO] Bootstrapped: %s",
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
                    "preserved": preserved,
                    "workspace": str(self._ctx.workspace_root),
                    "install_base_requested": install_base,
                    "note": f"Bootstrap failed while copying files: {exc}.{rollback_note}",
                }

            if written_paths or identical_paths:
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
                "preserved": preserved,
                "workspace": str(self._ctx.workspace_root),
                "note": "Bootstrap completed. Run /scf-list-available to inspect the package catalog.",
            })

        self._bootstrap_workspace_tool = scf_bootstrap_workspace

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
            workspace_root = self._ctx.workspace_root
            engine_cache = self._ctx.engine_root / "cache"
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
            dest = self._ctx.workspace_root / workspace_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            _gateway_write_text(
                self._ctx.workspace_root,
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
            dest = self._ctx.workspace_root / workspace_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            _gateway_write_text(
                self._ctx.workspace_root,
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
                dest = self._ctx.workspace_root / workspace_path
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

        @_register_tool("scf_get_update_policy")
        async def scf_get_update_policy() -> dict[str, Any]:
            """Return the workspace update policy used for SCF file updates."""
            payload, source = _read_update_policy_payload(self._ctx.github_root)
            return {
                "success": True,
                "policy": payload["update_policy"],
                "path": str(_update_policy_path(self._ctx.github_root)),
                "source": source,
            }

        @_register_tool("scf_set_update_policy")
        async def scf_set_update_policy(
            auto_update: bool,
            default_mode: str | None = None,
            mode_per_package: dict[str, str] | None = None,
            mode_per_file_role: dict[str, str] | None = None,
        ) -> dict[str, Any]:
            """Create or update the workspace update policy for SCF file operations."""
            payload, source = _read_update_policy_payload(self._ctx.github_root)
            policy = dict(payload["update_policy"])

            if default_mode is not None:
                validated_default_mode = _validate_update_mode(
                    default_mode,
                    allow_selective=False,
                )
                if validated_default_mode is None:
                    return {
                        "success": False,
                        "error": (
                            "Invalid default_mode. Supported values: ask, integrative, "
                            "replace, conservative."
                        ),
                        "path": str(_update_policy_path(self._ctx.github_root)),
                    }
                policy["default_mode"] = validated_default_mode

            if mode_per_package is not None:
                normalized_package_modes: dict[str, str] = {}
                invalid_package_modes: list[str] = []
                for package_key, mode_value in mode_per_package.items():
                    normalized_key = str(package_key).strip()
                    validated_mode = _validate_update_mode(str(mode_value), allow_selective=True)
                    if not normalized_key or validated_mode is None:
                        invalid_package_modes.append(f"{package_key}={mode_value}")
                        continue
                    normalized_package_modes[normalized_key] = validated_mode
                if invalid_package_modes:
                    return {
                        "success": False,
                        "error": "Invalid mode_per_package entries.",
                        "invalid_entries": invalid_package_modes,
                        "path": str(_update_policy_path(self._ctx.github_root)),
                    }
                policy["mode_per_package"] = normalized_package_modes

            if mode_per_file_role is not None:
                normalized_role_modes: dict[str, str] = {}
                invalid_role_modes: list[str] = []
                for role_key, mode_value in mode_per_file_role.items():
                    normalized_key = str(role_key).strip()
                    validated_mode = _validate_update_mode(str(mode_value), allow_selective=True)
                    if not normalized_key or validated_mode is None:
                        invalid_role_modes.append(f"{role_key}={mode_value}")
                        continue
                    normalized_role_modes[normalized_key] = validated_mode
                if invalid_role_modes:
                    return {
                        "success": False,
                        "error": "Invalid mode_per_file_role entries.",
                        "invalid_entries": invalid_role_modes,
                        "path": str(_update_policy_path(self._ctx.github_root)),
                    }
                policy["mode_per_file_role"] = normalized_role_modes

            policy["auto_update"] = bool(auto_update)
            policy["last_changed"] = _format_utc_timestamp(_utc_now())
            policy["changed_by_user"] = True

            saved_path = _write_update_policy_payload(
                self._ctx.github_root,
                {"update_policy": policy},
            )
            return {
                "success": True,
                "policy": policy,
                "path": str(saved_path),
                "source": source,
            }

        _log.info("[SPARK-ENGINE][INFO] Tools registrati: %d", len(tool_names))


