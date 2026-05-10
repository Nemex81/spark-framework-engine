"""Modulo spark.plugins.registry — stato locale dei plugin installati.

Gestisce lo stato dei pacchetti del Plugin Manager (Universo B) installati
fisicamente nel workspace utente.  A partire da Step 3, il backend preferito
è ``ManifestManager`` (entry sentinella con ``installation_mode: "plugin_manager"``);
il file ``.github/.spark-plugins`` rimane come fallback per retrocompatibilità
con workspace non ancora migrati.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from spark.plugins.schema import PluginRecord

if TYPE_CHECKING:
    from spark.manifest.manifest import ManifestManager

# Nome del file di stato legacy del Plugin Manager (Universo B).
# Mantenuto solo per la migrazione; i nuovi record usano il manifest.
_PLUGINS_FILENAME: str = ".spark-plugins"

# Versione corrente dello schema del file .spark-plugins (legacy).
_PLUGINS_SCHEMA_VERSION: str = "1.0"

# installation_mode usato nelle entry sentinella del manifest.
_PLUGIN_MANAGER_INSTALLATION_MODE: str = "plugin_manager"


def _plugin_sentinel_file(package_id: str) -> str:
    """Path sentinella per le entry plugin_manager nel manifest.

    Non corrisponde a un path reale nel workspace — serve solo come chiave
    univoca nell'indice del manifest per evitare collisioni con file reali.
    """
    return f"__plugins__/{package_id}"


class PluginRegistry:
    """Gestisce lo stato dei pacchetti plugin installati nel workspace.

    Supporta due backend di storage:
    - **Manifest-based** (preferito): richiede ``manifest_manager``. Le info
      di installazione vengono scritte come entry sentinella con
      ``installation_mode: "plugin_manager"`` nel ``.scf-manifest.json``.
    - **File-based** (legacy/fallback): legge e scrive ``.github/.spark-plugins``.

    Attributes:
        _github_root: Path assoluto alla cartella ``.github/`` del workspace.
        _path: Path assoluto al file ``.github/.spark-plugins`` (legacy).
        _manifest: ManifestManager opzionale per il backend manifest-based.
    """

    def __init__(
        self,
        github_root: Path,
        manifest_manager: ManifestManager | None = None,
    ) -> None:
        """Inizializza il registry puntando alla root .github/ del workspace.

        Args:
            github_root: Path assoluto alla cartella ``.github/`` del workspace.
            manifest_manager: Se fornito, abilita il backend manifest-based.
                I nuovi record vengono scritti nel manifest come entry sentinella;
                il file ``.spark-plugins`` viene ignorato in scrittura ma resta
                leggibile per la migrazione.
        """
        self._github_root = github_root
        self._path = github_root / _PLUGINS_FILENAME
        self._manifest = manifest_manager

    # ------------------------------------------------------------------
    # Lettura
    # ------------------------------------------------------------------

    def load(self) -> dict[str, PluginRecord]:
        """Carica tutti i record dei plugin installati.

        Se ``manifest_manager`` è disponibile, legge dal manifest (backend
        preferito).  Altrimenti legge dal file ``.spark-plugins`` legacy.

        Returns:
            Dizionario ``{pkg_id: PluginRecord}`` con i plugin installati.
            Vuoto se nessun plugin è installato o il file è assente/malformato.
        """
        if self._manifest is not None:
            return self._load_from_manifest()
        return self._load_from_file()

    def get(self, pkg_id: str) -> PluginRecord | None:
        """Restituisce il record di un plugin installato, o None se assente.

        Args:
            pkg_id: Identificatore del pacchetto.

        Returns:
            ``PluginRecord`` se il plugin è installato, ``None`` altrimenti.
        """
        return self.load().get(pkg_id)

    # ------------------------------------------------------------------
    # Scrittura
    # ------------------------------------------------------------------

    def register(self, record: PluginRecord) -> None:
        """Aggiunge o aggiorna il record di un plugin e persiste lo stato.

        Se ``manifest_manager`` è disponibile, scrive una entry sentinella nel
        manifest (backend preferito).  Altrimenti scrive nel file legacy.

        Args:
            record: PluginRecord da registrare.
        """
        if self._manifest is not None:
            self._register_in_manifest(record)
        else:
            self._register_in_file(record)
        print(
            f"[SPARK-PLUGINS][INFO] Registered plugin {record.pkg_id}@{record.version}",
            file=sys.stderr,
        )

    def unregister(self, pkg_id: str) -> None:
        """Rimuove il record di un plugin e persiste lo stato.

        No-op se il plugin non è presente — non solleva eccezioni.

        Args:
            pkg_id: Identificatore del pacchetto da rimuovere.
        """
        if self._manifest is not None:
            self._unregister_from_manifest(pkg_id)
        else:
            self._unregister_from_file(pkg_id)
        print(
            f"[SPARK-PLUGINS][INFO] Unregistered plugin {pkg_id}",
            file=sys.stderr,
        )

    # ------------------------------------------------------------------
    # Migrazione da ManifestManager
    # ------------------------------------------------------------------

    def migrate_from_manifest(self, manifest_manager: ManifestManager) -> int:
        """Importa i pacchetti tracciati da ManifestManager come record migrati.

        Viene chiamato una sola volta quando ``.spark-plugins`` è assente e si
        vuole inizializzare il Plugin Registry a partire dallo stato del manifest
        esistente. I record importati hanno ``migrated=True`` per distinguerli
        da installazioni native via PluginInstaller.

        Args:
            manifest_manager: Istanza di ManifestManager già istanziata con
                il ``github_root`` del workspace corrente.

        Returns:
            Numero di record importati. 0 se il file esiste già o il manifest
            è vuoto.
        """
        # Non sovrascrivere: il file esiste già, la migrazione è già avvenuta.
        if self._path.is_file():
            return 0

        installed_versions = manifest_manager.get_installed_versions()
        if not installed_versions:
            return 0

        print(
            f"[SPARK-PLUGINS][INFO] Migrating {len(installed_versions)} package(s) "
            "from ManifestManager to .spark-plugins",
            file=sys.stderr,
        )

        entries = manifest_manager.load()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        migrated_records: dict[str, PluginRecord] = {}

        for pkg_id, version in installed_versions.items():
            # Raccoglie tutti i file tracciati per questo pacchetto nel manifest.
            pkg_files: list[str] = [
                str(e.get("file", ""))
                for e in entries
                if str(e.get("package", "")).strip() == pkg_id
                and str(e.get("file", "")).strip()
                # Escludi le sentinelle che non sono file fisici.
                and not str(e.get("installation_mode", "")).strip() in (
                    "v3_store",
                    _PLUGIN_MANAGER_INSTALLATION_MODE,
                )
            ]
            migrated_records[pkg_id] = PluginRecord(
                pkg_id=pkg_id,
                version=version,
                # source_repo non disponibile nel manifest: placeholder vuoto.
                source_repo="",
                installed_at=now,
                files=pkg_files,
                file_hashes={},
                migrated=True,
            )

        self._save_file(migrated_records)
        print(
            f"[SPARK-PLUGINS][INFO] Migration complete: {len(migrated_records)} record(s) written",
            file=sys.stderr,
        )
        return len(migrated_records)

    # ------------------------------------------------------------------
    # Backend manifest-based (Step 3 — preferito)
    # ------------------------------------------------------------------

    def _load_from_manifest(self) -> dict[str, PluginRecord]:
        """Legge i record plugin dalle entry sentinella del manifest."""
        assert self._manifest is not None  # noqa: S101
        entries = self._manifest.load()
        records: dict[str, PluginRecord] = {}
        for entry in entries:
            if str(entry.get("installation_mode", "")).strip() != _PLUGIN_MANAGER_INSTALLATION_MODE:
                continue
            pkg_id = str(entry.get("package", "")).strip()
            if not pkg_id:
                continue
            version = str(entry.get("package_version", "")).strip()
            source_repo = str(entry.get("source_repo", "")).strip()
            installed_at = str(entry.get("installed_at", "")).strip()
            raw_files = entry.get("files", [])
            files: list[str] = raw_files if isinstance(raw_files, list) else []
            raw_hashes = entry.get("file_hashes", {})
            file_hashes: dict[str, str] = raw_hashes if isinstance(raw_hashes, dict) else {}
            migrated: bool = bool(entry.get("migrated", False))
            try:
                records[pkg_id] = PluginRecord(
                    pkg_id=pkg_id,
                    version=version,
                    source_repo=source_repo,
                    installed_at=installed_at,
                    files=files,
                    file_hashes=file_hashes,
                    migrated=migrated,
                )
            except (TypeError, ValueError) as exc:
                print(
                    f"[SPARK-PLUGINS][WARNING] Skipping malformed manifest plugin record "
                    f"for {pkg_id!r}: {exc}",
                    file=sys.stderr,
                )
        return records

    def _register_in_manifest(self, record: PluginRecord) -> None:
        """Scrive la entry sentinella del plugin nel manifest."""
        assert self._manifest is not None  # noqa: S101
        sentinel = _plugin_sentinel_file(record.pkg_id)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entries = self._manifest.load()
        # Rimuovi entry sentinella precedente per questo package.
        entries = [
            e
            for e in entries
            if not (
                str(e.get("installation_mode", "")).strip() == _PLUGIN_MANAGER_INSTALLATION_MODE
                and str(e.get("package", "")).strip() == record.pkg_id
            )
        ]
        entries.append(
            {
                "file": sentinel,
                "package": record.pkg_id,
                "package_version": record.version,
                "installed_at": now,
                "installation_mode": _PLUGIN_MANAGER_INSTALLATION_MODE,
                "source_repo": record.source_repo,
                "files": list(record.files),
                "file_hashes": dict(record.file_hashes),
                "migrated": record.migrated,
            }
        )
        self._manifest.save(entries)

    def _unregister_from_manifest(self, pkg_id: str) -> None:
        """Rimuove la entry sentinella del plugin dal manifest."""
        assert self._manifest is not None  # noqa: S101
        entries = self._manifest.load()
        filtered = [
            e
            for e in entries
            if not (
                str(e.get("installation_mode", "")).strip() == _PLUGIN_MANAGER_INSTALLATION_MODE
                and str(e.get("package", "")).strip() == pkg_id
            )
        ]
        if len(filtered) < len(entries):
            self._manifest.save(filtered)

    # ------------------------------------------------------------------
    # Backend file-based (legacy / fallback)
    # ------------------------------------------------------------------

    def _load_from_file(self) -> dict[str, PluginRecord]:
        """Carica tutti i record dal file ``.spark-plugins`` (legacy)."""
        if not self._path.is_file():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(
                f"[SPARK-PLUGINS][WARNING] Cannot read {self._path}: {exc}",
                file=sys.stderr,
            )
            return {}

        installed_raw = raw.get("installed") or {}
        if not isinstance(installed_raw, dict):
            return {}

        records: dict[str, PluginRecord] = {}
        for pkg_id, entry in installed_raw.items():
            if not isinstance(entry, dict):
                continue
            try:
                entry_with_id = {**entry, "pkg_id": pkg_id}
                records[pkg_id] = PluginRecord.from_dict(entry_with_id)
            except (KeyError, TypeError, ValueError) as exc:
                print(
                    f"[SPARK-PLUGINS][WARNING] Skipping malformed record for {pkg_id!r}: {exc}",
                    file=sys.stderr,
                )
        return records

    def _register_in_file(self, record: PluginRecord) -> None:
        """Aggiunge o aggiorna il record nel file ``.spark-plugins`` (legacy)."""
        records = self._load_from_file()
        records[record.pkg_id] = record
        self._save_file(records)

    def _unregister_from_file(self, pkg_id: str) -> None:
        """Rimuove il record dal file ``.spark-plugins`` (legacy)."""
        records = self._load_from_file()
        if pkg_id not in records:
            return
        del records[pkg_id]
        self._save_file(records)

    def _save_file(self, records: dict[str, PluginRecord]) -> None:
        """Persiste il dizionario dei record nel file ``.spark-plugins`` su disco.

        Args:
            records: Dizionario ``{pkg_id: PluginRecord}`` da salvare.

        Raises:
            OSError: Se la scrittura su disco fallisce.
        """
        installed_payload: dict[str, Any] = {
            pkg_id: {k: v for k, v in record.to_dict().items() if k != "pkg_id"}
            for pkg_id, record in records.items()
        }
        payload: dict[str, Any] = {
            "schema_version": _PLUGINS_SCHEMA_VERSION,
            "installed": installed_payload,
        }
        try:
            self._github_root.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            print(
                f"[SPARK-PLUGINS][ERROR] Cannot write {self._path}: {exc}",
                file=sys.stderr,
            )
            raise
