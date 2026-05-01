# Modulo manifest/snapshots — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""SnapshotManager and workspace backup helper."""
from __future__ import annotations

import logging
import re
from pathlib import Path, PurePosixPath

from spark.core.constants import _BACKUPS_SUBDIR, _SNAPSHOTS_SUBDIR
from spark.core.utils import _utc_now

_log: logging.Logger = logging.getLogger("spark-framework-engine")


class SnapshotManager:
    """Manage UTF-8 BASE snapshots stored under .github/runtime/snapshots/."""

    def __init__(self, snapshots_root: Path) -> None:
        self._snapshots_root = snapshots_root

    def save_snapshot(self, package_id: str, file_rel: str, file_abs: Path) -> bool:
        """Persist a UTF-8 snapshot for one package-managed file."""
        snapshot_path = self._snapshot_path(package_id, file_rel)
        if snapshot_path is None:
            return False

        try:
            content = file_abs.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _log.warning("Snapshot skipped for %s (%s): %s", file_rel, package_id, exc)
            return False

        try:
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(content, encoding="utf-8")
        except OSError as exc:
            _log.warning("Cannot write snapshot for %s (%s): %s", file_rel, package_id, exc)
            return False
        return True

    def load_snapshot(self, package_id: str, file_rel: str) -> str | None:
        """Return the stored UTF-8 snapshot content, if available and decodable."""
        snapshot_path = self._snapshot_path(package_id, file_rel)
        if snapshot_path is None or not snapshot_path.is_file():
            return None
        try:
            return snapshot_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _log.warning("Cannot read snapshot for %s (%s): %s", file_rel, package_id, exc)
            return None

    def delete_package_snapshots(self, package_id: str) -> list[str]:
        """Delete all snapshots for one package and return removed relative paths."""
        package_root = self._package_root(package_id)
        if package_root is None or not package_root.exists():
            return []

        all_files = sorted(
            (path for path in package_root.rglob("*") if path.is_file()),
            key=lambda path: len(path.parts),
            reverse=True,
        )
        deleted_files: list[str] = []
        for file_path in all_files:
            try:
                rel = file_path.relative_to(package_root).as_posix()
                file_path.unlink()
                deleted_files.append(rel)
            except OSError as exc:
                _log.warning(
                    "[SPARK-ENGINE][WARNING] delete_package_snapshots partial failure for %s: "
                    "deleted %d file(s), blocked at %s: %s",
                    package_id,
                    len(deleted_files),
                    file_path,
                    exc,
                )
                return sorted(deleted_files)

        for dir_path in sorted(
            (path for path in package_root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            try:
                dir_path.rmdir()
            except OSError:
                pass
        try:
            package_root.rmdir()
        except OSError:
            pass

        return sorted(deleted_files)

    def snapshot_exists(self, package_id: str, file_rel: str) -> bool:
        """Return True when a snapshot file exists for the given package/file pair."""
        snapshot_path = self._snapshot_path(package_id, file_rel)
        return snapshot_path is not None and snapshot_path.is_file()

    def list_package_snapshots(self, package_id: str) -> list[str]:
        """Return sorted snapshot paths relative to the package snapshot root."""
        package_root = self._package_root(package_id)
        if package_root is None or not package_root.is_dir():
            return []
        return sorted(
            path.relative_to(package_root).as_posix()
            for path in package_root.rglob("*")
            if path.is_file()
        )

    def _package_root(self, package_id: str) -> Path | None:
        normalized_package = self._validate_relative_path(package_id)
        if normalized_package is None or "/" in normalized_package:
            return None
        return self._snapshots_root / normalized_package

    def _snapshot_path(self, package_id: str, file_rel: str) -> Path | None:
        package_root = self._package_root(package_id)
        normalized_rel = self._validate_relative_path(file_rel)
        if package_root is None or normalized_rel is None:
            return None
        return package_root / PurePosixPath(normalized_rel)

    def _validate_relative_path(self, path_value: str) -> str | None:
        normalized = path_value.replace("\\", "/").strip()
        if not normalized:
            return None
        if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
            return None

        candidate = PurePosixPath(normalized)
        parts = candidate.parts
        if not parts or any(part in {"", ".", ".."} for part in parts):
            return None
        return candidate.as_posix()


def _scf_backup_workspace(
    package_id: str,
    files_to_backup: list[tuple[str, Path]],
    backup_root: "Path | None" = None,
) -> str:
    """Create a timestamped backup directory for files about to be modified.

    Args:
        package_id: Package identifier for this backup.
        files_to_backup: List of (rel_path, abs_path) pairs.
        backup_root: Optional base dir for backups. When ``None``, the backup is
            created under ``.github/runtime/backups/`` (legacy mode, inferred
            from the file paths). Pass ``runtime_dir / _BACKUPS_SUBDIR`` to
            route backups to the engine runtime directory.
    """
    timestamp = _utc_now().strftime("%Y%m%d-%H%M%S")

    if backup_root is None:
        # Legacy path resolution: infer github_root from file paths.
        github_root: Path | None = None
        for _, file_abs in files_to_backup:
            for candidate in (file_abs.parent, *file_abs.parents):
                if candidate.name == ".github":
                    github_root = candidate
                    break
            if github_root is not None:
                break

        if github_root is None:
            raise ValueError("Cannot infer .github root for workspace backup.")

        effective_backup_root = github_root / "runtime" / "backups" / timestamp
    else:
        effective_backup_root = backup_root / timestamp

    effective_backup_root.mkdir(parents=True, exist_ok=True)
    path_validator = SnapshotManager(effective_backup_root)

    for rel_path, file_abs in files_to_backup:
        normalized_rel = path_validator._validate_relative_path(rel_path)
        if normalized_rel is None or not file_abs.is_file():
            continue
        destination = effective_backup_root / PurePosixPath(normalized_rel)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(file_abs.read_bytes())

    _log.info("Workspace backup created for %s: %s", package_id, effective_backup_root)
    return str(effective_backup_root)
