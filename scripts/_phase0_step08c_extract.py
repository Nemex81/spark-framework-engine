"""Phase 0 Step 08-C: extract SparkFrameworkEngine to spark/boot/engine.py.

Reads ``spark-framework-engine.py``, locates the ``SparkFrameworkEngine``
class body (from ``class SparkFrameworkEngine:`` to the ``# Entry point``
section marker), applies 6 surgical string replacements, prepends an import
header, and writes the result to ``spark/boot/engine.py``.

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts/_phase0_step08c_extract.py
"""
from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HUB = REPO_ROOT / "spark-framework-engine.py"
OUT = REPO_ROOT / "spark" / "boot" / "engine.py"

# Marker lines to locate class boundaries
CLASS_START_MARKER = "class SparkFrameworkEngine:"
CLASS_END_MARKER = "# ---------------------------------------------------------------------------\n# Entry point\n# ---------------------------------------------------------------------------"

# 6 surgical replacements (old, new)
REPLACEMENTS: list[tuple[str, str]] = [
    # 1. _v3_runtime_state method: EngineInventory() → explicit engine_root
    (
        "                EngineInventory().engine_manifest, {}",
        "                EngineInventory(engine_root=self._ctx.engine_root).engine_manifest, {}",
    ),
    # 2. _v3_repopulate_registry method
    (
        "        engine_manifest = EngineInventory().engine_manifest\n        manifest = ManifestManager(self._ctx.github_root)",
        "        engine_manifest = EngineInventory(engine_root=self._ctx.engine_root).engine_manifest\n        manifest = ManifestManager(self._ctx.github_root)",
    ),
    # 3. register_resources: engine_inventory = EngineInventory()
    (
        "        engine_inventory = EngineInventory()\n\n        def _log_alias_once",
        "        engine_inventory = EngineInventory(engine_root=self._ctx.engine_root)\n\n        def _log_alias_once",
    ),
    # 4. _ensure_registry closure
    (
        "                    engine_manifest = EngineInventory().engine_manifest",
        "                    engine_manifest = EngineInventory(engine_root=self._ctx.engine_root).engine_manifest",
    ),
    # 5. scf_bootstrap_workspace first occurrence
    (
        "            engine_github_root = Path(__file__).resolve().parent / \".github\"",
        "            engine_github_root = self._ctx.engine_root / \".github\"",
    ),
]

IMPORT_HEADER = '''"""SparkFrameworkEngine — SPARK Framework Engine.

Extracted to ``spark.boot.engine`` during Phase 0 modular refactoring.
Re-exported from ``spark.boot``.

Surgical changes vs. original hub (all logically equivalent at runtime):
1. ``_v3_runtime_state``: ``EngineInventory()`` → ``EngineInventory(engine_root=self._ctx.engine_root)``
2. ``_v3_repopulate_registry``: same
3. ``register_resources``: same (``engine_inventory = EngineInventory()``)
4. ``_ensure_registry`` closure: same
5+6. ``scf_bootstrap_workspace`` (×2): ``Path(__file__).resolve().parent / ".github"``
     → ``self._ctx.engine_root / ".github"`` (identical value since ctx.engine_root
     is set by WorkspaceLocator which receives Path(__file__).resolve().parent from hub)
"""
from __future__ import annotations

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
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar

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
from spark.merge import (
    MergeEngine,
    MergeSessionManager,
    run_post_merge_validators,
    validate_completeness,
    validate_structural,
    validate_tool_coherence,
)
from spark.merge.sections import (
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
from spark.merge.validators import (
    _MARKDOWN_HEADING_RE,
    _SUPPORTED_CONFLICT_MODES,
    _extract_frontmatter_block,
    _extract_markdown_headings,
    _normalize_merge_text,
    _resolve_disjoint_line_additions,
)
from spark.manifest import (
    ManifestManager,
    SnapshotManager,
    _normalize_remote_file_record,
    _scf_backup_workspace,
    _scf_diff_workspace,
)
from spark.registry import (
    McpResourceRegistry,
    PackageResourceStore,
    RegistryClient,
    _V3_STORE_INSTALLATION_MODE,
    _build_package_raw_url_base,
    _resource_filename_candidates,
    _v3_store_sentinel_file,
)
from spark.workspace import (
    MigrationPlan,
    MigrationPlanner,
    WorkspaceLocator,
    _V2_MIGRATION_DELETE_FILES,
    _V2_MIGRATION_DELETE_PATTERNS,
    _V2_MIGRATION_KEEP_DIRS,
    _V2_MIGRATION_KEEP_FILES,
    _V2_MIGRATION_OVERRIDE_DIRS,
    _classify_v2_workspace_file,
    _default_update_policy,
    _default_update_policy_payload,
    _normalize_update_mode,
    _read_update_policy_payload,
    _update_policy_path,
    _validate_update_mode,
    _write_update_policy_payload,
)
from spark.packages import (
    _build_registry_package_summary,
    _get_registry_min_engine_version,
    _install_package_v3_into_store,
    _list_orphan_overrides_for_package,
    _remove_package_v3_from_store,
    _resolve_package_version,
    _v3_overrides_blocking_update,
)
from spark.assets import (
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
from spark.inventory import EngineInventory, FrameworkInventory

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as _import_exc:
    import logging as _logging
    _logging.getLogger("spark-framework-engine").critical(
        "mcp library not installed. Run: pip install mcp"
    )
    raise SystemExit(1) from _import_exc

_log: logging.Logger = logging.getLogger("spark-framework-engine")

'''


def main() -> None:
    hub_text = HUB.read_text(encoding="utf-8")

    # Find class start
    start_idx = hub_text.find("\n" + CLASS_START_MARKER + "\n")
    if start_idx == -1:
        start_idx = hub_text.find("\n" + CLASS_START_MARKER + "\r\n")
    if start_idx == -1:
        print("ERROR: class SparkFrameworkEngine not found in hub", file=sys.stderr)
        sys.exit(1)
    start_idx += 1  # skip the leading newline

    # Find class end (Entry point section)
    end_marker = "\n# ---------------------------------------------------------------------------\n# Entry point\n# ---------------------------------------------------------------------------\n"
    end_idx = hub_text.find(end_marker, start_idx)
    if end_idx == -1:
        print("ERROR: Entry point marker not found after class start", file=sys.stderr)
        sys.exit(1)

    class_text = hub_text[start_idx:end_idx]

    # Apply surgical replacements
    for old, new in REPLACEMENTS:
        count = class_text.count(old)
        if count == 0:
            print(f"WARNING: replacement target not found:\n  {old!r}", file=sys.stderr)
        elif count > 1:
            print(f"WARNING: replacement target found {count} times (expected 1):\n  {old!r}", file=sys.stderr)
        class_text = class_text.replace(old, new)

    # Write output file
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(IMPORT_HEADER + class_text + "\n", encoding="utf-8")
    print(f"Written: {OUT}")
    print(f"  Class lines: {class_text.count(chr(10))}")


if __name__ == "__main__":
    main()
