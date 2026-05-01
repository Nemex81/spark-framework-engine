# Modulo merge — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""Public re-exports for the ``spark.merge`` package."""
from __future__ import annotations

from spark.merge.engine import MergeEngine
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
from spark.merge.sessions import MergeSessionManager
from spark.merge.validators import (
    _MARKDOWN_HEADING_RE,
    _SUPPORTED_CONFLICT_MODES,
    _extract_frontmatter_block,
    _extract_markdown_headings,
    _normalize_merge_text,
    _resolve_disjoint_line_additions,
    run_post_merge_validators,
    validate_completeness,
    validate_structural,
    validate_tool_coherence,
)

__all__ = [
    "MergeEngine",
    "MergeSessionManager",
    "run_post_merge_validators",
    "validate_completeness",
    "validate_structural",
    "validate_tool_coherence",
]
