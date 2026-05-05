"""Unit tests for the Phase 1 MergeEngine core."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

MergeEngine = _module.MergeEngine
MERGE_STATUS_CLEAN = _module.MERGE_STATUS_CLEAN
MERGE_STATUS_CONFLICT = _module.MERGE_STATUS_CONFLICT
MERGE_STATUS_IDENTICAL = _module.MERGE_STATUS_IDENTICAL


class TestMergeEngine(unittest.TestCase):
    """Tests for 3-way merge behavior required by Phase 1."""

    def setUp(self) -> None:
        self.engine = MergeEngine()

    def test_diff3_merge_when_all_versions_match_returns_identical(self) -> None:
        result = self.engine.diff3_merge("alpha\nbeta\n", "alpha\nbeta\n", "alpha\nbeta\n")

        self.assertEqual(result.status, MERGE_STATUS_IDENTICAL)
        self.assertEqual(result.merged_text, "alpha\nbeta\n")
        self.assertEqual(result.conflicts, ())

    def test_diff3_merge_when_both_sides_make_same_change_returns_clean(self) -> None:
        result = self.engine.diff3_merge("alpha\nbeta\n", "alpha\ngamma\n", "alpha\ngamma\n")

        self.assertEqual(result.status, MERGE_STATUS_CLEAN)
        self.assertEqual(result.merged_text, "alpha\ngamma\n")
        self.assertEqual(result.conflicts, ())

    def test_diff3_merge_when_only_ours_changes_returns_ours(self) -> None:
        result = self.engine.diff3_merge("alpha\nbeta\n", "alpha\ngamma\n", "alpha\nbeta\n")

        self.assertEqual(result.status, MERGE_STATUS_CLEAN)
        self.assertEqual(result.merged_text, "alpha\ngamma\n")

    def test_diff3_merge_when_only_theirs_changes_returns_theirs(self) -> None:
        result = self.engine.diff3_merge("alpha\nbeta\n", "alpha\nbeta\n", "alpha\ndelta\n")

        self.assertEqual(result.status, MERGE_STATUS_CLEAN)
        self.assertEqual(result.merged_text, "alpha\ndelta\n")

    def test_diff3_merge_when_changes_diverge_returns_conflict(self) -> None:
        result = self.engine.diff3_merge(
            "alpha\nbeta\nomega\n",
            "alpha\nours\nomega\n",
            "alpha\ntheirs\nomega\n",
        )

        self.assertEqual(result.status, MERGE_STATUS_CONFLICT)
        self.assertEqual(len(result.conflicts), 1)
        self.assertEqual(result.conflicts[0].start_line, 2)
        self.assertEqual(result.conflicts[0].end_line, 2)

    def test_diff3_merge_when_base_has_no_shared_context_keeps_base_coordinates(self) -> None:
        result = self.engine.diff3_merge(
            "x\ny\n",
            "a\nb\nc\n",
            "a\nb\nd\n",
        )

        self.assertEqual(result.status, MERGE_STATUS_CONFLICT)
        self.assertEqual(len(result.conflicts), 1)
        self.assertEqual(result.conflicts[0].start_line, 1)
        self.assertEqual(result.conflicts[0].end_line, 2)
        self.assertEqual(result.conflicts[0].base_text, "x\ny\n")
        self.assertEqual(result.conflicts[0].ours_text, "a\nb\nc\n")
        self.assertEqual(result.conflicts[0].theirs_text, "a\nb\nd\n")

    def test_render_with_markers_when_conflict_returns_expected_text(self) -> None:
        result = self.engine.diff3_merge(
            "alpha\nbeta\nomega\n",
            "alpha\nours\nomega\n",
            "alpha\ntheirs\nomega\n",
        )

        rendered = self.engine.render_with_markers(result)

        self.assertEqual(
            rendered,
            "alpha\n<<<<<<< YOURS\nours\n=======\ntheirs\n>>>>>>> OFFICIAL\nomega\n",
        )

    def test_has_conflict_markers_detects_marker_presence(self) -> None:
        text = "alpha\n<<<<<<< YOURS\nours\n=======\ntheirs\n>>>>>>> OFFICIAL\nomega\n"

        self.assertTrue(self.engine.has_conflict_markers(text))

    def test_has_conflict_markers_when_text_is_clean_returns_false(self) -> None:
        self.assertFalse(self.engine.has_conflict_markers("alpha\nbeta\n"))

    def test_diff3_merge_normalizes_newlines_before_merge(self) -> None:
        result = self.engine.diff3_merge(
            "alpha\r\nbeta\r\n",
            "alpha\r\ngamma\r\n",
            "alpha\r\ngamma\r\n",
        )

        self.assertEqual(result.status, MERGE_STATUS_CLEAN)
        self.assertEqual(result.merged_text, "alpha\ngamma\n")

    def test_diff3_merge_with_empty_strings_returns_identical(self) -> None:
        result = self.engine.diff3_merge("", "", "")

        self.assertEqual(result.status, MERGE_STATUS_IDENTICAL)
        self.assertEqual(result.merged_text, "")
        self.assertEqual(self.engine.render_with_markers(result), "")


if __name__ == "__main__":
    unittest.main()