"""Modulo spark.plugins.updater — aggiornamento plugin installati.

Confronta la versione installata con quella disponibile, esegue la
rimozione dei file vecchi e l'installazione dei nuovi tramite le
istanze già create di ``PluginInstaller`` e ``PluginRemover``.
"""
from __future__ import annotations

import sys

from spark.plugins.installer import PluginInstaller
from spark.plugins.registry import PluginRegistry
from spark.plugins.remover import PluginRemover
from spark.plugins.schema import PluginManifest, PluginRecord


class PluginUpdater:
    """Aggiorna un plugin installato a una nuova versione.

    Esegue in sequenza: rimozione dei file vecchi, installazione dei
    nuovi file e aggiornamento del ``PluginRegistry``. Se la rimozione
    parziale ha preservato alcuni file (modificati dall'utente), la
    nuova versione viene comunque installata per i file non preservati.

    Attributes:
        _installer: Istanza di PluginInstaller per la fase di install.
        _remover: Istanza di PluginRemover per la fase di remove.
        _registry: Istanza di PluginRegistry per aggiornare lo stato.
    """

    def __init__(
        self,
        installer: PluginInstaller,
        remover: PluginRemover,
        registry: PluginRegistry,
    ) -> None:
        """Inizializza l'updater con le dipendenze già istanziate.

        Args:
            installer: PluginInstaller attivo per il workspace corrente.
            remover: PluginRemover attivo per il workspace corrente.
            registry: PluginRegistry attivo per il workspace corrente.
        """
        self._installer = installer
        self._remover = remover
        self._registry = registry

    def update(
        self,
        pkg_id: str,
        new_manifest: PluginManifest,
        old_record: PluginRecord,
    ) -> dict:
        """Aggiorna un plugin dalla versione installata a quella nuova.

        Flusso:
        1. Rimuove i file della versione precedente via ``PluginRemover``.
        2. Installa i file della nuova versione via ``PluginInstaller``.
        3. Aggiunge la referenza #file: se necessario.
        4. Aggiorna il ``PluginRegistry`` con il nuovo ``PluginRecord``.

        Args:
            pkg_id: Identificatore del pacchetto da aggiornare.
            new_manifest: PluginManifest della versione target.
            old_record: PluginRecord della versione correntemente installata.

        Returns:
            Dizionario con:
            - ``removed``: path dei file rimossi dalla versione precedente.
            - ``installed``: path dei file installati nella nuova versione.
            - ``version_from``: versione precedente.
            - ``version_to``: nuova versione.

        Raises:
            PluginInstallError: Se uno o più file della nuova versione
                non possono essere installati.
        """
        print(
            f"[SPARK-PLUGINS][INFO] Updating {pkg_id}: "
            f"{old_record.version} → {new_manifest.version}",
            file=sys.stderr,
        )

        # Fase 1: rimozione file della versione precedente.
        removed = self._remover.remove_files(old_record)

        # Fase 2: installazione file della nuova versione.
        # PluginInstallError viene propagata al chiamante se ci sono fallimenti.
        installed = self._installer.install_files(new_manifest)

        # Fase 3: aggiunge o aggiorna la referenza #file: in copilot-instructions.md.
        self._installer._add_instruction_reference(pkg_id)

        # Fase 4: aggiorna il registry con il nuovo record.
        # Importiamo PluginRecord e datetime qui per non appesantire gli import.
        from datetime import datetime, timezone  # noqa: PLC0415

        from spark.plugins.schema import PluginRecord  # noqa: PLC0415

        import hashlib  # noqa: PLC0415

        # Calcola gli SHA dei file appena installati per il tracking futuro.
        from pathlib import Path  # noqa: PLC0415

        github_root = self._installer._github_root
        new_hashes: dict[str, str] = {}
        for file_path in installed:
            github_rel = file_path.removeprefix(".github/")
            abs_path = github_root / github_rel
            if abs_path.is_file():
                try:
                    data = abs_path.read_bytes()
                    new_hashes[file_path] = hashlib.sha256(data).hexdigest()
                except OSError:
                    pass

        new_record = PluginRecord(
            pkg_id=pkg_id,
            version=new_manifest.version,
            source_repo=new_manifest.source_repo,
            installed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            files=installed,
            file_hashes=new_hashes,
            migrated=False,
        )
        self._registry.register(new_record)

        print(
            f"[SPARK-PLUGINS][INFO] Update complete for {pkg_id}: "
            f"{len(removed)} removed, {len(installed)} installed",
            file=sys.stderr,
        )

        return {
            "removed": removed,
            "installed": installed,
            "version_from": old_record.version,
            "version_to": new_manifest.version,
        }
