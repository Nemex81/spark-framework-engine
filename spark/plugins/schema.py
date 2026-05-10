"""Modulo spark.plugins.schema — dataclass e eccezioni del Plugin Manager.

Definisce le strutture dati condivise da tutti i moduli del package
``spark.plugins``. Nessuna logica di I/O o rete: solo rappresentazione
dei dati e gerarchia di eccezioni custom.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Eccezioni custom
# ---------------------------------------------------------------------------


class PluginError(Exception):
    """Base exception per il Plugin Manager."""


class PluginInstallError(PluginError):
    """Sollevata quando uno o più file falliscono durante l'installazione.

    Args:
        pkg_id: ID del pacchetto che ha fallito.
        failed_files: Lista dei path che non è stato possibile installare.
    """

    def __init__(self, pkg_id: str, failed_files: list[str]) -> None:
        self.pkg_id = pkg_id
        self.failed_files = failed_files
        super().__init__(f"Plugin {pkg_id}: install failed for {failed_files}")


class PluginNotFoundError(PluginError):
    """Sollevata quando il pacchetto non è presente nel registry remoto."""


class PluginNotInstalledError(PluginError):
    """Sollevata quando si tenta di rimuovere/aggiornare un plugin non installato."""


# ---------------------------------------------------------------------------
# Dataclass PluginManifest
# ---------------------------------------------------------------------------


@dataclass
class PluginManifest:
    """Rappresenta il manifest di un pacchetto scaricato dal registry remoto.

    Costruito al momento dell'installazione a partire dai dati del registry
    e del ``package-manifest.json`` recuperato dal repository GitHub del plugin.

    Attributes:
        pkg_id: Identificatore univoco del pacchetto (es. "scf-master-codecrafter").
        version: Versione SemVer del pacchetto (es. "2.6.0").
        source_repo: Percorso GitHub del repo sorgente nel formato "owner/repo"
            (es. "Nemex81/scf-master-codecrafter").
        plugin_files: Lista di path relativi al workspace dei file da installare
            fisicamente in ``.github/``. Se vuota, l'installazione non scrive nulla.
    """

    pkg_id: str
    version: str
    source_repo: str
    plugin_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializza il manifest in un dizionario JSON-serializzabile.

        Returns:
            Dict con i campi del manifest.
        """
        return {
            "pkg_id": self.pkg_id,
            "version": self.version,
            "source_repo": self.source_repo,
            "plugin_files": list(self.plugin_files),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginManifest:
        """Deserializza un dizionario in un'istanza di PluginManifest.

        Args:
            data: Dizionario con i campi del manifest.

        Returns:
            Istanza di PluginManifest.

        Raises:
            KeyError: Se mancano campi obbligatori nel dizionario.
        """
        return cls(
            pkg_id=str(data["pkg_id"]),
            version=str(data["version"]),
            source_repo=str(data["source_repo"]),
            plugin_files=list(data.get("plugin_files") or []),
        )


# ---------------------------------------------------------------------------
# Dataclass PluginRecord
# ---------------------------------------------------------------------------


@dataclass
class PluginRecord:
    """Rappresenta un pacchetto installato nel workspace utente.

    Persistito nel file ``.github/.spark-plugins`` come entry JSON nel
    campo ``installed``. Aggiornato da ``PluginRegistry`` ad ogni
    operazione di install/update/remove.

    Attributes:
        pkg_id: Identificatore univoco del pacchetto.
        version: Versione installata.
        source_repo: Percorso GitHub sorgente nel formato "owner/repo".
        installed_at: Timestamp di installazione in formato ISO 8601.
        files: Lista dei path relativi al workspace dei file installati.
        file_hashes: Mappa path → sha256 dei file al momento dell'installazione.
        migrated: True se il record è stato importato da ManifestManager
            piuttosto che installato tramite PluginInstaller.
    """

    pkg_id: str
    version: str
    source_repo: str
    installed_at: str
    files: list[str] = field(default_factory=list)
    file_hashes: dict[str, str] = field(default_factory=dict)
    migrated: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serializza il record in un dizionario JSON-serializzabile.

        Returns:
            Dict con tutti i campi del record.
        """
        return {
            "pkg_id": self.pkg_id,
            "version": self.version,
            "source_repo": self.source_repo,
            "installed_at": self.installed_at,
            "files": list(self.files),
            "file_hashes": dict(self.file_hashes),
            "migrated": self.migrated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginRecord:
        """Deserializza un dizionario in un'istanza di PluginRecord.

        Args:
            data: Dizionario con i campi del record.

        Returns:
            Istanza di PluginRecord.

        Raises:
            KeyError: Se mancano campi obbligatori nel dizionario.
        """
        return cls(
            pkg_id=str(data["pkg_id"]),
            version=str(data["version"]),
            source_repo=str(data.get("source_repo", "")),
            installed_at=str(data["installed_at"]),
            files=list(data.get("files") or []),
            file_hashes=dict(data.get("file_hashes") or {}),
            migrated=bool(data.get("migrated", False)),
        )
