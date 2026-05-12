"""Plugin tools factory — Step 2 Full Decoupling + Dual-Mode Architecture.

Registers 9 MCP tools:
  scf_plugin_install, scf_plugin_remove, scf_plugin_update, scf_plugin_list,
    scf_get_plugin_info, scf_plugin_list_remote, scf_plugin_install_remote,
    scf_list_plugins, scf_install_plugin.

I primi 4 tool delegano a ``PluginManagerFacade`` (store-based, Universo A).
``scf_get_plugin_info`` legge i metadati plugin dal registry e dal manifest remoto.
``scf_plugin_list_remote`` e ``scf_plugin_install_remote`` sono U2 direct-download
con TTL cache (1h) via ``tools_registry_client`` helpers.
Gli ultimi 2 tool sono compat legacy verso ``PluginManager`` / ``download_plugin``
(download diretto senza store, TASK-4 Dual-Mode Architecture v1.0).

Tutti i tool accettano ``workspace_root: str`` per consentire operazioni
su workspace arbitrari (utile in ambienti multi-root).
"""
from __future__ import annotations

import logging
from pathlib import Path, PureWindowsPath
from typing import Any

import urllib.error
import urllib.request

from spark.boot.tools_registry_client import find_remote_package
from spark.core.constants import ENGINE_VERSION, _REGISTRY_URL
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
    engine_client = getattr(engine, "_registry_client", None)
    if engine_client is None:
        return RegistryClient(github_root)

    client_root = getattr(engine_client, "_github_root", github_root)
    try:
        same_root = Path(client_root).resolve() == github_root.resolve()
    except (OSError, RuntimeError, TypeError, ValueError):
        same_root = client_root == github_root
    if same_root:
        return engine_client

    registry_url = getattr(engine_client, "_registry_url", _REGISTRY_URL)
    return RegistryClient(github_root, registry_url=registry_url)


