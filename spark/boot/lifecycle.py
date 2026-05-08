"""_V3LifecycleMixin — estratto da spark.boot.engine (Phase 0, Task 2).

Contiene gli 8 metodi v3 di SparkFrameworkEngine che gestiscono il ciclo
install/update/remove dello store locale e i workspace_files (Cat. A).
Estratti come mixin per ridurre le dimensioni di engine.py mantenendo
completa compatibilità con i test e il runtime.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spark.core.constants import ENGINE_VERSION, _RESOURCE_TYPES
from spark.core.utils import _sha256_text
from spark.inventory import EngineInventory
from spark.manifest import ManifestManager, WorkspaceWriteGateway
from spark.packages import (
    _install_package_v3_into_store,
    _list_orphan_overrides_for_package,
    _remove_package_v3_from_store,
    _v3_overrides_blocking_update,
)
from spark.registry import (
    McpResourceRegistry,
    PackageResourceStore,
    RegistryClient,
    _v3_store_sentinel_file,
)
from spark.assets import _apply_phase6_assets

_log: logging.Logger = logging.getLogger("spark-framework-engine")


def _collect_mcp_service_uris(pkg_manifest: Mapping[str, Any]) -> list[str]:
    """Return MCP resource URIs activated by a package manifest."""
    resources = pkg_manifest.get("mcp_resources") or {}
    if not isinstance(resources, Mapping):
        return []
    uris: list[str] = []
    for resource_type in _RESOURCE_TYPES:
        names = resources.get(resource_type) or []
        if not isinstance(names, list):
            continue
        for name in names:
            uris.append(McpResourceRegistry.make_uri(resource_type, str(name)))
    return sorted(uris)


def _dedupe_preserving_order(items: list[str]) -> list[str]:
    """Return items without duplicates while preserving first-seen order."""
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


class _V3LifecycleMixin:
    """Mixin: metodi v3 del ciclo di vita per SparkFrameworkEngine.

    Presuppone che ``self`` sia un'istanza di ``SparkFrameworkEngine`` con
    gli attributi ``_ctx``, ``_inventory`` e ``_runtime_dir`` già inizializzati
    dall'``__init__`` di ``SparkFrameworkEngine``.
    """

    def _v3_runtime_state(self) -> tuple[ManifestManager, McpResourceRegistry, Path]:
        """Comodità: ritorna (manifest, registry, engine_root) del contesto attivo."""
        manifest = ManifestManager(self._ctx.github_root)  # type: ignore[attr-defined]
        registry = self._inventory.mcp_registry  # type: ignore[attr-defined]
        if registry is None:
            registry = self._inventory.populate_mcp_registry(  # type: ignore[attr-defined]
                EngineInventory(engine_root=self._ctx.engine_root).engine_manifest, {}  # type: ignore[attr-defined]
            )
        return manifest, registry, self._ctx.engine_root  # type: ignore[attr-defined]

    def _is_github_write_authorized_v3(self) -> bool:
        """Legge ``github_write_authorized`` dallo state file dell'orchestrator.

        Wrapper minimale per i metodi v3 che vivono fuori dalla closure
        ``register_tools`` dove la stessa logica è già inline.
        """
        state_path = (
            self._ctx.github_root / "runtime" / "orchestrator-state.json"  # type: ignore[attr-defined]
        )
        if not state_path.is_file():
            return False
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return bool(payload.get("github_write_authorized", False))

    def _v3_repopulate_registry(
        self,
        freshly_installed: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Ricostruisce il registry MCP dopo install/remove/update v3.

        Args:
            freshly_installed: manifest già in memoria per i pacchetti appena
                installati, indicizzato per ``package_id``. Quando presente,
                evita la ri-lettura del file ``package-manifest.json`` dallo
                store per quei pacchetti (OPT-6).
        """
        engine_manifest = EngineInventory(engine_root=self._ctx.engine_root).engine_manifest  # type: ignore[attr-defined]
        manifest = ManifestManager(self._ctx.github_root)  # type: ignore[attr-defined]
        store = PackageResourceStore(self._ctx.engine_root)  # type: ignore[attr-defined]
        installed = manifest.get_installed_versions()
        package_manifests: dict[str, dict[str, Any]] = {}
        for pkg_id in installed:
            # OPT-6: usa il manifest già in memoria quando disponibile.
            if freshly_installed and pkg_id in freshly_installed:
                package_manifests[pkg_id] = freshly_installed[pkg_id]
                continue
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
        self._inventory.populate_mcp_registry(engine_manifest, package_manifests)  # type: ignore[attr-defined]

    def _install_workspace_files_v3(
        self,
        package_id: str,
        pkg_version: str,
        pkg_manifest: Mapping[str, Any],
        manifest: ManifestManager,
    ) -> dict[str, Any]:
        """Scrive nel workspace solo i file dichiarati in ``workspace_files``.

        Categoria A del refactoring v3: file referenziati staticamente da
        Copilot/Cline (es. ``copilot-instructions.md``, instructions globali,
        ``project-profile.md``). I file Categoria B (prompts, instructions
        operative, agents, skills) restano nello store centrale e sono
        serviti via MCP.

        Idempotente: se il file esiste già con sha identico, gateway aggiorna
        solo l'ownership nel manifest. Se l'utente ha modificato il file
        (sha mismatch su entry tracciata), viene preservato.

        Args:
            package_id: ID del pacchetto.
            pkg_version: versione installata.
            pkg_manifest: package-manifest.json (deve contenere
                opzionalmente ``workspace_files`` e ``file_policies``).
            manifest: ManifestManager attivo del workspace.

        Returns:
            ``{"success": bool, "files_written": [...], "preserved": [...],
              "errors": [...]}``. ``success=True`` anche con preserved
            non vuoti (semantica di idempotenza). ``success=False`` solo
            se sorgente mancante o write fallita.
        """
        workspace_files = pkg_manifest.get("workspace_files") or []
        if not isinstance(workspace_files, list) or not workspace_files:
            return {
                "success": True,
                "files_written": [],
                "preserved": [],
                "errors": [],
            }
        store = PackageResourceStore(self._ctx.engine_root)  # type: ignore[attr-defined]
        package_root = store.packages_root / package_id
        file_policies = pkg_manifest.get("file_policies") or {}
        if not isinstance(file_policies, dict):
            file_policies = {}
        # OPT-1: snapshot pre-caricato (usa il cache di ManifestManager se già
        # popolato dalla stessa operazione corrente). sha_map consente OPT-5
        # senza ulteriori letture disco del manifest.
        entries_snapshot = manifest.load()
        sha_map: dict[str, str] = {}
        for _e in entries_snapshot:
            _fk = str(_e.get("file", "")).strip()
            if _fk and _fk not in sha_map:
                _sha = str(_e.get("sha256", "")).strip()
                if _sha:
                    sha_map[_fk] = _sha

        preserved: list[str] = []
        errors: list[str] = []
        # OPT-2: raccolta scritture pendenti per batch post-loop.
        # Ogni entry: (original_entry, github_rel, dest_path, content, merge_strategy).
        pending_writes: list[tuple[str, str, Path, str, str | None]] = []
        for entry in workspace_files:
            if not isinstance(entry, str):
                errors.append(f"invalid workspace_files entry: {entry!r}")
                continue
            github_rel = entry.removeprefix(".github/")
            if ".." in Path(github_rel).parts:
                errors.append(f"unsafe workspace_files path: {entry}")
                continue
            source_path = package_root / entry
            if not source_path.is_file():
                errors.append(
                    f"workspace_files source missing in store: {entry}"
                )
                continue
            # Preservation gate: se il file è già presente nel workspace ed è
            # tracciato come modificato dall'utente da un altro owner,
            # non sovrascrivere.
            # NOTE: ``scf-engine-bootstrap`` viene escluso perché è un owner-shadow
            # generato da auto-bootstrap (Cat. A sentinella) e non rappresenta una
            # claim reale di pacchetto; in scenari multi-owner
            # [scf-engine-bootstrap, <pkg>] il gate scatta correttamente
            # sull'owner di pacchetto se l'utente ha modificato il file.
            existing_owners = manifest.get_file_owners(github_rel)
            other_owner_modified = any(
                owner != package_id
                and owner != "scf-engine-bootstrap"
                and manifest.is_user_modified(github_rel) is True
                for owner in existing_owners
            )
            if other_owner_modified:
                preserved.append(entry)
                continue
            try:
                content = source_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"{entry}: cannot read source ({exc})")
                continue
            policy_meta = file_policies.get(entry) or {}
            merge_strategy = (
                policy_meta.get("merge_strategy") if isinstance(policy_meta, dict) else None
            )
            dest_path = self._ctx.github_root / github_rel  # type: ignore[attr-defined]
            # OPT-5: salta la scrittura se il contenuto sorgente è identico
            # all'SHA già tracciato nel manifest e il file esiste su disco
            # (idempotenza su re-install senza variazioni di contenuto).
            # Nota: _sha256_text usa UTF-8 LF; su Windows può differire dallo
            # SHA binario CRLF — in quel caso il check non combacia e la
            # scrittura avviene normalmente (comportamento corretto e sicuro).
            if _sha256_text(content) == sha_map.get(github_rel, "") and dest_path.is_file():
                preserved.append(entry)
                continue
            pending_writes.append((entry, github_rel, dest_path, content, merge_strategy))

        # Errori di validazione pre-scrittura: restituisce subito senza toccare disco.
        if errors:
            return {
                "success": False,
                "files_written": [],
                "preserved": preserved,
                "errors": errors,
            }

        if not pending_writes:
            return {
                "success": True,
                "files_written": [],
                "preserved": preserved,
                "errors": [],
            }

        # OPT-4 + OPT-2: scritture fisiche batch + manifest.upsert_many() una sola volta.
        # Il manifest viene aggiornato solo se tutte le scritture hanno avuto successo.
        files_written: list[str] = []
        upsert_files: list[tuple[str, Path]] = []
        merge_strategies_by_file: dict[str, str] = {}
        write_errors: list[str] = []
        for entry, github_rel, dest_path, content, merge_strategy in pending_writes:
            try:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                dest_path.write_text(content, encoding="utf-8")
                upsert_files.append((github_rel, dest_path))
                if merge_strategy is not None:
                    merge_strategies_by_file[github_rel] = merge_strategy
                files_written.append(entry)
            except OSError as exc:
                write_errors.append(f"{github_rel}: write failed ({exc})")

        if write_errors:
            return {
                "success": False,
                "files_written": files_written,
                "preserved": preserved,
                "errors": write_errors,
            }

        manifest.upsert_many(
            package=package_id,
            package_version=pkg_version,
            files=upsert_files,
            merge_strategies_by_file=merge_strategies_by_file or None,
        )
        return {
            "success": True,
            "files_written": files_written,
            "preserved": preserved,
            "errors": [],
        }

    def _install_standalone_files_v3(
        self,
        package_id: str,
        pkg_version: str,
        pkg_manifest: Mapping[str, Any],
        manifest: ManifestManager,
    ) -> dict[str, Any]:
        """Copia nel workspace i file dichiarati in ``deployment_modes.standalone_files``.

        A differenza di ``_install_workspace_files_v3`` (che opera su
        ``workspace_files`` della Categoria A), questo metodo gestisce i file
        di Categoria B che il pacchetto dichiara esplicitamente come
        standalone, cioè file che devono risiedere fisicamente nel workspace
        oltre che nello store MCP centrale.

        Delega interamente a ``_install_workspace_files_v3`` usando un manifest
        sintetico che mappa ``standalone_files`` su ``workspace_files``.

        Args:
            package_id: ID del pacchetto.
            pkg_version: versione installata.
            pkg_manifest: package-manifest.json (deve contenere
                ``deployment_modes.standalone_files``).
            manifest: ManifestManager attivo del workspace.

        Returns:
            Stesso formato di ``_install_workspace_files_v3``:
            ``{"success": bool, "files_written": [...], "preserved": [...],
              "errors": [...]}``. Se ``standalone_files`` è vuoto o assente,
            ritorna success=True con tutte le liste vuote.
        """
        from spark.packages import _get_deployment_modes  # noqa: PLC0415

        modes = _get_deployment_modes(pkg_manifest)
        standalone_files = modes.get("standalone_files") or []
        plugin_files = pkg_manifest.get("plugin_files", [])
        if plugin_files is None:
            plugin_files = []
        if not isinstance(plugin_files, list):
            return {
                "success": False,
                "files_written": [],
                "standalone_files_written": [],
                "plugin_files_installed": [],
                "preserved": [],
                "standalone_files_preserved": [],
                "plugin_files_preserved": [],
                "errors": ["plugin_files must be a list when declared"],
            }
        if not standalone_files and not plugin_files:
            return {
                "success": True,
                "files_written": [],
                "standalone_files_written": [],
                "plugin_files_installed": [],
                "preserved": [],
                "standalone_files_preserved": [],
                "plugin_files_preserved": [],
                "errors": [],
            }

        file_policies = pkg_manifest.get("file_policies") or {}
        standalone_result = self._install_workspace_files_v3(
            package_id=package_id,
            pkg_version=pkg_version,
            pkg_manifest={
                "workspace_files": standalone_files,
                "file_policies": file_policies,
            },
            manifest=manifest,
        )
        plugin_result = self._install_workspace_files_v3(
            package_id=package_id,
            pkg_version=pkg_version,
            pkg_manifest={
                "workspace_files": plugin_files,
                "file_policies": file_policies,
            },
            manifest=manifest,
        )
        standalone_written = list(standalone_result.get("files_written", []) or [])
        plugin_written = list(plugin_result.get("files_written", []) or [])
        standalone_preserved = list(standalone_result.get("preserved", []) or [])
        plugin_preserved = list(plugin_result.get("preserved", []) or [])
        errors = list(standalone_result.get("errors", []) or []) + list(
            plugin_result.get("errors", []) or []
        )
        return {
            "success": bool(standalone_result.get("success"))
            and bool(plugin_result.get("success")),
            "files_written": _dedupe_preserving_order(standalone_written + plugin_written),
            "standalone_files_written": standalone_written,
            "plugin_files_installed": plugin_written,
            "preserved": _dedupe_preserving_order(standalone_preserved + plugin_preserved),
            "standalone_files_preserved": standalone_preserved,
            "plugin_files_preserved": plugin_preserved,
            "errors": errors,
        }

    def _remove_workspace_files_v3(
        self,
        package_id: str,
        pkg_manifest: Mapping[str, Any],
        manifest: ManifestManager,
    ) -> dict[str, Any]:
        """Rimuove dal workspace i file ``workspace_files`` non modificati dall'utente.

        Args:
            package_id: ID del pacchetto da rimuovere.
            pkg_manifest: package-manifest.json letto dallo store
                PRIMA della rmtree (deve contenere ``workspace_files``).
            manifest: ManifestManager attivo del workspace.

        Returns:
            ``{"removed": [...], "preserved": [...], "errors": [...]}``.
        """
        workspace_files = pkg_manifest.get("workspace_files") or []
        plugin_files = pkg_manifest.get("plugin_files", [])
        if plugin_files is None:
            plugin_files = []
        if isinstance(workspace_files, list) and isinstance(plugin_files, list):
            workspace_files = _dedupe_preserving_order(workspace_files + plugin_files)
        if not isinstance(workspace_files, list) or not workspace_files:
            return {"removed": [], "preserved": [], "errors": []}
        gateway = WorkspaceWriteGateway(self._ctx.workspace_root, manifest)  # type: ignore[attr-defined]
        removed: list[str] = []
        preserved: list[str] = []
        errors: list[str] = []
        for entry in workspace_files:
            if not isinstance(entry, str):
                continue
            github_rel = entry.removeprefix(".github/")
            target = self._ctx.github_root / github_rel  # type: ignore[attr-defined]
            if not target.is_file():
                continue
            owners = manifest.get_file_owners(github_rel)
            # Non toccare se l'unica ownership tracciata è di un altro pacchetto.
            non_package_owners = [o for o in owners if o != package_id]
            if non_package_owners and package_id not in owners:
                preserved.append(entry)
                continue
            # File non tracciato nel manifest: preserva per sicurezza e logga warning.
            if not owners:
                _log.warning(
                    "[SPARK-ENGINE][WARNING] _remove_workspace_files_v3: "
                    "file %s non tracciato nel manifest, preservato per sicurezza.",
                    entry,
                )
                preserved.append(entry)
                continue
            # Preservazione user-modified.
            if manifest.is_user_modified(github_rel) is True:
                preserved.append(entry)
                continue
            try:
                gateway.delete(github_rel, package_id)
                removed.append(entry)
            except OSError as exc:
                errors.append(f"{entry}: delete failed ({exc})")
        return {"removed": removed, "preserved": preserved, "errors": errors}

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
                mcp_services_activated=_collect_mcp_service_uris(pkg_manifest),
                workspace_files_written=[],
                workspace_files_preserved=[],
                plugin_files_installed=[],
                plugin_files_preserved=[],
                installed=[],
                _deprecated_note=(
                    "Use workspace_files_written and plugin_files_installed instead"
                ),
                idempotent=True,
                message=f"Package {package_id}@{pkg_version} already installed.",
            )

        # Scarichiamo i file nello store. In caso di errore non scriviamo nulla.
        store_result = _install_package_v3_into_store(
            engine_root=engine_root,
            package_id=package_id,
            pkg=pkg,
            pkg_manifest=pkg_manifest,
            fetch_raw_file=RegistryClient(self._ctx.github_root).fetch_raw_file,  # type: ignore[attr-defined]
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

        # v3 FIX 3 — scriviamo i workspace_files (Cat. A) nel workspace
        # utente. Categoria B (prompts/agents/skills/instructions operative)
        # resta nello store ed è servita via MCP.
        ws_result = self._install_workspace_files_v3(
            package_id=package_id,
            pkg_version=pkg_version,
            pkg_manifest=pkg_manifest,
            manifest=manifest,
        )
        if not ws_result["success"]:
            # Compensazione: rollback dello store per coerenza.
            _log.warning(
                "[SPARK-ENGINE][WARNING] workspace_files write failed for %s: %s",
                package_id,
                "; ".join(ws_result["errors"]),
            )
            try:
                _remove_package_v3_from_store(engine_root, package_id)
            except OSError as exc:
                _log.warning(
                    "[SPARK-ENGINE][WARNING] Rollback store failed for %s: %s",
                    package_id,
                    exc,
                )
            # Ripristina manifest senza la sentinella appena aggiunta.
            manifest.save(existing_entries)
            return build_install_result(
                False,
                error="Cannot write workspace_files: " + "; ".join(ws_result["errors"]),
                package=package_id,
                version=pkg_version,
                installation_mode="v3_store",
                store_path=store_result["store_path"],
            )

        # Re-popoliamo il registry MCP per esporre subito le risorse
        # del pacchetto appena installato (idempotente).
        # OPT-6: passa il manifest già in memoria per evitare una ri-lettura disco.
        self._v3_repopulate_registry(freshly_installed={package_id: dict(pkg_manifest)})

        # Rigeneriamo gli asset Phase 6 (AGENTS.md, AGENTS-{pkg}.md, ecc.).
        try:
            installed_ids = list(manifest.get_installed_versions().keys())
            _phase6_gateway = WorkspaceWriteGateway(self._ctx.workspace_root, manifest)  # type: ignore[attr-defined]
            phase6_report = _apply_phase6_assets(
                self._ctx.workspace_root,  # type: ignore[attr-defined]
                self._ctx.engine_root,  # type: ignore[attr-defined]
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
            mcp_services_activated=_collect_mcp_service_uris(pkg_manifest),
            workspace_files_written=ws_result["files_written"],
            workspace_files_preserved=ws_result["preserved"],
            plugin_files_installed=[],
            plugin_files_preserved=[],
            installed=list(ws_result["files_written"]),
            _deprecated_note="Use workspace_files_written and plugin_files_installed instead",
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
        # Guard canonico: garantisce che il registry sia inizializzato prima dell'uso.
        if self._inventory.mcp_registry is None:  # type: ignore[attr-defined]
            self._v3_repopulate_registry()
        registry = self._inventory.mcp_registry  # type: ignore[attr-defined]
        # Lista override orfani PRIMA di toccare il registry.
        orphan_overrides = _list_orphan_overrides_for_package(registry, package_id)

        # v3 FIX 5 — leggi pkg_manifest dallo store PRIMA della rmtree per
        # poter rimuovere i workspace_files (Cat. A) dal workspace utente.
        store = PackageResourceStore(self._ctx.engine_root)  # type: ignore[attr-defined]
        pkg_manifest_path = store.packages_root / package_id / "package-manifest.json"
        pkg_manifest_for_cleanup: dict[str, Any] = {}
        if pkg_manifest_path.is_file():
            try:
                pkg_manifest_for_cleanup = json.loads(
                    pkg_manifest_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError) as exc:
                _log.warning(
                    "[SPARK-ENGINE][WARNING] Cannot read store manifest "
                    "for cleanup of %s: %s",
                    package_id,
                    exc,
                )
        ws_cleanup = self._remove_workspace_files_v3(
            package_id=package_id,
            pkg_manifest=pkg_manifest_for_cleanup,
            manifest=manifest,
        )

        # Rimuoviamo dallo store fisico.
        store_result = _remove_package_v3_from_store(self._ctx.engine_root, package_id)  # type: ignore[attr-defined]

        # Rimuoviamo manualmente la sola entry v3 dal manifest.
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
            _phase6_gateway = WorkspaceWriteGateway(self._ctx.workspace_root, manifest)  # type: ignore[attr-defined]
            phase6_report = _apply_phase6_assets(
                self._ctx.workspace_root,  # type: ignore[attr-defined]
                self._ctx.engine_root,  # type: ignore[attr-defined]
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
            "workspace_files_removed": ws_cleanup["removed"],
            "workspace_files_preserved": ws_cleanup["preserved"],
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
        # Re-popoliamo per allineare il registry con eventuali override
        # workspace creati dopo l'install.
        self._v3_repopulate_registry()
        # Guard canonico: accediamo al registry dopo la repopulate.
        if self._inventory.mcp_registry is None:  # type: ignore[attr-defined]
            self._v3_repopulate_registry()
        registry = self._inventory.mcp_registry  # type: ignore[attr-defined]
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
