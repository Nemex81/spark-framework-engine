# Modulo manifest — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""Public re-exports for the ``spark.manifest`` package."""
from __future__ import annotations

from spark.manifest.diff import _normalize_remote_file_record, _scf_diff_workspace
from spark.manifest.manifest import ManifestManager
from spark.manifest.snapshots import SnapshotManager, _scf_backup_workspace

__all__ = [
    "ManifestManager",
    "SnapshotManager",
    "_normalize_remote_file_record",
    "_scf_backup_workspace",
    "_scf_diff_workspace",
]