def _resolve_safe_github_destination(github_root: Path, file_path: str) -> Path | None:
    """Return a safe destination inside .github/, or None for unsafe paths."""
    github_rel = file_path.removeprefix(".github/").replace("\\", "/").strip()
    if not github_rel or github_rel in {".", "/"}:
        return None

    rel_path = Path(github_rel)
    if rel_path.is_absolute() or PureWindowsPath(github_rel).is_absolute():
        return None
    if ".." in rel_path.parts:
        return None

    dest = (github_root / rel_path).resolve()
    try:
        dest.relative_to(github_root.resolve())
    except ValueError:
        return None
    return dest


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
    # U2 Remote Registry: elenco diretto da scf-registry con TTL cache
    # -----------------------------------------------------------------------

    @_register_tool("scf_plugin_list_remote")
    async def scf_plugin_list_remote(force_refresh: bool = False) -> dict[str, Any]:
        """List packages available in the remote SCF registry (Universe U2).

        Uses a TTL-based cache (1h) to avoid unnecessary GitHub requests.
        Each entry is annotated with ``universe`` and ``delivery_mode``.
        Packages with ``delivery_mode == "mcp_only"`` are Universe U1 (served
        locally by the engine); all others are Universe U2 (installable from
        remote).

        Args:
            force_refresh: If True, bypass the TTL cache and fetch fresh data.

        Returns:
            A dict with keys:
              - ``status``: ``"ok"`` or ``"error"``
              - ``packages``: Annotated list of packages with ``universe`` field
              - ``u1_count``: Count of mcp_only (U1) packages in registry
              - ``u2_count``: Count of installable (U2) packages in registry
              - ``from_cache``: True if data was served from local cache before any refresh
              - ``cache_age_seconds``: Age of the local cache file after the operation
              - ``message``: Human-readable summary
        """
        _log.info("[SPARK-ENGINE][INFO] scf_plugin_list_remote: start force_refresh=%s", force_refresh)
        try:
            registry_client = _make_registry_client(engine, ctx.github_root)
            ttl = 0 if force_refresh else 3600
            cache_fresh_before_fetch = False if force_refresh else registry_client.is_cache_fresh(ttl)
            try:
                data = registry_client.fetch_if_stale(ttl_seconds=ttl)
                from_cache = cache_fresh_before_fetch
                cache_age_getter = getattr(registry_client, "cache_age_seconds", None)
                cache_age_seconds = (
                    cache_age_getter() if callable(cache_age_getter) else None
                )
            except RuntimeError as exc:
                _log.warning(
                    "[SPARK-ENGINE][WARNING] scf_plugin_list_remote: registry non raggiungibile: %s", exc
                )
                return {
                    "status": "error",
                    "packages": [],
                    "u1_count": 0,
                    "u2_count": 0,
                    "from_cache": False,
                    "cache_age_seconds": None,
                    "message": f"Registry non raggiungibile: {exc}",
                }

            raw_packages: list[dict[str, Any]] = data.get("packages", [])
            annotated: list[dict[str, Any]] = []
            u1_count = 0
            u2_count = 0
            for pkg in raw_packages:
                delivery = str(pkg.get("delivery_mode", "managed")).strip()
                if delivery == "mcp_only":
                    universe = "U1"
                    u1_count += 1
                else:
                    universe = "U2"
                    u2_count += 1
                annotated.append({**pkg, "universe": universe, "delivery_mode": delivery})

        except Exception as exc:  # noqa: BLE001
            _log.error("[SPARK-ENGINE][ERROR] scf_plugin_list_remote: %s", exc)
            return {
                "status": "error",
                "packages": [],
                "u1_count": 0,
                "u2_count": 0,
                "from_cache": False,
                "cache_age_seconds": None,
                "message": str(exc),
            }

        _log.info(
            "[SPARK-ENGINE][INFO] scf_plugin_list_remote: done total=%d u1=%d u2=%d from_cache=%s",
            len(annotated), u1_count, u2_count, from_cache,
        )
        return {
            "status": "ok",
            "packages": annotated,
            "u1_count": u1_count,
            "u2_count": u2_count,
            "from_cache": from_cache,
            "cache_age_seconds": cache_age_seconds,
            "message": (
                f"{len(annotated)} pacchetti nel registry "
                f"({u1_count} U1 mcp_only, {u2_count} U2 installabili)."
            ),
        }

    # -----------------------------------------------------------------------
    # U2 Remote Install: download diretto HTTPS con TTL cache
    # -----------------------------------------------------------------------

    @_register_tool("scf_plugin_install_remote")
    async def scf_plugin_install_remote(
        pkg_id: str,
        workspace_root: str = "",
        overwrite: bool = False,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Download a Universe U2 plugin directly from its GitHub source into .github/.

        Fetches the SCF registry with a 1-hour TTL cache to resolve ``pkg_id``
        to a repo URL, then downloads each file declared in ``plugin_files``
        via HTTPS into ``workspace_root/.github/``.

        Only packages with ``delivery_mode != "mcp_only"`` are supported —
        ``mcp_only`` (U1) packages are served by the engine MCP store and do
        not need to be installed in the workspace.

        This tool does **not** register anything in ``.spark-plugins`` or the
        engine manifest — the downloaded files are owned entirely by the user.
        For tracked lifecycle management, use ``scf_plugin_install`` instead.

        Args:
            pkg_id: Registry identifier of the package to install
                (e.g. ``"scf-master-codecrafter"``).
            workspace_root: Absolute path to the target workspace root. Defaults
                to the engine's active workspace if empty.
            overwrite: If True, overwrite files that already exist in .github/.
                Default False (idempotent skip).
            force_refresh: If True, bypass the TTL cache and fetch a fresh
                registry copy before resolving the package.

        Returns:
            A dict with keys:
              - ``status``: ``"ok"`` or ``"error"``
              - ``pkg_id``: Package identifier echoed back
              - ``universe``: Always ``"U2"`` on success
              - ``version``: Resolved version from registry
              - ``files_written``: List of files written to .github/
              - ``files_skipped``: List of files skipped (already exist, overwrite=False)
              - ``errors``: List of per-file error messages
              - ``message``: Human-readable summary
        """
        _log.info(
            "[SPARK-ENGINE][INFO] scf_plugin_install_remote: start pkg=%s overwrite=%s force_refresh=%s",
            pkg_id, overwrite, force_refresh,
        )
        workspace = Path(workspace_root).resolve() if workspace_root else ctx.workspace_root
        github_root = workspace / ".github"

        try:
            registry_client = _make_registry_client(engine, github_root)
            entry = find_remote_package(
                github_root=github_root,
                pkg_id=pkg_id,
                engine=engine,
                force_refresh=force_refresh,
            )
        except Exception as exc:  # noqa: BLE001
            _log.error("[SPARK-ENGINE][ERROR] scf_plugin_install_remote registry: %s", exc)
            return {
                "status": "error",
                "pkg_id": pkg_id,
                "universe": "U2",
                "version": "",
                "files_written": [],
                "files_skipped": [],
                "errors": [f"Registry non raggiungibile: {exc}"],
                "message": str(exc),
            }

        if entry is None:
            _log.warning(
                "[SPARK-ENGINE][WARNING] scf_plugin_install_remote: '%s' non trovato", pkg_id
            )
            return {
                "status": "error",
                "pkg_id": pkg_id,
                "universe": "U2",
                "version": "",
                "files_written": [],
                "files_skipped": [],
                "errors": [f"Package '{pkg_id}' non trovato nel registry."],
                "message": f"Package '{pkg_id}' non trovato nel registry.",
            }

        delivery = str(entry.get("delivery_mode", "managed")).strip()
        if delivery == "mcp_only":
            _log.warning(
                "[SPARK-ENGINE][WARNING] scf_plugin_install_remote: '%s' è mcp_only (U1) — usa scf_plugin_install",
                pkg_id,
            )
            return {
                "status": "error",
                "pkg_id": pkg_id,
                "universe": "U1",
                "version": str(entry.get("latest_version", "")),
                "files_written": [],
                "files_skipped": [],
                "errors": [
                    f"'{pkg_id}' è un pacchetto mcp_only (U1): non può essere installato "
                    "direttamente nel workspace. Usa 'scf_plugin_install'."
                ],
                "message": (
                    f"'{pkg_id}' è mcp_only (U1). Usa 'scf_plugin_install' per il ciclo di vita completo."
                ),
            }

        repo_url = str(entry.get("repo_url", "")).strip()
        version = str(entry.get("latest_version", "latest")).strip()

        try:
            pkg_manifest = registry_client.fetch_package_manifest(repo_url)
        except Exception as exc:  # noqa: BLE001
            _log.error("[SPARK-ENGINE][ERROR] scf_plugin_install_remote manifest: %s", exc)
            return {
                "status": "error",
                "pkg_id": pkg_id,
                "universe": "U2",
                "version": version,
                "files_written": [],
                "files_skipped": [],
                "errors": [f"Impossibile scaricare il manifest: {exc}"],
                "message": str(exc),
            }

        plugin_files: list[str] = list(pkg_manifest.get("plugin_files") or [])
        if not plugin_files:
            _log.info("[SPARK-ENGINE][INFO] scf_plugin_install_remote: nessun plugin_files dichiarato per '%s'", pkg_id)
            return {
                "status": "ok",
                "pkg_id": pkg_id,
                "universe": "U2",
                "version": version,
                "files_written": [],
                "files_skipped": [],
                "errors": [],
                "message": f"'{pkg_id}' non ha plugin_files dichiarati nel manifest.",
            }

        # Prefisso raw GitHub
        if not repo_url.startswith("https://github.com/"):
            return {
                "status": "error",
                "pkg_id": pkg_id,
                "universe": "U2",
                "version": version,
                "files_written": [],
                "files_skipped": [],
                "errors": [f"URL repo non supportata: {repo_url!r}"],
                "message": f"URL repo non supportata: {repo_url!r}",
            }
        raw_base = (
            repo_url.replace("https://github.com/", "https://raw.githubusercontent.com/")
            + "/main/"
        )

        files_written: list[str] = []
        files_skipped: list[str] = []
        errors_list: list[str] = []

        for file_path in plugin_files:
            if not isinstance(file_path, str) or not file_path:
                errors_list.append(f"Entry non valida nel manifest: {file_path!r}")
                continue

            dest = _resolve_safe_github_destination(github_root, file_path)
            if dest is None:
                errors_list.append(f"Path non sicuro rifiutato: {file_path!r}")
                continue

            if dest.is_file() and not overwrite:
                files_skipped.append(file_path)
                _log.info(
                    "[SPARK-ENGINE][INFO] scf_plugin_install_remote: skipped existing %s",
                    file_path,
                )
                continue

            raw_url = raw_base + file_path
            if not raw_url.startswith("https://raw.githubusercontent.com/"):
                errors_list.append(f"URL non sicura rifiutata: {raw_url!r}")
                continue

            try:
                req = urllib.request.Request(
                    raw_url,
                    headers={"User-Agent": f"spark-framework-engine/{ENGINE_VERSION}"},
                )
                _DOWNLOAD_TIMEOUT: int = 10
                with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT) as resp:  # noqa: S310
                    content = resp.read().decode("utf-8")
            except (urllib.error.URLError, OSError, UnicodeDecodeError) as exc:
                errors_list.append(f"{file_path}: download fallito ({exc})")
                _log.error(
                    "[SPARK-ENGINE][ERROR] scf_plugin_install_remote: %s download failed: %s",
                    file_path, exc,
                )
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                dest.write_text(content, encoding="utf-8")
                files_written.append(file_path)
                _log.info(
                    "[SPARK-ENGINE][INFO] scf_plugin_install_remote: written %s", file_path
                )
            except OSError as exc:
                errors_list.append(f"{file_path}: scrittura fallita ({exc})")
                _log.error(
                    "[SPARK-ENGINE][ERROR] scf_plugin_install_remote: write %s failed: %s",
                    file_path, exc,
                )

        success = not errors_list
        _log.info(
            "[SPARK-ENGINE][INFO] scf_plugin_install_remote: done pkg=%s written=%d skipped=%d errors=%d",
            pkg_id, len(files_written), len(files_skipped), len(errors_list),
        )
        return {
            "status": "ok" if success else "error",
            "pkg_id": pkg_id,
            "universe": "U2",
            "version": version,
            "files_written": files_written,
            "files_skipped": files_skipped,
            "errors": errors_list,
            "message": (
                f"{len(files_written)} file installati, {len(files_skipped)} saltati"
                + (f", {len(errors_list)} errori" if errors_list else "")
                + f" ({pkg_id} v{version})."
            ),
        }

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
