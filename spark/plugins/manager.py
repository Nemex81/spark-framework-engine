"""Modulo spark.plugins.manager — Plugin Manager leggero per download diretto.

Espone ``PluginManager``, ``download_plugin()`` e ``list_available_plugins()``.

Differenza rispetto a ``PluginManagerFacade``:
- NON registra nulla nello store interno del motore.
- NON aggiorna ``.github/.spark-plugins`` o il manifest.
- Scarica direttamente i ``plugin_files`` del pacchetto nella directory
  ``target_dir/.github/`` del workspace utente su richiesta esplicita.
- Filtra automaticamente i pacchetti ``delivery_mode == "mcp_only"``
  dai risultati di listing: quelli sono serviti via MCP, non da installare.

Questo modulo implementa il TASK-3 della SPARK Dual-Mode Architecture v1.0.
"""
from __future__ import annotations

import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from spark.core.constants import ENGINE_VERSION

_log: logging.Logger = logging.getLogger("spark-framework-engine")

# Timeout per i download HTTP dei file plugin.
_DOWNLOAD_TIMEOUT_SECONDS: int = 10


# ---------------------------------------------------------------------------
# Funzioni standalone (API pubblica del modulo)
# ---------------------------------------------------------------------------


def list_available_plugins(registry_client: Any) -> list[dict[str, Any]]:
    """Recupera dal registry i pacchetti installabili (non mcp_only).

    Filtra i pacchetti con ``delivery_mode == "mcp_only"``: questi sono
    serviti via MCP dallo store del motore e non devono essere scaricati
    direttamente nel workspace.

    Args:
        registry_client: Istanza di ``RegistryClient`` configurata con
            l'URL del registry SCF.

    Returns:
        Lista di dict dei pacchetti disponibili con ``delivery_mode != "mcp_only"``.
        Lista vuota se il registry non è raggiungibile.
    """
    try:
        packages: list[dict[str, Any]] = list(registry_client.list_packages())
    except (ValueError, RuntimeError) as exc:
        _log.warning(
            "[SPARK-PLUGINS][WARNING] list_available_plugins: registry non raggiungibile: %s",
            exc,
        )
        return []

    return [
        pkg
        for pkg in packages
        if str(pkg.get("delivery_mode", "managed")).strip() != "mcp_only"
    ]


