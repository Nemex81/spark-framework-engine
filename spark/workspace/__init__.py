# Modulo workspace — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""Public re-exports for the ``spark.workspace`` package."""
from __future__ import annotations

from spark.workspace.migration import (
    MigrationPlan,
    MigrationPlanner,
    _V2_MIGRATION_DELETE_FILES,
    _V2_MIGRATION_DELETE_PATTERNS,
    _V2_MIGRATION_KEEP_DIRS,
    _V2_MIGRATION_KEEP_FILES,
    _V2_MIGRATION_OVERRIDE_DIRS,
    _classify_v2_workspace_file,
)

__all__ = [
    "MigrationPlan",
    "MigrationPlanner",
    "_V2_MIGRATION_DELETE_FILES",
    "_V2_MIGRATION_DELETE_PATTERNS",
    "_V2_MIGRATION_KEEP_DIRS",
    "_V2_MIGRATION_KEEP_FILES",
    "_V2_MIGRATION_OVERRIDE_DIRS",
    "_classify_v2_workspace_file",
]
