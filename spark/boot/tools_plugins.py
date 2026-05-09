"""Plugin tools factory — Step 2 Full Decoupling + Dual-Mode Architecture.

Registers 7 MCP tools:
  scf_plugin_install, scf_plugin_remove, scf_plugin_update, scf_plugin_list,
    scf_get_plugin_info, scf_list_plugins, scf_install_plugin.

I primi 4 tool delegano a ``PluginManagerFacade`` (store-based, Universo A).
``scf_get_plugin_info`` legge i metadati plugin dal registry e dal manifest remoto.
Gli ultimi 2 tool sono compat legacy verso ``PluginManager`` / ``download_plugin``
(download diretto senza store, TASK-4 Dual-Mode Architecture v1.0).

Tutti i tool accettano ``workspace_root: str`` per consentire operazioni
su workspace arbitrari (utile in ambienti multi-root).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from spark.core.constants import ENGINE_VERSION
from spark.core.utils import _is_engine_version_compatible, _normalize_string_list
from spark.packages import _get_registry_min_engine_version, _resolve_package_version
from spark.plugins import PluginManagerFacade
from spark.plugins.manager import download_plugin, list_available_plugins
from spark.plugins.schema import (
    PluginInstallError,
    PluginNotFoundError,
    PluginNotInstalledError,
)
from spark.registry.client import RegistryClient

_log = logging.getLogger("spark-framework-engine")

__all__ = ["register_plugin_tools"]

# Marker uniforme per i tool legacy (TASK-4 Dual-Mode v1.0).
# Esposto a Copilot via campi ``deprecated`` + ``deprecation_notice`` +
# ``removal_target_version`` + ``migrate_to`` nei payload JSON dei tool
# ``scf_list_plugins`` e ``scf_install_plugin`` per pilotarne l'uso solo
# in workflow di compat (no tracking nello store).
# TODO: centralizzare in spark/boot/_legacy_markers.py se altri tool
# diventano legacy in moduli diversi (oggi: 2 tool in 1 solo modulo).
_LEGACY_DEPRECATION_NOTICE: str = (
    "Tool legacy senza tracking nello store. Preferire i tool store-based: "
    "'scf_plugin_list' (al posto di 'scf_list_plugins') e "
    "'scf_plugin_install' (al posto di 'scf_install_plugin'). "
    "Rimozione pianificata in engine 3.4.0 (due minor release dopo 3.2.0)."
)

# Versione engine in cui i tool legacy verranno rimossi (R3 — DualUniverse).
# Politica: due minor release dopo l'introduzione del marker deprecated.
_LEGACY_REMOVAL_TARGET_VERSION: str = "3.4.0"

# Mappa esplicita tool legacy -> tool store-based equivalente, esposta
# nei payload come campo ``migrate_to`` per indirizzare i client MCP.
_LEGACY_MIGRATION_MAP: dict[str, str] = {
    "scf_list_plugins": "scf_plugin_list",
    "scf_install_plugin": "scf_plugin_install",
}


# ---------------------------------------------------------------------------
# Helper privato: costruisce il facade per il workspace richiesto
# ---------------------------------------------------------------------------


def _make_facade(workspace_root_str: str, fallback: Path) -> PluginManagerFacade:
    """Istanzia PluginManagerFacade con il workspace_root corretto.

    Args:
        workspace_root_str: Stringa del path workspace ricevuta dal client MCP.
            Se vuota o non valida, viene usato il ``fallback``.
        fallback: Path di fallback (di solito ``engine._ctx.workspace_root``).

    Returns:
        PluginManagerFacade istanziato per il workspace richiesto.
    """
    workspace = Path(workspace_root_str).resolve() if workspace_root_str.strip() else fallback
    return PluginManagerFacade(workspace_root=workspace)


def _make_registry_client(engine: Any, github_root: Path) -> Any:
    """Return the engine registry client or create a fallback client."""
    return engine._registry_client if engine._registry_client is not None else RegistryClient(github_root)


def _get_direct_plugin_entries(registry_client: Any) -> list[dict[str, Any]]:
    """Return registry entries available for direct plugin workflows."""
    return list_available_plugins(registry_client)


def _build_plugin_info_payload(plugin_id: str, registry_client: Any) -> dict[str, Any]:
    """Build a public detail payload for one plugin registry entry."""
    plugins = _get_direct_plugin_entries(registry_client)
    plugin = next(
        (entry for entry in plugins if str(entry.get("id", "")).strip() == plugin_id),
        None,
    )
    if plugin is None:
        return {
            "success": False,
            "status": "error",
            "plugin_id": plugin_id,
            "error": f"Plugin '{plugin_id}' not found in registry.",
            "available": [entry.get("id") for entry in plugins],
        }

    repo_url = str(plugin.get("repo_url", "")).strip()
    try:
        plugin_manifest = registry_client.fetch_package_manifest(repo_url)
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "status": "error",
            "plugin_id": plugin_id,
            "error": f"Cannot fetch plugin manifest: {exc}",
            "plugin": plugin,
        }

    raw_plugin_files = plugin_manifest.get("plugin_files", [])
    plugin_files = raw_plugin_files if isinstance(raw_plugin_files, list) else []
    min_engine_version = str(
        plugin_manifest.get("min_engine_version", _get_registry_min_engine_version(plugin))
    ).strip()
    version = _resolve_package_version(
        plugin_manifest.get("version", ""),
        plugin.get("latest_version", ""),
    )
    name = str(
        plugin_manifest.get("display_name")
        or plugin_manifest.get("name")
        or plugin.get("name")
        or plugin_manifest.get("package")
        or plugin_id
    ).strip()
    description = str(
        plugin_manifest.get("description") or plugin.get("description", "")
    ).strip()

    return {
        "success": True,
        "status": "ok",
        "plugin_id": plugin_id,
        "name": name,
        "description": description,
        "version": version,
        "dependencies": _normalize_string_list(plugin_manifest.get("dependencies", [])),
        "source_url": repo_url,
        "min_engine_version": min_engine_version,
        "engine_version": ENGINE_VERSION,
        "engine_compatible": _is_engine_version_compatible(
            ENGINE_VERSION,
            min_engine_version,
        ),
        "delivery_mode": str(plugin.get("delivery_mode", "managed")).strip() or "managed",
        "plugin_files": plugin_files,
    }


def register_plugin_tools(engine: Any, mcp: Any, tool_names: list[str]) -> None:
    """Register plugin lifecycle and compatibility tools into mcp.

    Ogni tool è una thin-wrapper verso ``PluginManagerFacade``:
    - Converte ``workspace_root: str`` → ``Path``
    - Chiama il metodo facade corrispondente
    - Normalizza il dict di ritorno al formato ``{status, ...}``
    - Logga su stderr con livello INFO

    Args:
        engine: SparkFrameworkEngine instance (deve avere ``_ctx`` inizializzato).
        mcp: FastMCP instance.
        tool_names: Lista condivisa a cui vengono aggiunti i nomi tool alla
            registrazione. Necessaria per il contatore ``register_tools()``.
    """
    ctx = engine._ctx

    def _register_tool(name: str) -> Any:
        tool_names.append(name)
        return mcp.tool()

    @_register_tool("scf_plugin_install")
    async def scf_plugin_install(pkg_id: str, workspace_root: str = "") -> dict[str, Any]:
        """Install a plugin package from the remote SCF registry into the workspace.

        Downloads ``plugin_files`` declared in the package manifest from the GitHub
        source repo and writes them under ``.github/`` in the target workspace.
        Registers the plugin in ``.github/.spark-plugins`` for future management.

        Args:
            pkg_id: Identifier of the package to install (e.g. ``scf-master-codecrafter``).
            workspace_root: Absolute path to the target workspace root. Defaults to
                the engine's active workspace if empty.

        Returns:
            A dict with keys:
              - ``status``: ``"ok"`` or ``"error"``
              - ``pkg_id``: Package identifier echoed back
              - ``version``: Installed version (on success)
              - ``files_installed``: List of files written (on success)
              - ``message``: Human-readable summary or error description
        """
        _log.info("[SPARK-ENGINE][INFO] scf_plugin_install: start pkg_id=%s", pkg_id)
        try:
            facade = _make_facade(workspace_root, ctx.workspace_root)
            result = facade.install(pkg_id)
        except Exception as exc:  # noqa: BLE001
            _log.error("[SPARK-ENGINE][ERROR] scf_plugin_install(%s): %s", pkg_id, exc)
            return {
                "status": "error",
                "pkg_id": pkg_id,
                "message": str(exc),
            }

        if result.get("success"):
            _log.info("[SPARK-ENGINE][INFO] scf_plugin_install: done pkg_id=%s version=%s", pkg_id, result.get("version"))
            return {
                "status": "ok",
                "pkg_id": pkg_id,
                "version": result.get("version", ""),
                "files_installed": result.get("installed", []),
                "message": f"Plugin '{pkg_id}' installato con successo.",
            }
        else:
            _log.error("[SPARK-ENGINE][ERROR] scf_plugin_install(%s): %s", pkg_id, result.get("error"))
            return {
                "status": "error",
                "pkg_id": pkg_id,
                "message": result.get("error", "Installazione fallita."),
                "failed_files": result.get("failed_files", []),
            }

    @_register_tool("scf_plugin_remove")
    async def scf_plugin_remove(pkg_id: str, workspace_root: str = "") -> dict[str, Any]:
        """Remove an installed plugin package from the workspace.

        Deletes all plugin files that have not been user-modified, removes the
        ``#file:`` reference from ``copilot-instructions.md`` and deregisters the
        plugin from ``.github/.spark-plugins``.

        Args:
            pkg_id: Identifier of the installed plugin to remove.
            workspace_root: Absolute path to the target workspace root. Defaults to
                the engine's active workspace if empty.

        Returns:
            A dict with keys:
              - ``status``: ``"ok"`` or ``"error"``
              - ``pkg_id``: Package identifier echoed back
              - ``files_removed``: List of removed files (on success)
              - ``message``: Human-readable summary or error description
        """
        _log.info("[SPARK-ENGINE][INFO] scf_plugin_remove: start pkg_id=%s", pkg_id)
        try:
            facade = _make_facade(workspace_root, ctx.workspace_root)
            result = facade.remove(pkg_id)
        except Exception as exc:  # noqa: BLE001
            _log.error("[SPARK-ENGINE][ERROR] scf_plugin_remove(%s): %s", pkg_id, exc)
            return {
                "status": "error",
                "pkg_id": pkg_id,
                "message": str(exc),
            }

        if result.get("success"):
            _log.info("[SPARK-ENGINE][INFO] scf_plugin_remove: done pkg_id=%s", pkg_id)
            return {
                "status": "ok",
                "pkg_id": pkg_id,
                "files_removed": result.get("removed", []),
                "message": f"Plugin '{pkg_id}' rimosso con successo.",
            }
        else:
            _log.error("[SPARK-ENGINE][ERROR] scf_plugin_remove(%s): %s", pkg_id, result.get("error"))
            return {
                "status": "error",
                "pkg_id": pkg_id,
                "message": result.get("error", "Rimozione fallita."),
            }

    @_register_tool("scf_plugin_update")
    async def scf_plugin_update(pkg_id: str, workspace_root: str = "") -> dict[str, Any]:
        """Update an installed plugin package to the latest available version.

        Performs a remove → re-install cycle using the new version from the
        remote registry. Preserves user-modified files.

        Args:
            pkg_id: Identifier of the installed plugin to update.
            workspace_root: Absolute path to the target workspace root. Defaults to
                the engine's active workspace if empty.

        Returns:
            A dict with keys:
              - ``status``: ``"ok"`` or ``"error"``
              - ``pkg_id``: Package identifier echoed back
              - ``old_version``: Previous version (on success)
              - ``new_version``: Updated version (on success)
              - ``message``: Human-readable summary or error description
        """
        _log.info("[SPARK-ENGINE][INFO] scf_plugin_update: start pkg_id=%s", pkg_id)
        try:
            facade = _make_facade(workspace_root, ctx.workspace_root)
            result = facade.update(pkg_id)
        except Exception as exc:  # noqa: BLE001
            _log.error("[SPARK-ENGINE][ERROR] scf_plugin_update(%s): %s", pkg_id, exc)
            return {
                "status": "error",
                "pkg_id": pkg_id,
                "message": str(exc),
            }

        if result.get("success"):
            _log.info(
                "[SPARK-ENGINE][INFO] scf_plugin_update: done pkg_id=%s %s->%s",
                pkg_id,
                result.get("version_from", ""),
                result.get("version_to", ""),
            )
            return {
                "status": "ok",
                "pkg_id": pkg_id,
                "old_version": result.get("version_from", ""),
                "new_version": result.get("version_to", ""),
                "message": f"Plugin '{pkg_id}' aggiornato con successo.",
            }
        else:
            _log.error("[SPARK-ENGINE][ERROR] scf_plugin_update(%s): %s", pkg_id, result.get("error"))
            return {
                "status": "error",
                "pkg_id": pkg_id,
                "message": result.get("error", "Aggiornamento fallito."),
            }

    @_register_tool("scf_plugin_list")
    async def scf_plugin_list(workspace_root: str = "") -> dict[str, Any]:
        """List installed plugins and packages available in the remote registry.

        Combines ``list_installed()`` (local ``.spark-plugins`` state) and
        ``list_available()`` (remote registry HTTP fetch) into a single response.
        If the remote registry is unreachable, ``available`` is set to an empty
        list and the error is reported in ``registry_error``.

        Args:
            workspace_root: Absolute path to the target workspace root. Defaults to
                the engine's active workspace if empty.

        Returns:
            A dict with keys:
              - ``status``: ``"ok"`` or ``"error"``
              - ``installed``: List of installed plugin records
              - ``available``: List of packages from remote registry (may be empty)
              - ``registry_error``: Error message if remote fetch failed (optional)
              - ``message``: Human-readable summary
        """
        _log.info("[SPARK-ENGINE][INFO] scf_plugin_list: start")
        try:
            facade = _make_facade(workspace_root, ctx.workspace_root)
            installed_result = facade.list_installed()
            installed = installed_result.get("plugins", []) if installed_result.get("success") else []

            # Prova il fetch remoto: gestisce il fallimento senza bloccare la risposta.
            available: list[dict[str, Any]] = []
            registry_error: str | None = None
            available_result = facade.list_available()
            if available_result.get("success"):
                available = available_result.get("packages", [])
            else:
                registry_error = available_result.get("error", "Fetch registry fallito.")
                _log.warning("[SPARK-ENGINE][INFO] scf_plugin_list: registry non raggiungibile: %s", registry_error)

        except Exception as exc:  # noqa: BLE001
            _log.error("[SPARK-ENGINE][ERROR] scf_plugin_list: %s", exc)
            return {
                "status": "error",
                "installed": [],
                "available": [],
                "message": str(exc),
            }

        _log.info("[SPARK-ENGINE][INFO] scf_plugin_list: done installed=%d available=%d", len(installed), len(available))
        response: dict[str, Any] = {
            "status": "ok",
            "installed": installed,
            "available": available,
            "message": f"{len(installed)} plugin installati, {len(available)} disponibili nel registry.",
        }
        if registry_error is not None:
            response["registry_error"] = registry_error
        return response

    # -----------------------------------------------------------------------
    # TASK-4 — Dual-Mode Architecture: tool per download diretto (no store)
    # -----------------------------------------------------------------------

    @_register_tool("scf_list_plugins")
    async def scf_list_plugins() -> dict[str, Any]:
        """List plugin packages available for direct download (excludes mcp_only).

        DEPRECATED: use ``scf_plugin_list`` for tracked PluginManagerFacade
        listing. This compatibility tool remains for direct-download legacy
        workflows and will be removed after the documented migration window.

        Returns the list of packages from the remote SCF registry that can be
        downloaded directly into the workspace ```.github/`` directory without
        passing through the engine's internal store.

        Packages with ``delivery_mode == "mcp_only"`` are excluded: those are
        served via MCP from the engine store and do not need to be downloaded.

        Returns:
            A dict with keys:
              - ``status``: ``"ok"`` or ``"error"``
              - ``plugins``: List of package dicts from the remote registry
              - ``count``: Number of available packages
              - ``message``: Human-readable summary
        """
        _log.info("[SPARK-ENGINE][INFO] scf_list_plugins: start")
        try:
            registry_client = _make_registry_client(engine, ctx.github_root)
            plugins = _get_direct_plugin_entries(registry_client)
        except Exception as exc:  # noqa: BLE001
            _log.error("[SPARK-ENGINE][ERROR] scf_list_plugins: %s", exc)
            return {
                "status": "error",
                "plugins": [],
                "count": 0,
                "deprecated": True,
                "deprecation_notice": _LEGACY_DEPRECATION_NOTICE,
                "removal_target_version": _LEGACY_REMOVAL_TARGET_VERSION,
                "migrate_to": _LEGACY_MIGRATION_MAP["scf_list_plugins"],
                "message": str(exc),
            }
        _log.info("[SPARK-ENGINE][INFO] scf_list_plugins: done count=%d", len(plugins))
        return {
            "status": "ok",
            "plugins": plugins,
            "count": len(plugins),
            "deprecated": True,
            "deprecation_notice": _LEGACY_DEPRECATION_NOTICE,
            "removal_target_version": _LEGACY_REMOVAL_TARGET_VERSION,
            "migrate_to": _LEGACY_MIGRATION_MAP["scf_list_plugins"],
            "message": f"{len(plugins)} plugin disponibili per il download diretto.",
        }

    @_register_tool("scf_get_plugin_info")
    async def scf_get_plugin_info(plugin_id: str) -> dict[str, Any]:
        """Restituisce i dettagli di un singolo plugin Dual-Mode per ID.

        Args:
            plugin_id: Identificatore univoco del plugin nel registry.

        Returns:
            Dict con name, description, version, dependencies, source_url,
            min_engine_version. Chiave 'error' presente se plugin non trovato.

        Raises:
            Nessuna eccezione diretta. Errori restituiti come MCP error response.
        """
        _log.info("[SPARK-ENGINE][INFO] scf_get_plugin_info: %s", plugin_id)
        try:
            registry_client = _make_registry_client(engine, ctx.github_root)
            return _build_plugin_info_payload(plugin_id, registry_client)
        except Exception as exc:  # noqa: BLE001
            _log.error("[SPARK-ENGINE][ERROR] scf_get_plugin_info(%s): %s", plugin_id, exc)
            return {
                "success": False,
                "status": "error",
                "plugin_id": plugin_id,
                "error": str(exc),
            }

    @_register_tool("scf_install_plugin")
    async def scf_install_plugin(
        package_id: str,
        version: str = "latest",
        workspace_root: str = "",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Download a plugin directly into the workspace .github/ directory.

        DEPRECATED: use ``scf_plugin_install`` for tracked PluginManagerFacade
        installation. This compatibility tool remains for direct-download legacy
        workflows and will be removed after the documented migration window.

        Downloads ``plugin_files`` declared in the package manifest from the
        GitHub source repo into ``target_workspace/.github/`` without registering
        anything in the engine's internal store or ``.github/.spark-plugins``.

        The user owns the downloaded files. The engine does not track them.

        Args:
            package_id: Identifier of the plugin to download.
            version: Version to download. Use ``"latest"`` for the most recent.
            workspace_root: Absolute path to the target workspace root. Defaults to
                the engine's active workspace if empty.
            overwrite: If ``True``, overwrite existing files. Default ``False``.

        Returns:
            A dict with keys:
              - ``status``: ``"ok"`` or ``"error"``
              - ``package_id``: Package identifier echoed back
              - ``version``: Version effectively downloaded
              - ``files_written``: List of files written
              - ``files_skipped``: List of files skipped (already exist)
              - ``errors``: List of errors encountered
              - ``message``: Human-readable summary
        """
        _log.info("[SPARK-ENGINE][INFO] scf_install_plugin: start package_id=%s version=%s", package_id, version)
        target = Path(workspace_root).resolve() if workspace_root.strip() else ctx.workspace_root
        try:
            registry_client = _make_registry_client(engine, ctx.github_root)
            result = download_plugin(
                package_id=package_id,
                version=version,
                target_dir=target,
                registry_client=registry_client,
                overwrite=overwrite,
            )
        except Exception as exc:  # noqa: BLE001
            _log.error("[SPARK-ENGINE][ERROR] scf_install_plugin(%s): %s", package_id, exc)
            return {
                "status": "error",
                "package_id": package_id,
                "version": version,
                "files_written": [],
                "files_skipped": [],
                "errors": [str(exc)],
                "deprecated": True,
                "deprecation_notice": _LEGACY_DEPRECATION_NOTICE,
                "removal_target_version": _LEGACY_REMOVAL_TARGET_VERSION,
                "migrate_to": _LEGACY_MIGRATION_MAP["scf_install_plugin"],
                "message": str(exc),
            }

        status = "ok" if result.get("success") else "error"
        written = result.get("files_written", [])
        skipped = result.get("files_skipped", [])
        errors = result.get("errors", [])
        effective_version = result.get("version", version)

        _log.info(
            "[SPARK-ENGINE][INFO] scf_install_plugin: done package_id=%s version=%s written=%d",
            package_id,
            effective_version,
            len(written),
        )
        return {
            "status": status,
            "package_id": package_id,
            "version": effective_version,
            "files_written": written,
            "files_skipped": skipped,
            "errors": errors,
            "deprecated": True,
            "deprecation_notice": _LEGACY_DEPRECATION_NOTICE,
            "removal_target_version": _LEGACY_REMOVAL_TARGET_VERSION,
            "migrate_to": _LEGACY_MIGRATION_MAP["scf_install_plugin"],
            "message": (
                f"Plugin '{package_id}' v{effective_version}: "
                f"{len(written)} file scritti, {len(skipped)} saltati."
                if status == "ok"
                else f"Errore: {'; '.join(errors)}"
            ),
        }
