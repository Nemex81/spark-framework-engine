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
from spark.boot import install_helpers as _ih
from spark.boot.lifecycle import _V3LifecycleMixin
from spark.boot.tools_resources import (
    _ff_to_dict as _ff_to_dict_mod,
    register_resource_tools,
)
from spark.boot.tools_override import register_override_tools
from spark.boot.tools_bootstrap import register_bootstrap_tools
from spark.boot.tools_policy import register_policy_tools
from spark.boot.tools_packages import register_package_tools

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


class SparkFrameworkEngine(_V3LifecycleMixin):

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
        # D.0: runtime objects (inizializzati lazy via _init_runtime_objects).
        self._manifest: ManifestManager | None = None
        self._registry_client: RegistryClient | None = None
        self._merge_engine: MergeEngine | None = None
        self._snapshots: SnapshotManager | None = None
        self._sessions: MergeSessionManager | None = None
        self._install_package_tool_fn: Any | None = None

    def _init_runtime_objects(self) -> None:
        """Inizializza (idempotente) gli oggetti runtime come instance attributes.

        Deve essere chiamato all'inizio di register_tools() prima di qualsiasi
        uso di manifest, registry, merge_engine, snapshots o sessions.
        """
        if self._manifest is not None:
            # Già inizializzati — cleanup sessions e return.
            self._sessions.cleanup_expired_sessions()  # type: ignore[union-attr]
            return
        self._manifest = ManifestManager(self._ctx.github_root)
        self._registry_client = RegistryClient(self._ctx.github_root)
        self._merge_engine = MergeEngine()
        self._snapshots = SnapshotManager(self._runtime_dir / _SNAPSHOTS_SUBDIR)
        self._sessions = MergeSessionManager(self._runtime_dir / _MERGE_SESSIONS_SUBDIR)
        self._sessions.cleanup_expired_sessions()

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

        # Sentinel gate: la presenza simultanea di tutti i path Cat. A elencati in
        # ``_minimal_bootstrap_required_paths`` (incluso ``AGENTS.md`` come sentinella
        # di discovery) determina se il workspace è "già bootstrapped"; la cancellazione
        # manuale di uno qualunque di questi path forza un nuovo auto-bootstrap al boot.
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

    async def install_package_for_onboarding(
        self, package_id: str
    ) -> dict[str, Any]:
        """Esegue l'installazione di un pacchetto v3 nel contesto di onboarding.

        Wrapper minimale per ``_install_package_v3`` che risolve la dipendenza
        dal registry SCF e costruisce il contesto di installazione senza
        passare per le closure di ``register_tools``.
        Supporta solo pacchetti v3 (``min_engine_version >= "3.0.0"``).
        I pacchetti legacy non vengono installati per non compromettere l'avvio.

        Args:
            package_id: ID del pacchetto da installare (es. ``"spark-base"``).

        Returns:
            Dict con ``success: bool`` e informazioni sull'installazione.
        """
        from spark.core.utils import _is_v3_package  # noqa: PLC0415
        from spark.registry.client import RegistryClient  # noqa: PLC0415

        # Funzione locale per costruire un risultato consistente senza closure.
        def _simple_result(success: bool, error: str | None = None, **kw: Any) -> dict[str, Any]:
            out: dict[str, Any] = {"success": success, "package": package_id}
            if error:
                out["error"] = error
            out.update(kw)
            return out

        registry_client = RegistryClient(self._ctx.github_root)

        # Recupera lista pacchetti dal registry remoto
        try:
            packages = registry_client.list_packages()
        except Exception as exc:  # noqa: BLE001
            return _simple_result(False, error=f"Registry unavailable: {exc}")

        pkg = next((p for p in packages if p.get("id") == package_id), None)
        if pkg is None:
            return _simple_result(False, error=f"Package '{package_id}' not in registry.")

        # Scarica il manifest del pacchetto
        try:
            pkg_manifest: dict[str, Any] = registry_client.fetch_package_manifest(pkg["repo_url"])
        except Exception as exc:  # noqa: BLE001
            return _simple_result(False, error=f"Cannot fetch manifest: {exc}")

        # Solo pacchetti v3: onboarding non installa pacchetti legacy
        if not _is_v3_package(pkg_manifest):
            return _simple_result(
                False,
                error=f"Package '{package_id}' is legacy (v2); skipped in onboarding.",
            )

        pkg_version = str(pkg_manifest.get("version", pkg.get("latest_version", "unknown"))).strip()
        min_engine_version = str(pkg_manifest.get("min_engine_version", "")).strip()
        dependencies: list[str] = [
            str(d).strip() if isinstance(d, str) else str(d.get("id", "")).strip()
            for d in pkg_manifest.get("dependencies", [])
            if d
        ]

        return await self._install_package_v3(
            package_id=package_id,
            pkg=pkg,
            pkg_manifest=pkg_manifest,
            pkg_version=pkg_version,
            min_engine_version=min_engine_version,
            dependencies=dependencies,
            conflict_mode="abort",
            build_install_result=_simple_result,
        )

    # ------------------------------------------------------------------
    # v3 lifecycle methods (install / update / remove store-based)
    # ------------------------------------------------------------------

    # _v3_runtime_state, _is_github_write_authorized_v3, _v3_repopulate_registry
    # _install_workspace_files_v3, _remove_workspace_files_v3
    # _install_package_v3, _remove_package_v3, _update_package_v3
    # → moved to spark.boot.lifecycle._V3LifecycleMixin

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

        # D.1: _ff_to_dict importata da tools_resources.py.
        _ff_to_dict = _ff_to_dict_mod

        # ------------------------------------------------------------------
        # v3.0 Override tools + Resource tools — estratti in moduli factory (D.1/D.2)
        # ------------------------------------------------------------------

        # D.1: i 13 tool risorse sono registrati dalla factory in tools_resources.py.
        register_resource_tools(
            inventory=inventory,
            engine_root=self._ctx.engine_root,
            mcp=self._mcp,
            tool_names=tool_names,
        )

        # D.2: i 3 tool override sono registrati dalla factory in tools_override.py.
        register_override_tools(
            inventory=inventory,
            ctx=self._ctx,
            mcp=self._mcp,
            tool_names=tool_names,
        )

        # D.0: inizializza oggetti runtime come instance attrs e crea alias locali
        # per mantenere le closure dei tool invariate.
        self._init_runtime_objects()
        manifest = self._manifest
        registry = self._registry_client
        merge_engine = self._merge_engine
        snapshots = self._snapshots
        sessions = self._sessions
        assert manifest is not None  # noqa: S101 — garantito da _init_runtime_objects
        assert registry is not None  # noqa: S101
        assert merge_engine is not None  # noqa: S101
        assert snapshots is not None  # noqa: S101
        assert sessions is not None  # noqa: S101
        # D.4: i 9 tool policy sono registrati dalla factory in tools_policy.py.
        register_policy_tools(self, self._mcp, tool_names)

        # D.5: i 15 tool packages sono registrati dalla factory in tools_packages.py.
        register_package_tools(self, self._mcp, tool_names)
        # D.3: i 4 tool bootstrap sono registrati dopo packages (dipendono da _install_package_tool_fn).
        register_bootstrap_tools(self, self._mcp, tool_names)

        _log.info("[SPARK-ENGINE][INFO] Tools registrati: %d", len(tool_names))