def download_plugin(
    package_id: str,
    version: str,
    target_dir: Path,
    registry_client: Any,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Scarica un plugin nella directory ``target_dir/.github/``.

    Il plugin viene scaricato direttamente dal repo GitHub dichiarato nel
    registry. I file vengono estratti nella struttura ``target_dir/.github/``
    preservando la struttura di directory del pacchetto sorgente.

    Il plugin NON viene registrato nello store interno del motore né in
    ``.github/.spark-plugins``. L'utente gestisce i file in autonomia.

    Args:
        package_id: ID del pacchetto da scaricare.
        version: Versione richiesta. Se ``"latest"``, viene usata la versione
            più recente disponibile nel registry.
        target_dir: Directory di destinazione (root del workspace utente).
            I file vengono scritti in ``target_dir/.github/``.
        registry_client: Istanza di ``RegistryClient``.
        overwrite: Se ``True``, sovrascrive i file esistenti. Default ``False``.

    Returns:
        Dict con chiavi:
          - ``success`` (bool): True se tutti i file sono stati scaricati.
          - ``package_id`` (str): ID del pacchetto.
          - ``version`` (str): Versione effettivamente scaricata.
          - ``files_written`` (list[str]): File scritti con successo.
          - ``files_skipped`` (list[str]): File saltati (già esistenti,
            ``overwrite=False``).
          - ``errors`` (list[str]): Errori incontrati.

    """
    github_root = (target_dir / ".github").resolve()

    # Trova il pacchetto nel registry.
    try:
        packages = registry_client.list_packages()
    except (ValueError, RuntimeError) as exc:
        _log.error(
            "[SPARK-PLUGINS][ERROR] download_plugin: registry non raggiungibile: %s", exc
        )
        return {
            "success": False,
            "package_id": package_id,
            "version": version,
            "files_written": [],
            "files_skipped": [],
            "errors": [f"Registry non raggiungibile: {exc}"],
        }
    registry_entry: dict[str, Any] | None = None
    for pkg in packages:
        if str(pkg.get("id", "")).strip() == package_id:
            registry_entry = pkg
            break

    if registry_entry is None:
        return {
            "success": False,
            "package_id": package_id,
            "version": version,
            "files_written": [],
            "files_skipped": [],
            "errors": [f"Package '{package_id}' non trovato nel registry."],
        }

    # Risolvi "latest" alla versione effettiva.
    if version == "latest":
        version = str(registry_entry.get("latest_version", "latest"))

    # Scarica il package-manifest per ottenere la lista dei plugin_files.
    repo_url = str(registry_entry.get("repo_url", ""))
    try:
        pkg_manifest: dict[str, Any] = registry_client.fetch_package_manifest(repo_url)
    except (ValueError, RuntimeError) as exc:
        return {
            "success": False,
            "package_id": package_id,
            "version": version,
            "files_written": [],
            "files_skipped": [],
            "errors": [f"Impossibile scaricare il manifest: {exc}"],
        }

    plugin_files: list[str] = list(pkg_manifest.get("plugin_files") or [])
    if not plugin_files:
        return {
            "success": True,
            "package_id": package_id,
            "version": version,
            "files_written": [],
            "files_skipped": [],
            "errors": [],
        }

    # Estrai il prefisso raw GitHub dal repo_url.
    raw_base = (
        repo_url.replace("https://github.com/", "https://raw.githubusercontent.com/")
        + "/main/"
    )

    files_written: list[str] = []
    files_skipped: list[str] = []
    errors: list[str] = []

    for file_path in plugin_files:
        if not isinstance(file_path, str) or not file_path:
            errors.append(f"Entry non valida nel manifest: {file_path!r}")
            continue

        github_rel = file_path.removeprefix(".github/")

        # Path traversal guard.
        if ".." in Path(github_rel).parts:
            errors.append(f"Path non sicuro rifiutato: {file_path!r}")
            continue

        dest = github_root / github_rel

        # Se il file esiste già e overwrite è False, salta.
        if dest.is_file() and not overwrite:
            files_skipped.append(file_path)
            _log.info(
                "[SPARK-PLUGINS][INFO] download_plugin: skipped existing %s (overwrite=False)",
                file_path,
            )
            continue

        # Download del file.
        raw_url = raw_base + file_path
        if not raw_url.startswith("https://raw.githubusercontent.com/"):
            errors.append(f"URL non supportata: {raw_url!r}")
            continue

        try:
            req = urllib.request.Request(
                raw_url,
                headers={"User-Agent": f"spark-framework-engine/{ENGINE_VERSION}"},
            )
            with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as resp:  # noqa: S310
                content = resp.read().decode("utf-8")
        except (urllib.error.URLError, OSError, UnicodeDecodeError) as exc:
            errors.append(f"{file_path}: download fallito ({exc})")
            _log.error(
                "[SPARK-PLUGINS][ERROR] download_plugin: %s download failed: %s",
                file_path,
                exc,
            )
            continue

        # Scrittura del file nel target_dir.
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            files_written.append(file_path)
            _log.info("[SPARK-PLUGINS][INFO] download_plugin: written %s", file_path)
        except OSError as exc:
            errors.append(f"{file_path}: scrittura fallita ({exc})")
            _log.error(
                "[SPARK-PLUGINS][ERROR] download_plugin: write failed for %s: %s",
                file_path,
                exc,
            )

    return {
        "success": len(errors) == 0,
        "package_id": package_id,
        "version": version,
        "files_written": files_written,
        "files_skipped": files_skipped,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Classe PluginManager
# ---------------------------------------------------------------------------


class PluginManager:
    """Plugin Manager leggero per download diretto nel workspace utente.

    Scarica i plugin direttamente nella struttura ``.github/`` del workspace
    senza registrarli nello store interno del motore.

    Differisce da ``PluginManagerFacade``:
    - Nessun tracking in ``.github/.spark-plugins``.
    - Nessuna scrittura nello store ``packages/<id>/``.
    - Filtra automaticamente i pacchetti ``mcp_only`` dal listing.

    Args:
        registry_client: Istanza di ``RegistryClient``.
        workspace_locator: Istanza di ``WorkspaceLocator`` per risolvere
            il workspace utente corrente.
    """

    def __init__(
        self,
        registry_client: Any,
        workspace_locator: Any,
    ) -> None:
        """Inizializza il PluginManager con le dipendenze iniettate.

        Args:
            registry_client: ``RegistryClient`` configurato con l'URL registry.
            workspace_locator: ``WorkspaceLocator`` per risolvere il workspace.
        """
        self._registry_client = registry_client
        self._workspace_locator = workspace_locator

    def list(self) -> list[dict[str, Any]]:
        """Elenca i plugin disponibili nel registry (esclude mcp_only).

        Returns:
            Lista di dict dei pacchetti installabili via download diretto.
        """
        return list_available_plugins(self._registry_client)

    def install(
        self,
        package_id: str,
        version: str = "latest",
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Scarica un plugin nel workspace utente corrente.

        Usa ``WorkspaceLocator.resolve()`` per determinare il workspace di
        destinazione, poi delega a ``download_plugin()``.

        Args:
            package_id: ID del pacchetto da scaricare.
            version: Versione richiesta o ``"latest"``.
            overwrite: Se True, sovrascrive i file già presenti.

        Returns:
            Dict con ``success``, ``package_id``, ``version``, ``files_written``,
            ``files_skipped``, ``errors``.
        """
        try:
            ctx = self._workspace_locator.resolve()
            workspace_root = ctx.workspace_root
        except Exception as exc:  # noqa: BLE001
            _log.error(
                "[SPARK-PLUGINS][ERROR] PluginManager.install: workspace non risolvibile: %s",
                exc,
            )
            return {
                "success": False,
                "package_id": package_id,
                "version": version,
                "files_written": [],
                "files_skipped": [],
                "errors": [f"workspace non risolvibile: {exc}"],
            }

        return download_plugin(
            package_id=package_id,
            version=version,
            target_dir=workspace_root,
            registry_client=self._registry_client,
            overwrite=overwrite,
        )
