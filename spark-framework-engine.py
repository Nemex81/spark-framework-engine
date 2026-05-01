"""SPARK Framework Engine: expose the SPARK Code Framework as MCP Resources and Tools.

Transport: stdio only.
Logging: stderr or file — never stdout (would corrupt the JSON-RPC stream).
Python: 3.10+ required (MCP SDK baseline).

Domain boundary:
- Slash commands (/scf-*): handled by VS Code natively from .github/prompts/
- Tools and Resources: handled by this server — dynamic, on-demand, Agent mode only
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
_log: logging.Logger = logging.getLogger("spark-framework-engine")

# ---------------------------------------------------------------------------
# Re-export hub — Fase 0 refactoring modulare
# Le definizioni canoniche vivono in spark/core/*. L'hub mantiene compatibilità
# di import per chiamate esterne legacy (`from spark_framework_engine import X`).
# ---------------------------------------------------------------------------
from spark.core.constants import (  # noqa: E402,F401
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
from spark.core.models import (  # noqa: E402,F401
    MERGE_STATUS_CLEAN,
    MERGE_STATUS_CONFLICT,
    MERGE_STATUS_IDENTICAL,
    FrameworkFile,
    MergeConflict,
    MergeResult,
    WorkspaceContext,
)
from spark.core.utils import (  # noqa: E402,F401
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
from spark.merge import (  # noqa: E402,F401
    MergeEngine,
    MergeSessionManager,
    run_post_merge_validators,
    validate_completeness,
    validate_structural,
    validate_tool_coherence,
)
from spark.merge.sections import (  # noqa: E402,F401
    _SCF_SECTION_HEADER,
    _classify_copilot_instructions_format,
    _prepare_copilot_instructions_migration,
    _scf_extract_merge_priority,
    _scf_iter_section_blocks,
    _scf_render_section,
    _scf_section_markers,
    _scf_section_merge,
    _scf_section_merge_text,
    _scf_split_frontmatter,
    _scf_strip_section,
    _section_markers_for_package,
    _strip_package_section,
)
from spark.merge.validators import (  # noqa: E402,F401
    _MARKDOWN_HEADING_RE,
    _SUPPORTED_CONFLICT_MODES,
    _extract_frontmatter_block,
    _extract_markdown_headings,
    _normalize_merge_text,
    _resolve_disjoint_line_additions,
)
from spark.manifest import (  # noqa: E402,F401
    ManifestManager,
    SnapshotManager,
    _normalize_remote_file_record,
    _scf_backup_workspace,
    _scf_diff_workspace,
)
from spark.registry import (  # noqa: E402,F401
    McpResourceRegistry,
    PackageResourceStore,
    RegistryClient,
    _V3_STORE_INSTALLATION_MODE,
    _build_package_raw_url_base,
    _resource_filename_candidates,
    _v3_store_sentinel_file,
)
from spark.workspace import (  # noqa: E402,F401
    MigrationPlan,
    MigrationPlanner,
    _V2_MIGRATION_DELETE_FILES,
    _V2_MIGRATION_DELETE_PATTERNS,
    _V2_MIGRATION_KEEP_DIRS,
    _V2_MIGRATION_KEEP_FILES,
    _V2_MIGRATION_OVERRIDE_DIRS,
    _classify_v2_workspace_file,
)
from spark.packages import (  # noqa: E402,F401
    _build_registry_package_summary,
    _get_registry_min_engine_version,
    _install_package_v3_into_store,
    _list_orphan_overrides_for_package,
    _remove_package_v3_from_store,
    _resolve_package_version,
    _v3_overrides_blocking_update,
)
from spark.assets import (  # noqa: E402,F401
    _AGENTS_INDEX_BEGIN,
    _AGENTS_INDEX_END,
    _CLINERULES_TEMPLATE_HEADER,
    _PROJECT_PROFILE_TEMPLATE,
    _agents_index_section_text,
    _apply_phase6_assets,
    _collect_engine_agents,
    _collect_package_agents,
    _extract_profile_summary,
    _read_agent_summary,
    _render_agents_md,
    _render_clinerules,
    _render_plugin_agents_md,
    _render_project_profile_template,
)
from spark.workspace import (  # noqa: E402,F401
    WorkspaceLocator,
    _default_update_policy,
    _default_update_policy_payload,
    _normalize_update_mode,
    _read_update_policy_payload,
    _update_policy_path,
    _validate_update_mode,
    _write_update_policy_payload,
)
from spark.inventory import (  # noqa: E402,F401
    EngineInventory,
    FrameworkInventory,
    build_workspace_info,
)
from spark.boot import (  # noqa: E402,F401
    SparkFrameworkEngine,
    _build_app,
    resolve_runtime_dir,
)

# ---------------------------------------------------------------------------
# FastMCP import guard
# ---------------------------------------------------------------------------
try:
    from mcp.server.fastmcp import FastMCP
except ImportError as _import_exc:
    _log.critical(
        "mcp library not installed. Run: pip install mcp  (Python 3.10+ required)"
    )
    raise SystemExit(1) from _import_exc

# ---------------------------------------------------------------------------
# Data models — moved to spark.core.models (re-exported in header)
# ---------------------------------------------------------------------------


# MergeEngine moved to spark.merge.engine (re-exported in header).


# Utility helpers _utc_now


# Utility helpers _utc_now / _format_utc_timestamp / _parse_utc_timestamp /
# _sha256_text moved to spark.core.utils (re-exported in header).


# Update policy helpers (_default_update_policy, _default_update_policy_payload,
# _update_policy_path, _normalize_update_mode, _validate_update_mode,
# _read_update_policy_payload, _write_update_policy_payload)
# moved to spark.workspace.policy (re-exported in header).

# ---------------------------------------------------------------------------
# WorkspaceLocator
# ---------------------------------------------------------------------------


# WorkspaceLocator moved to spark.workspace.locator (re-exported in header).

# ---------------------------------------------------------------------------
# Standalone parsers
# ---------------------------------------------------------------------------

# Pre-compiled patterns _FM_INLINE_LIST_RE / _FM_BLOCK_ITEM_RE / _SEMVER_RE and
# parse_markdown_frontmatter moved to spark.core.utils (re-exported in header).


# Helpers _extract_version_from_changelog / _normalize_string_list /
# _parse_semver_triplet / _is_engine_version_compatible / _is_v3_package /
# _resolve_dependency_update_order moved to spark.core.utils
# (re-exported in header). _V3_LIFECYCLE_MIN_ENGINE_VERSION lives there as well.


# Validators / merge-text helpers moved to spark.merge.validators
# (re-exported in header).


# SCF section helpers moved to spark.merge.sections (re-exported in header).


# ---------------------------------------------------------------------------
# FrameworkInventory
# ---------------------------------------------------------------------------


# FrameworkInventory moved to spark.inventory.framework (re-exported in header).

# ---------------------------------------------------------------------------
# EngineInventory (v2.4.0 — engine-hosted skills and instructions)
# ---------------------------------------------------------------------------


# EngineInventory moved to spark.inventory.engine (re-exported in header).

# ---------------------------------------------------------------------------
# workspace-info builder
# ---------------------------------------------------------------------------


# build_workspace_info moved to spark.inventory.framework (re-exported in header).

# ---------------------------------------------------------------------------
# ManifestManager (A3 — installation manifest)
# ---------------------------------------------------------------------------

# Manifest schema constants moved to spark.core.constants (re-exported in header).


# _resolve_package_version / _get_registry_min_engine_version /
# _build_registry_package_summary moved to spark.packages.registry_summary
# (re-exported in header).


# ManifestManager moved to spark.manifest.manifest (re-exported in header).


# SnapshotManager moved to spark.manifest.snapshots (re-exported in header).


# _normalize_remote_file_record / _scf_diff_workspace / _scf_backup_workspace
# moved to spark.manifest (re-exported in header).


# MergeSessionManager moved to spark.merge.sessions (re-exported in header).


# ---------------------------------------------------------------------------
# RegistryClient (A4 — package registry)
# ---------------------------------------------------------------------------

# Registry endpoint constants moved to spark.core.constants (re-exported in header).


# RegistryClient moved to spark.registry.client (re-exported in header).


# ---------------------------------------------------------------------------
# Migration v2.x -> v3.0 helpers (Phase 0 - scf_migrate_workspace)


# ---------------------------------------------------------------------------
# Migration v2.x -> v3.0 helpers (Phase 0 - scf_migrate_workspace)
# ---------------------------------------------------------------------------


# Migration v2.x->v3.0 helpers (constants, classifier, MigrationPlan, MigrationPlanner)
# moved to spark.workspace.migration (re-exported in header).


# ---------------------------------------------------------------------------
# Phase 6 — Bootstrap v3 asset rendering (AGENTS.md, .clinerules, profile)
# ---------------------------------------------------------------------------


# Phase 6 assets (templates, rendering, collectors, _apply_phase6_assets)
# moved to spark.assets (re-exported in header).


# ---------------------------------------------------------------------------
# v3 package lifecycle helpers — install / update / remove store-based
# ---------------------------------------------------------------------------


# v3_store helpers moved to spark.registry.v3_store (re-exported in header).


# v3 lifecycle helpers (_install_package_v3_into_store, _remove_package_v3_from_store,
# _list_orphan_overrides_for_package, _v3_overrides_blocking_update) moved to
# spark.packages.lifecycle (re-exported in header).


# ---------------------------------------------------------------------------
# PackageResourceStore (v3.0) — deposito centralizzato file di pacchetto
# ---------------------------------------------------------------------------


# Constant _RESOURCE_TYPES moved to spark.core.constants (re-exported in header).
# PackageResourceStore + _resource_filename_candidates moved to
# spark.registry.store (re-exported in header).


# ---------------------------------------------------------------------------
# McpResourceRegistry (v3.0)


# ---------------------------------------------------------------------------
# McpResourceRegistry (v3.0) — indice URI -> (engine_path, override_path)
# ---------------------------------------------------------------------------


# McpResourceRegistry moved to spark.registry.mcp (re-exported in header).


# SparkFrameworkEngine moved to spark.boot.engine (re-exported in header).



# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------



if __name__ == "__main__":
    _build_app(engine_root=Path(__file__).resolve().parent).run(transport="stdio")
