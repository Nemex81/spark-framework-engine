# Modulo core — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""Public re-exports for the ``spark.core`` package."""
from __future__ import annotations

from spark.core.constants import (
    ENGINE_VERSION,
    _ALLOWED_UPDATE_MODES,
    _BACKUPS_SUBDIR,
    _BOOTSTRAP_PACKAGE_ID,
    _CHANGELOGS_SUBDIR,
    _LEGACY_MANIFEST_SCHEMA_VERSIONS,
    _MANIFEST_FILENAME,
    _MANIFEST_SCHEMA_VERSION,
    _MERGE_SESSIONS_SUBDIR,
    _REGISTRY_CACHE_FILENAME,
    _REGISTRY_TIMEOUT_SECONDS,
    _REGISTRY_URL,
    _RESOURCE_TYPES,
    _SNAPSHOTS_SUBDIR,
    _SUPPORTED_MANIFEST_SCHEMA_VERSIONS,
    _USER_PREFS_FILENAME,
)
from spark.core.models import (
    MERGE_STATUS_CLEAN,
    MERGE_STATUS_CONFLICT,
    MERGE_STATUS_IDENTICAL,
    FrameworkFile,
    MergeConflict,
    MergeResult,
    WorkspaceContext,
)
from spark.core.utils import (
    _FM_BLOCK_ITEM_RE,
    _FM_INLINE_LIST_RE,
    _SEMVER_RE,
    _V3_LIFECYCLE_MIN_ENGINE_VERSION,
    _extract_version_from_changelog,
    _format_utc_timestamp,
    _infer_scf_file_role,
    _is_engine_version_compatible,
    _is_v3_package,
    _normalize_manifest_relative_path,
    _normalize_string_list,
    _parse_semver_triplet,
    _parse_utc_timestamp,
    _resolve_dependency_update_order,
    _sha256_text,
    _utc_now,
    parse_markdown_frontmatter,
)

__all__ = [
    "ENGINE_VERSION",
    "FrameworkFile",
    "MERGE_STATUS_CLEAN",
    "MERGE_STATUS_CONFLICT",
    "MERGE_STATUS_IDENTICAL",
    "MergeConflict",
    "MergeResult",
    "WorkspaceContext",
    "parse_markdown_frontmatter",
]
