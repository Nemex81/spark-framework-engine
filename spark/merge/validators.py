"""Post-merge validators — estratti da spark-framework-engine.py durante Fase 0.

Pure functions per validazione strutturale, completezza heading e coerenza
tools dichiarati nei merge a tre vie.
"""
from __future__ import annotations

import re
from typing import Any

from spark.core.utils import _normalize_string_list, parse_markdown_frontmatter
from spark.merge.engine import MergeEngine

_SUPPORTED_CONFLICT_MODES: set[str] = {"abort", "replace", "manual", "auto", "assisted"}
_MARKDOWN_HEADING_RE: re.Pattern[str] = re.compile(r"(?m)^(#{1,2})\s+(.+?)\s*$")


def _normalize_merge_text(text: str) -> str:
    """Normalize line endings for merge-related comparisons."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _extract_frontmatter_block(text: str) -> str | None:
    """Return the raw frontmatter block when present and closed correctly."""
    normalized = _normalize_merge_text(text)
    if not normalized.startswith("---\n") and normalized != "---":
        return None

    lines = normalized.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "".join(lines[: index + 1])
    return None


def _extract_markdown_headings(text: str) -> list[str]:
    """Extract normalized H1/H2 headings from markdown text."""
    normalized = _normalize_merge_text(text)
    return [match.group(2).strip() for match in _MARKDOWN_HEADING_RE.finditer(normalized)]


def validate_structural(merged_text: str, base_text: str) -> tuple[bool, str, str]:
    """Validate conflict markers, frontmatter delimiters and basic markdown structure."""
    normalized_merged = _normalize_merge_text(merged_text)
    normalized_base = _normalize_merge_text(base_text)
    merge_engine = MergeEngine()

    if merge_engine.has_conflict_markers(normalized_merged):
        return (False, "conflict_markers_present", "")

    base_frontmatter = _extract_frontmatter_block(normalized_base)
    merged_frontmatter = _extract_frontmatter_block(normalized_merged)
    if base_frontmatter is not None and merged_frontmatter is None:
        return (False, "frontmatter_missing_or_unbalanced", "")
    if normalized_merged.startswith("---") and merged_frontmatter is None:
        return (False, "frontmatter_missing_or_unbalanced", "")

    if _extract_markdown_headings(normalized_base) and not _extract_markdown_headings(normalized_merged):
        return (False, "base_headings_removed", "")

    return (True, "", "")


def validate_completeness(merged_text: str, ours_text: str) -> tuple[bool, str, str]:
    """Validate that H1/H2 headings from OURS survive in the merged content."""
    ours_headings = _extract_markdown_headings(ours_text)
    if not ours_headings:
        return (True, "no_h1_h2_headings_in_ours", "")

    merged_headings = {heading.casefold() for heading in _extract_markdown_headings(merged_text)}
    missing = [heading for heading in ours_headings if heading.casefold() not in merged_headings]
    if missing:
        return (False, f"missing_headings: {', '.join(missing)}", "")
    return (True, "", "")


def validate_tool_coherence(merged_text: str, ours_text: str) -> tuple[bool, str, str]:
    """Validate that tools declared in OURS frontmatter remain present after merge."""
    ours_tools = _normalize_string_list(parse_markdown_frontmatter(ours_text).get("tools", []))
    if not ours_tools:
        return (True, "tools_block_not_applicable", "")

    merged_tools = _normalize_string_list(parse_markdown_frontmatter(merged_text).get("tools", []))
    if not merged_tools:
        return (False, "merged_tools_block_missing", "")

    missing = [tool for tool in ours_tools if tool not in merged_tools]
    if missing:
        return (False, f"missing_tools: {', '.join(missing)}", "")

    duplicates = sorted({tool for tool in merged_tools if merged_tools.count(tool) > 1})
    if duplicates:
        return (True, "", f"duplicate_tools: {', '.join(duplicates)}")
    return (True, "", "")


def run_post_merge_validators(
    merged_text: str,
    base_text: str,
    ours_text: str,
    file_rel: str,
) -> dict[str, Any]:
    """Run all post-merge validators and return a structured result."""
    results: list[dict[str, Any]] = []

    structural_ok, structural_msg, structural_warning = validate_structural(merged_text, base_text)
    results.append(
        {
            "check": "structural",
            "passed": structural_ok,
            "message": structural_msg,
            "warning": structural_warning,
        }
    )

    completeness_ok, completeness_msg, completeness_warning = validate_completeness(merged_text, ours_text)
    results.append(
        {
            "check": "completeness",
            "passed": completeness_ok,
            "message": completeness_msg,
            "warning": completeness_warning,
        }
    )

    if file_rel.endswith(".agent.md"):
        tool_ok, tool_msg, tool_warning = validate_tool_coherence(merged_text, ours_text)
        results.append(
            {
                "check": "tool_coherence",
                "passed": tool_ok,
                "message": tool_msg,
                "warning": tool_warning,
            }
        )

    warnings = [item["warning"] for item in results if item.get("warning")]
    return {
        "passed": all(bool(item.get("passed")) for item in results),
        "results": results,
        "warnings": warnings,
    }


def _resolve_disjoint_line_additions(base_text: str, ours_text: str, theirs_text: str) -> str | None:
    """Combine simple prefix/suffix additions around the unchanged BASE text."""
    normalized_base = _normalize_merge_text(base_text)
    normalized_ours = _normalize_merge_text(ours_text)
    normalized_theirs = _normalize_merge_text(theirs_text)

    if not normalized_base:
        return None

    ours_index = normalized_ours.find(normalized_base)
    theirs_index = normalized_theirs.find(normalized_base)
    if ours_index < 0 or theirs_index < 0:
        return None

    ours_prefix = normalized_ours[:ours_index]
    ours_suffix = normalized_ours[ours_index + len(normalized_base) :]
    theirs_prefix = normalized_theirs[:theirs_index]
    theirs_suffix = normalized_theirs[theirs_index + len(normalized_base) :]

    if ours_prefix and theirs_prefix and ours_prefix != theirs_prefix:
        return None
    if ours_suffix and theirs_suffix and ours_suffix != theirs_suffix:
        return None
    if ours_prefix == theirs_prefix and ours_suffix == theirs_suffix:
        return None

    merged_prefix = ours_prefix or theirs_prefix
    merged_suffix = ours_suffix or theirs_suffix
    return f"{merged_prefix}{normalized_base}{merged_suffix}"
