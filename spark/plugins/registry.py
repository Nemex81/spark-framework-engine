"""Modulo spark.plugins.registry — stato locale dei plugin installati.

Gestisce il file ``.github/.spark-plugins`` che tiene traccia dei pacchetti
del Plugin Manager (Universo B) installati fisicamente nel workspace utente.
Questo file è parallelo e complementare a ``.github/.scf-manifest.json``:
il manifest traccia i file singoli, il plugin registry traccia i pacchetti.
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

# Nome del file di stato locale del Plugin Manager.
_PLUGINS_FILENAME: str = ".spark-plugins"

# Versione corrente dello schema del file .spark-plugins.
_PLUGINS_SCHEMA_VERSION: str = "1.0"


class PluginRegistry:
    """Gestisce lo stato dei pacchetti plugin installati nel workspace.

    Legge e scrive il file ``.github/.spark-plugins`` in formato JSON.
    Ogni operazione di scrittura (``register``, ``unregister``) salva
    immediatamente su disco per garantire coerenza anche in caso di crash.

    Attributes:
        _github_root: Path assoluto alla cartella ``.github/`` del workspace.
        _path: Path assoluto al file ``.github/.spark-plugins``.
    """

    def __init__(self, github_root: Path) -> None:
        """Inizializza il registry puntando alla root .github/ del workspace.

        Args:
            github_root: Path assoluto alla cartella ``.github/`` del workspace.
        """
        self._github_root = github_root
        self._path = github_root / _PLUGINS_FILENAME

    # ------------------------------------------------------------------
    # Lettura
    # ------------------------------------------------------------------

    def load(self) -> dict[str, PluginRecord]:
        """Carica tutti i record dal file ``.spark-plugins``.

        Se il file è assente o non leggibile, restituisce un dizionario vuoto
        senza sollevare eccezioni — comportamento atteso al primo avvio.

        Returns:
            Dizionario ``{pkg_id: PluginRecord}`` con i plugin installati.
            Vuoto se il file non esiste o è malformato.
        """
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
                # pkg_id è già nella chiave del dict, ma lo preserviamo anche
                # nel campo del record per self-description.
                entry_with_id = {**entry, "pkg_id": pkg_id}
                records[pkg_id] = PluginRecord.from_dict(entry_with_id)
            except (KeyError, TypeError, ValueError) as exc:
                print(
                    f"[SPARK-PLUGINS][WARNING] Skipping malformed record for {pkg_id!r}: {exc}",
                    file=sys.stderr,
                )
        return records

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
        """Aggiunge o aggiorna il record di un plugin e salva su disco.

        Operazione idempotente: se il pkg_id esiste già, il record viene
        sostituito con i nuovi dati.

        Args:
            record: PluginRecord da registrare.
        """
        records = self.load()
        records[record.pkg_id] = record
        self._save(records)
        print(
            f"[SPARK-PLUGINS][INFO] Registered plugin {record.pkg_id}@{record.version}",
            file=sys.stderr,
        )

    def unregister(self, pkg_id: str) -> None:
        """Rimuove il record di un plugin e salva su disco.

        No-op se il plugin non è presente — non solleva eccezioni.

        Args:
            pkg_id: Identificatore del pacchetto da rimuovere.
        """
        records = self.load()
        if pkg_id not in records:
            return
        del records[pkg_id]
        self._save(records)
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
                # Escludi la sentinella v3_store che non è un file fisico.
                and not str(e.get("installation_mode", "")).strip() == "v3_store"
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

        self._save(migrated_records)
        print(
            f"[SPARK-PLUGINS][INFO] Migration complete: {len(migrated_records)} record(s) written",
            file=sys.stderr,
        )
        return len(migrated_records)

    # ------------------------------------------------------------------
    # Helper privato
    # ------------------------------------------------------------------

    def _save(self, records: dict[str, PluginRecord]) -> None:
        """Persiste il dizionario dei record su disco.

        Args:
            records: Dizionario ``{pkg_id: PluginRecord}`` da salvare.

        Raises:
            OSError: Se la scrittura su disco fallisce.
        """
        # Costruisce il payload JSON dal dict dei record.
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
