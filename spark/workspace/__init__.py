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
from spark.workspace.locator import WorkspaceLocator
from spark.workspace.policy import (
    _default_update_policy,
    _default_update_policy_payload,
    _normalize_update_mode,
    _read_update_policy_payload,
    _update_policy_path,
    _validate_update_mode,
    _write_update_policy_payload,
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
    "WorkspaceLocator",
    "_default_update_policy",
    "_default_update_policy_payload",
    "_normalize_update_mode",
    "_read_update_policy_payload",
    "_update_policy_path",
    "_validate_update_mode",
    "_write_update_policy_payload",
]
