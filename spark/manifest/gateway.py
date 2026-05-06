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

    def write_many(
        self,
        writes: list[tuple[str, str]],
        owner: str,
        version: str,
        merge_strategies: dict[str, str] | None = None,
    ) -> list[Path]:
        """Scrive N file nel workspace e aggiorna il manifest in una sola operazione.

        Tutti i file condividono lo stesso ``owner`` e ``version``.
        Le scritture fisiche avvengono in sequenza; il manifest è aggiornato
        una sola volta al termine con ``upsert_many`` (OPT-8).

        Args:
            writes: lista di ``(github_rel, content)``.
            owner: package id proprietario di tutti i file.
            version: versione del pacchetto.
            merge_strategies: strategia per file specifici, indicizzata per
                ``github_rel``. Se assente, usa il default del manifest.

        Returns:
            Lista dei Path assoluti scritti.
        """
        if not writes:
            return []
        written_paths: list[Path] = []
        upsert_files: list[tuple[str, Path]] = []
        for github_rel, content in writes:
            target = self._github_root / github_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written_paths.append(target)
            upsert_files.append((github_rel, target))
        try:
            self._manifest.upsert_many(
                package=owner,
                package_version=version,
                files=upsert_files,
                merge_strategies_by_file=merge_strategies,
            )
        except OSError as exc:
            _log.warning(
                "[SPARK-ENGINE][WARNING] Gateway batch upsert failed: %s",
                exc,
            )
        return written_paths

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
