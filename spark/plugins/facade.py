"""Modulo spark.plugins.facade — punto di accesso unico al Plugin Manager.

``PluginManagerFacade`` è l'unica classe esposta via ``spark.plugins.__init__``
verso il server MCP. Coordina tutte le operazioni di installazione, rimozione
e aggiornamento plugin delegando ai componenti interni del package.

Tutti i metodi pubblici sono sincroni, gestiscono le eccezioni internamente
e restituiscono dict JSON-serializzabili — il canale MCP non riceve mai
stack trace non gestiti.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spark.core.constants import _REGISTRY_URL
from spark.manifest.gateway import WorkspaceWriteGateway
from spark.manifest.manifest import ManifestManager
from spark.plugins.installer import PluginInstaller
from spark.plugins.registry import PluginRegistry
from spark.plugins.remover import PluginRemover
from spark.plugins.schema import (
    PluginInstallError,
    PluginManifest,
    PluginNotFoundError,
    PluginNotInstalledError,
    PluginRecord,
)
from spark.plugins.updater import PluginUpdater
from spark.registry.client import RegistryClient


class PluginManagerFacade:
    """Punto di accesso unico al Plugin Manager dal Server MCP.

    Coordina ``PluginInstaller``, ``PluginRemover``, ``PluginUpdater``,
    ``PluginRegistry`` e ``RegistryClient`` in un'unica interfaccia
    coerente esposta tramite i tool MCP.

    Tutti i metodi pubblici catturano le eccezioni e le restituiscono
    come ``{"success": False, "error": "...", "pkg_id": ...}`` per
    garantire che il canale MCP non riceva mai eccezioni non gestite.

    Args:
        workspace_root: Path assoluto alla root del workspace utente.
        registry_url: URL del ``registry.json`` remoto. Default: costante
            ``_REGISTRY_URL`` da ``spark.core.constants``.
    """

    def __init__(
        self,
        workspace_root: Path,
        registry_url: str = _REGISTRY_URL,
    ) -> None:
        """Inizializza il Plugin Manager con tutte le dipendenze interne.

        Args:
            workspace_root: Path assoluto alla root del workspace utente.
                Corrisponde a ``WorkspaceContext.workspace_root`` nel motore.
            registry_url: URL del registry SCF remoto.
        """
        github_root = workspace_root / ".github"
        self._workspace_root = workspace_root

        # ManifestManager: traccia ownership e SHA dei file installati.
        self._manifest = ManifestManager(github_root)

        # WorkspaceWriteGateway: centralizza le scritture su .github/.
        # Il costruttore reale richiede workspace_root (non github_root).
        self._gateway = WorkspaceWriteGateway(workspace_root, self._manifest)

        # RegistryClient: accesso al registry remoto e cache locale.
        self._remote_registry = RegistryClient(
            github_root=github_root,
            registry_url=registry_url,
        )

        # PluginRegistry: stato dei plugin installati.
        # Usa il manifest-based backend (Step 3) passando il manifest_manager.
        self._plugin_registry = PluginRegistry(github_root, manifest_manager=self._manifest)

        # Componenti operativi del Plugin Manager.
        self._installer = PluginInstaller(workspace_root, self._manifest, self._gateway)
        self._remover = PluginRemover(workspace_root, self._manifest, self._gateway)
        self._updater = PluginUpdater(self._installer, self._remover, self._plugin_registry)

    # ------------------------------------------------------------------
    # API pubblica — tutti i metodi restituiscono dict JSON-serializzabili
    # ------------------------------------------------------------------

    def install(self, pkg_id: str) -> dict[str, Any]:
        """Scarica e installa un plugin dal registry remoto nel workspace.

        Flusso:
        1. Recupera il catalogo dal registry remoto.
        2. Trova il pacchetto per ``pkg_id``.
        3. Scarica il ``package-manifest.json`` dal repo GitHub del plugin.
        4. Installa i file tramite ``PluginInstaller``.
        5. Aggiunge la referenza ``#file:`` in ``copilot-instructions.md``.
        6. Registra il record in ``PluginRegistry``.

        Args:
            pkg_id: Identificatore del pacchetto da installare.

        Returns:
            Dizionario con ``success``, ``pkg_id``, ``version``, ``installed``.
            In caso di errore: ``{"success": False, "error": "...", "pkg_id": ...}``.
        """
        try:
            registry_entry = self._find_registry_entry(pkg_id)
            if registry_entry is None:
                raise PluginNotFoundError(
                    f"Package {pkg_id!r} not found in remote registry."
                )

            version = str(registry_entry.get("latest_version", ""))
            repo_url = str(registry_entry.get("repo_url", ""))
            source_repo = self._extract_source_repo(repo_url)

            # Scarica il package-manifest.json dal repo del plugin.
            pkg_manifest_data = self._remote_registry.fetch_package_manifest(repo_url)

            # Estrai plugin_files: lista dei file da installare fisicamente.
            plugin_files = list(pkg_manifest_data.get("plugin_files") or [])

            plugin_manifest = PluginManifest(
                pkg_id=pkg_id,
                version=version,
                source_repo=source_repo,
                plugin_files=plugin_files,
            )

            # Installa i file nel workspace.
            installed_files = self._installer.install_files(plugin_manifest)

            # Aggiunge la referenza #file: in copilot-instructions.md.
            self._installer._add_instruction_reference(pkg_id)

            # Crea e registra il PluginRecord.
            record = self._build_plugin_record(
                plugin_manifest=plugin_manifest,
                installed_files=installed_files,
            )
            self._plugin_registry.register(record)

            return {
                "success": True,
                "pkg_id": pkg_id,
                "version": version,
                "installed": installed_files,
            }

        except PluginInstallError as exc:
            print(
                f"[SPARK-PLUGINS][ERROR] install({pkg_id}): {exc}",
                file=sys.stderr,
            )
            return {
                "success": False,
                "error": str(exc),
                "pkg_id": pkg_id,
                "failed_files": exc.failed_files,
            }
        except Exception as exc:  # noqa: BLE001
            print(
                f"[SPARK-PLUGINS][ERROR] install({pkg_id}): {exc}",
                file=sys.stderr,
            )
            return {"success": False, "error": str(exc), "pkg_id": pkg_id}

    def remove(self, pkg_id: str) -> dict[str, Any]:
        """Rimuove un plugin installato e i suoi file dal workspace.

        Args:
            pkg_id: Identificatore del pacchetto da rimuovere.

        Returns:
            Dizionario con ``success``, ``pkg_id``, ``removed``.
            In caso di errore: ``{"success": False, "error": "...", "pkg_id": ...}``.
        """
        try:
            record = self._plugin_registry.get(pkg_id)
            if record is None:
                raise PluginNotInstalledError(
                    f"Package {pkg_id!r} is not installed."
                )

            removed_files = self._remover.remove_files(record)
            self._remover._remove_instruction_reference(pkg_id)
            self._plugin_registry.unregister(pkg_id)

            return {
                "success": True,
                "pkg_id": pkg_id,
                "removed": removed_files,
            }

        except Exception as exc:  # noqa: BLE001
            print(
                f"[SPARK-PLUGINS][ERROR] remove({pkg_id}): {exc}",
                file=sys.stderr,
            )
            return {"success": False, "error": str(exc), "pkg_id": pkg_id}

    def update(self, pkg_id: str) -> dict[str, Any]:
        """Aggiorna un plugin installato alla versione più recente disponibile.

        Args:
            pkg_id: Identificatore del pacchetto da aggiornare.

        Returns:
            Dizionario con ``success``, ``pkg_id``, e i campi di ``PluginUpdater.update``.
            In caso di errore: ``{"success": False, "error": "...", "pkg_id": ...}``.
        """
        try:
            old_record = self._plugin_registry.get(pkg_id)
            if old_record is None:
                raise PluginNotInstalledError(
                    f"Package {pkg_id!r} is not installed."
                )

            registry_entry = self._find_registry_entry(pkg_id)
            if registry_entry is None:
                raise PluginNotFoundError(
                    f"Package {pkg_id!r} not found in remote registry."
                )

            version = str(registry_entry.get("latest_version", ""))
            repo_url = str(registry_entry.get("repo_url", ""))
            source_repo = self._extract_source_repo(repo_url)

            pkg_manifest_data = self._remote_registry.fetch_package_manifest(repo_url)
            plugin_files = list(pkg_manifest_data.get("plugin_files") or [])

            new_manifest = PluginManifest(
                pkg_id=pkg_id,
                version=version,
                source_repo=source_repo,
                plugin_files=plugin_files,
            )

            result = self._updater.update(
                pkg_id=pkg_id,
                new_manifest=new_manifest,
                old_record=old_record,
            )

            return {"success": True, "pkg_id": pkg_id, **result}

        except Exception as exc:  # noqa: BLE001
            print(
                f"[SPARK-PLUGINS][ERROR] update({pkg_id}): {exc}",
                file=sys.stderr,
            )
            return {"success": False, "error": str(exc), "pkg_id": pkg_id}

    def list_installed(self) -> dict[str, Any]:
        """Elenca i plugin installati con versione e metadati.

        Returns:
            Dizionario con ``success`` e ``plugins`` (lista di record).
        """
        try:
            records = self._plugin_registry.load()
            plugins = [record.to_dict() for record in records.values()]
            return {"success": True, "plugins": plugins, "count": len(plugins)}
        except Exception as exc:  # noqa: BLE001
            print(
                f"[SPARK-PLUGINS][ERROR] list_installed(): {exc}",
                file=sys.stderr,
            )
            return {"success": False, "error": str(exc), "plugins": []}

    def list_available(self) -> dict[str, Any]:
        """Elenca i pacchetti disponibili nel registry remoto.

        Returns:
            Dizionario con ``success`` e ``packages`` (lista dal registry).
        """
        try:
            packages = self._remote_registry.list_packages()
            return {"success": True, "packages": packages, "count": len(packages)}
        except Exception as exc:  # noqa: BLE001
            print(
                f"[SPARK-PLUGINS][ERROR] list_available(): {exc}",
                file=sys.stderr,
            )
            return {"success": False, "error": str(exc), "packages": []}

    def status(self, pkg_id: str) -> dict[str, Any]:
        """Restituisce lo stato di un singolo plugin: versione, integrità file.

        Args:
            pkg_id: Identificatore del pacchetto.

        Returns:
            Dizionario con ``success``, ``installed``, e se installato:
            ``version``, ``files``, ``migrated``.
        """
        try:
            record = self._plugin_registry.get(pkg_id)
            if record is None:
                return {
                    "success": True,
                    "pkg_id": pkg_id,
                    "installed": False,
                }

            # Verifica quali file sono ancora presenti sul disco.
            present_files = [
                f
                for f in record.files
                if (self._workspace_root / f).is_file()
                or (self._workspace_root / ".github" / f.removeprefix(".github/")).is_file()
            ]

            return {
                "success": True,
                "pkg_id": pkg_id,
                "installed": True,
                "version": record.version,
                "source_repo": record.source_repo,
                "installed_at": record.installed_at,
                "files": record.files,
                "files_present": present_files,
                "files_missing": [f for f in record.files if f not in present_files],
                "migrated": record.migrated,
            }

        except Exception as exc:  # noqa: BLE001
            print(
                f"[SPARK-PLUGINS][ERROR] status({pkg_id}): {exc}",
                file=sys.stderr,
            )
            return {"success": False, "error": str(exc), "pkg_id": pkg_id}

    # ------------------------------------------------------------------
    # Helper privati
    # ------------------------------------------------------------------

    def _find_registry_entry(self, pkg_id: str) -> dict[str, Any] | None:
        """Cerca un pacchetto nel registry remoto per ID.

        Args:
            pkg_id: ID del pacchetto da cercare.

        Returns:
            Entry del registry o None se non trovato.
        """
        packages = self._remote_registry.list_packages()
        for entry in packages:
            if str(entry.get("id", "")).strip() == pkg_id:
                return entry
        return None

    def _extract_source_repo(self, repo_url: str) -> str:
        """Estrae il percorso "owner/repo" dalla URL GitHub completa.

        Args:
            repo_url: URL GitHub nel formato "https://github.com/owner/repo".

        Returns:
            Percorso nel formato "owner/repo" (es. "Nemex81/scf-master-codecrafter").
        """
        prefix = "https://github.com/"
        if repo_url.startswith(prefix):
            return repo_url[len(prefix):]
        return repo_url

    def _build_plugin_record(
        self,
        plugin_manifest: PluginManifest,
        installed_files: list[str],
    ) -> PluginRecord:
        """Costruisce un PluginRecord a partire dal manifest e dai file installati.

        Calcola gli SHA-256 dei file appena scritti nel workspace per
        il tracking futuro del preservation gate.

        Args:
            plugin_manifest: Manifest del plugin appena installato.
            installed_files: Lista dei path dei file scritti con successo.

        Returns:
            PluginRecord pronto per essere registrato in PluginRegistry.
        """
        import hashlib  # noqa: PLC0415

        github_root = self._workspace_root / ".github"
        file_hashes: dict[str, str] = {}

        for file_path in installed_files:
            github_rel = file_path.removeprefix(".github/")
            abs_path = github_root / github_rel
            if abs_path.is_file():
                try:
                    data = abs_path.read_bytes()
                    file_hashes[file_path] = hashlib.sha256(data).hexdigest()
                except OSError:
                    pass

        return PluginRecord(
            pkg_id=plugin_manifest.pkg_id,
            version=plugin_manifest.version,
            source_repo=plugin_manifest.source_repo,
            installed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            files=installed_files,
            file_hashes=file_hashes,
            migrated=False,
        )
