"""Plugin tools factory — Step 2 Full Decoupling Architecture.

Registers 4 MCP tools:
  scf_plugin_install, scf_plugin_remove, scf_plugin_update, scf_plugin_list.

Tutti i tool delegano interamente a ``PluginManagerFacade`` senza logica
di business interna. Ogni tool accetta ``workspace_root: str`` per consentire
operazioni su workspace arbitrari (utile in ambienti multi-root).

Il facade viene instanziato fresh per ogni chiamata con il workspace_root
fornito dal client, con fallback a ``engine._ctx.workspace_root`` se la
stringa è vuota o assente.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from spark.plugins import PluginManagerFacade
from spark.plugins.schema import (
    PluginInstallError,
    PluginNotFoundError,
    PluginNotInstalledError,
)

_log = logging.getLogger("spark-framework-engine")

__all__ = ["register_plugin_tools"]


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


def register_plugin_tools(engine: Any, mcp: Any, tool_names: list[str]) -> None:
    """Register 4 plugin lifecycle tools into mcp.

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
