# Modulo assets — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""Public re-exports for the ``spark.assets`` package."""
from __future__ import annotations

from spark.assets.collectors import (
    _collect_engine_agents,
    _collect_package_agents,
    _read_agent_summary,
)
from spark.assets.phase6 import _apply_phase6_assets
from spark.assets.rendering import (
    _agents_index_section_text,
    _extract_profile_summary,
    _render_agents_md,
    _render_clinerules,
    _render_plugin_agents_md,
    _render_project_profile_template,
)
from spark.assets.templates import (
    _AGENTS_INDEX_BEGIN,
    _AGENTS_INDEX_END,
    _CLINERULES_TEMPLATE_HEADER,
    _PROJECT_PROFILE_TEMPLATE,
)

__all__ = [
    "_AGENTS_INDEX_BEGIN",
    "_AGENTS_INDEX_END",
    "_CLINERULES_TEMPLATE_HEADER",
    "_PROJECT_PROFILE_TEMPLATE",
    "_agents_index_section_text",
    "_apply_phase6_assets",
    "_collect_engine_agents",
    "_collect_package_agents",
    "_extract_profile_summary",
    "_read_agent_summary",
    "_render_agents_md",
    "_render_clinerules",
    "_render_plugin_agents_md",
    "_render_project_profile_template",
]
