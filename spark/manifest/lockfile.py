"""spark.manifest.lockfile — Lockfile runtime SCF.

Gestisce ``.spark/scf-lock.json`` nella root del workspace.
Traccia versioni risolte, hash SHA-256 dei file installati,
sorgente del package (U1 locale / U2 registry) e dipendenze.

Il lockfile è un artefatto derivato dal manifest ed è aggiornato
dopo ogni install/update/remove completato con successo.
Non è mai la fonte di verità per le operazioni di installazione:
il manifest primario rimane ``.scf-manifest.json``.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spark.core.constants import _SCF_LOCK_FILENAME, _SCF_LOCK_SCHEMA_VERSION, _SPARK_DIR

_log: logging.Logger = logging.getLogger("spark-framework-engine")

__all__ = ["LockfileManager"]


class LockfileManager:
    """Read/write the SCF lockfile at ``<workspace_root>/.spark/scf-lock.json``.

    Thread-safety: NOT thread-safe. Designed for single-process sequential use.
    """

    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root
        self._spark_dir = workspace_root / _SPARK_DIR
        self._path = workspace_root / _SCF_LOCK_FILENAME

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> dict[str, Any]:
        """Return the lockfile data dict.

        Returns a fresh empty structure if the file is absent or unreadable.
        """
        if not self._path.is_file():
            return self._empty()
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                _log.warning("[SPARK-ENGINE][LOCKFILE] File non valido, struttura non dict.")
                return self._empty()
            # Normalise: ensure entries is a dict
            if not isinstance(raw.get("entries"), dict):
                raw["entries"] = {}
            return raw
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning("[SPARK-ENGINE][LOCKFILE] Errore lettura lockfile: %s", exc)
            return self._empty()

    def save(self, data: dict[str, Any]) -> None:
        """Persist lockfile data to disk.

        Args:
            data: Full lockfile dict as returned by :meth:`load`.

        Raises:
            OSError: If the file cannot be written.
        """
        self._spark_dir.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def get(self, package_id: str) -> dict[str, Any] | None:
        """Return the lockfile entry for *package_id*, or ``None`` if absent."""
        data = self.load()
        return data["entries"].get(package_id)

    def upsert(
        self,
        package_id: str,
        version: str,
        source: str,
        dependencies: list[str],
        files: dict[str, str] | None = None,
    ) -> None:
        """Insert or update the lock entry for *package_id*.

        Args:
            package_id: SCF package identifier.
            version: Resolved version string (e.g. ``"1.2.3"``).
            source: Package origin: ``"U1"`` (local) or ``"U2"`` (registry).
            dependencies: List of resolved dependency package IDs.
            files: Mapping of ``relative_path -> sha256_hex`` for installed files.
                   Pass ``None`` or empty to omit file hashes.
        """
        data = self.load()
        entry: dict[str, Any] = {
            "version": version,
            "source": source,
            "installed_at": datetime.now(tz=timezone.utc).isoformat(),
            "dependencies": sorted(set(dependencies)),
        }
        if files:
            entry["files"] = dict(files)
        data["entries"][package_id] = entry
        try:
            self.save(data)
        except OSError as exc:
            _log.warning(
                "[SPARK-ENGINE][LOCKFILE] Impossibile aggiornare lockfile per %s: %s",
                package_id,
                exc,
            )

    def remove(self, package_id: str) -> bool:
        """Remove the lock entry for *package_id*.

        Args:
            package_id: SCF package identifier.

        Returns:
            ``True`` if the entry existed and was removed, ``False`` otherwise.
        """
        data = self.load()
        if package_id not in data["entries"]:
            return False
        del data["entries"][package_id]
        try:
            self.save(data)
            return True
        except OSError as exc:
            _log.warning(
                "[SPARK-ENGINE][LOCKFILE] Impossibile rimuovere entry lockfile per %s: %s",
                package_id,
                exc,
            )
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def compute_file_hashes(
        workspace_root: Path, file_paths: list[str]
    ) -> dict[str, str]:
        """Compute SHA-256 hashes for a list of workspace-relative file paths.

        Files that cannot be read are silently skipped.

        Args:
            workspace_root: Absolute path to the workspace root.
            file_paths: Relative paths from workspace root.

        Returns:
            Dict mapping ``relative_path -> sha256_hex`` for readable files.
        """
        result: dict[str, str] = {}
        for rel in file_paths:
            abs_path = workspace_root / rel
            try:
                content = abs_path.read_bytes()
                result[rel] = hashlib.sha256(content).hexdigest()
            except OSError:
                pass
        return result

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {
            "schema_version": _SCF_LOCK_SCHEMA_VERSION,
            "entries": {},
        }
