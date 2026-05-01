# Modulo manifest/gateway — SPARK Framework Engine
"""WorkspaceWriteGateway — gateway centralizzato per scritture su workspace .github/."""
from __future__ import annotations

import logging
from pathlib import Path

from spark.manifest.manifest import ManifestManager

_log: logging.Logger = logging.getLogger("spark-framework-engine")


class WorkspaceWriteGateway:
    """Route tutte le scritture su ``<workspace>/.github/**`` attraverso ManifestManager.

    Ogni chiamata a ``write`` o ``write_bytes``:

    1. Crea le directory padre se necessario.
    2. Scrive il contenuto su disco.
    3. Chiama ``manifest_manager.upsert()`` per registrare owner, version e sha256.

    ``delete`` rimuove il file e l'entry owner dal manifest.

    Le scritture alla root del workspace al di fuori di ``.github/`` (es. ``.clinerules``)
    devono essere fatte direttamente: sono fuori scope di questo gateway.
    """

    def __init__(
        self,
        workspace_root: Path,
        manifest_manager: ManifestManager,
    ) -> None:
        self._workspace_root = workspace_root
        self._github_root = workspace_root / ".github"
        self._manifest = manifest_manager

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def write(
        self,
        github_rel: str,
        content: str,
        owner: str,
        version: str,
        merge_strategy: str | None = None,
    ) -> Path:
        """Scrive *content* in ``<github>/{github_rel}`` e registra nel manifest.

        Args:
            github_rel: path relativo a ``.github/``.
            content: testo da scrivere (UTF-8).
            owner: package id proprietario del file.
            version: versione del pacchetto.
            merge_strategy: strategia di merge opzionale per il manifest entry.

        Returns:
            Path assoluto del file scritto.
        """
        target = self._github_root / github_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        try:
            self._manifest.upsert(github_rel, owner, version, target, merge_strategy)
        except OSError as exc:
            _log.warning(
                "[SPARK-ENGINE][WARNING] Gateway manifest upsert failed for %s: %s",
                github_rel,
                exc,
            )
        return target

    def write_bytes(
        self,
        github_rel: str,
        content: bytes,
        owner: str,
        version: str,
    ) -> Path:
        """Scrive bytes grezzi in ``<github>/{github_rel}`` e registra nel manifest.

        Args:
            github_rel: path relativo a ``.github/``.
            content: bytes da scrivere.
            owner: package id proprietario del file.
            version: versione del pacchetto.

        Returns:
            Path assoluto del file scritto.
        """
        target = self._github_root / github_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        try:
            self._manifest.upsert(github_rel, owner, version, target)
        except OSError as exc:
            _log.warning(
                "[SPARK-ENGINE][WARNING] Gateway manifest upsert failed for %s: %s",
                github_rel,
                exc,
            )
        return target

    # ------------------------------------------------------------------
    # Delete helper
    # ------------------------------------------------------------------

    def delete(
        self,
        github_rel: str,
        owner: str,
    ) -> bool:
        """Elimina ``<github>/{github_rel}`` e rimuove l'entry owner dal manifest.

        Args:
            github_rel: path relativo a ``.github/``.
            owner: package id di cui rimuovere l'entry.

        Returns:
            ``True`` se il file esisteva ed è stato eliminato.

        Raises:
            OSError: se l'unlink fallisce.
        """
        target = self._github_root / github_rel
        existed = target.is_file()
        if existed:
            try:
                target.unlink()
            except OSError as exc:
                _log.warning(
                    "[SPARK-ENGINE][WARNING] Gateway delete failed for %s: %s",
                    github_rel,
                    exc,
                )
                raise
        try:
            entries = self._manifest.load()
            new_entries = [
                e
                for e in entries
                if not (
                    str(e.get("file", "")).strip() == github_rel
                    and str(e.get("package", "")).strip() == owner
                )
            ]
            if len(new_entries) != len(entries):
                self._manifest.save(new_entries)
        except OSError as exc:
            _log.warning(
                "[SPARK-ENGINE][WARNING] Gateway manifest cleanup failed for %s: %s",
                github_rel,
                exc,
            )
        return existed
