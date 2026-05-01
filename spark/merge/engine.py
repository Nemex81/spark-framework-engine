"""3-way merge engine — estratto da spark-framework-engine.py durante Fase 0.

Compute deterministic 3-way merges with no filesystem or MCP dependencies.
"""
from __future__ import annotations

import re

from spark.core.models import (
    MERGE_STATUS_CLEAN,
    MERGE_STATUS_CONFLICT,
    MERGE_STATUS_IDENTICAL,
    MergeConflict,
    MergeResult,
)


class MergeEngine:
    """Compute a normalized 3-way merge without filesystem or MCP dependencies."""

    OURS_MARKER: str = "<<<<<<< YOURS"
    SEPARATOR_MARKER: str = "======="
    THEIRS_MARKER: str = ">>>>>>> OFFICIAL"

    def diff3_merge(self, base: str, ours: str, theirs: str) -> MergeResult:
        """Merge three text versions using explicit clean-path rules first."""
        normalized_base = self._normalize_newlines(base)
        normalized_ours = self._normalize_newlines(ours)
        normalized_theirs = self._normalize_newlines(theirs)

        if normalized_base == normalized_ours == normalized_theirs:
            return MergeResult(
                status=MERGE_STATUS_IDENTICAL,
                merged_text=normalized_base,
                sections=(normalized_base,),
            )

        if normalized_ours == normalized_theirs:
            return MergeResult(
                status=MERGE_STATUS_CLEAN,
                merged_text=normalized_ours,
                sections=(normalized_ours,),
            )

        if normalized_base == normalized_ours:
            return MergeResult(
                status=MERGE_STATUS_CLEAN,
                merged_text=normalized_theirs,
                sections=(normalized_theirs,),
            )

        if normalized_base == normalized_theirs:
            return MergeResult(
                status=MERGE_STATUS_CLEAN,
                merged_text=normalized_ours,
                sections=(normalized_ours,),
            )

        return self._build_conflict_result(
            base=normalized_base,
            ours=normalized_ours,
            theirs=normalized_theirs,
        )

    def render_with_markers(self, result: MergeResult) -> str:
        """Render a merge result, adding conflict markers when needed."""
        if not result.conflicts:
            return result.merged_text

        rendered_sections: list[str] = []
        for section in result.sections:
            if isinstance(section, MergeConflict):
                rendered_sections.append(self._render_conflict(section))
            else:
                rendered_sections.append(section)
        return "".join(rendered_sections)

    def has_conflict_markers(self, text: str) -> bool:
        """Return True when a text already contains merge markers."""
        normalized_text = self._normalize_newlines(text)
        marker_pattern = re.compile(
            rf"(?m)^({re.escape(self.OURS_MARKER)}|"
            rf"{re.escape(self.SEPARATOR_MARKER)}|{re.escape(self.THEIRS_MARKER)})$"
        )
        return bool(marker_pattern.search(normalized_text))

    def _build_conflict_result(self, base: str, ours: str, theirs: str) -> MergeResult:
        ours_lines = self._split_lines(ours)
        theirs_lines = self._split_lines(theirs)
        base_lines = self._split_lines(base)

        prefix_len = self._shared_prefix_len_threeway(base_lines, ours_lines, theirs_lines)
        suffix_len = self._shared_suffix_len_threeway(
            base_lines,
            ours_lines,
            theirs_lines,
            prefix_len,
        )
        ours_end = len(ours_lines) - suffix_len if suffix_len else len(ours_lines)
        theirs_end = len(theirs_lines) - suffix_len if suffix_len else len(theirs_lines)
        base_end = len(base_lines) - suffix_len if suffix_len else len(base_lines)

        prefix_text = "".join(ours_lines[:prefix_len])
        suffix_text = "".join(ours_lines[len(ours_lines) - suffix_len :]) if suffix_len else ""

        base_start = prefix_len

        conflict = MergeConflict(
            start_line=base_start + 1,
            end_line=max(base_start + 1, base_end),
            base_text="".join(base_lines[base_start:base_end]),
            ours_text="".join(ours_lines[prefix_len:ours_end]),
            theirs_text="".join(theirs_lines[prefix_len:theirs_end]),
        )
        return MergeResult(
            status=MERGE_STATUS_CONFLICT,
            merged_text="",
            conflicts=(conflict,),
            sections=(prefix_text, conflict, suffix_text),
        )

    def _render_conflict(self, conflict: MergeConflict) -> str:
        ours_text = self._ensure_conflict_body_newline(conflict.ours_text)
        theirs_text = self._ensure_conflict_body_newline(conflict.theirs_text)
        return (
            f"{self.OURS_MARKER}\n"
            f"{ours_text}"
            f"{self.SEPARATOR_MARKER}\n"
            f"{theirs_text}"
            f"{self.THEIRS_MARKER}\n"
        )

    @staticmethod
    def _ensure_conflict_body_newline(text: str) -> str:
        if not text or text.endswith("\n"):
            return text
        return f"{text}\n"

    @staticmethod
    def _normalize_newlines(text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n")

    @staticmethod
    def _split_lines(text: str) -> list[str]:
        return text.splitlines(keepends=True)

    @staticmethod
    def _shared_prefix_len(left: list[str], right: list[str]) -> int:
        limit = min(len(left), len(right))
        index = 0
        while index < limit and left[index] == right[index]:
            index += 1
        return index

    @classmethod
    def _shared_prefix_len_threeway(
        cls,
        base_lines: list[str],
        ours_lines: list[str],
        theirs_lines: list[str],
    ) -> int:
        return min(
            cls._shared_prefix_len(base_lines, ours_lines),
            cls._shared_prefix_len(base_lines, theirs_lines),
            cls._shared_prefix_len(ours_lines, theirs_lines),
        )

    @staticmethod
    def _shared_suffix_len(left: list[str], right: list[str], prefix_len: int) -> int:
        max_suffix = min(len(left), len(right)) - prefix_len
        index = 0
        while index < max_suffix and left[-(index + 1)] == right[-(index + 1)]:
            index += 1
        return index

    @classmethod
    def _shared_suffix_len_threeway(
        cls,
        base_lines: list[str],
        ours_lines: list[str],
        theirs_lines: list[str],
        prefix_len: int,
    ) -> int:
        return min(
            cls._shared_suffix_len(base_lines, ours_lines, prefix_len),
            cls._shared_suffix_len(base_lines, theirs_lines, prefix_len),
            cls._shared_suffix_len(ours_lines, theirs_lines, prefix_len),
        )
