"""Unit tests for OWN-C section merge utilities."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

_scf_section_merge = _module._scf_section_merge
_scf_strip_section = _module._scf_strip_section


def _source(priority: int, body: str) -> str:
    return (
        "---\n"
        "spark: true\n"
        f"scf_merge_priority: {priority}\n"
        "---\n\n"
        f"{body}\n"
    )


class TestSectionMerge(unittest.TestCase):
    def test_replace_strategy_new_file_returns_source_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "copilot-instructions.md"

            result = _scf_section_merge(
                _source(20, "## Master\nbody"),
                target,
                "replace",
                "scf-master-codecrafter",
                "2.1.0",
            )

            self.assertIn("## Master", result)
            self.assertIn("scf_merge_priority: 20", result)

    def test_replace_strategy_preserves_existing_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "copilot-instructions.md"
            target.write_text("---\nowner: user\n---\n\nold body\n", encoding="utf-8")

            result = _scf_section_merge(
                _source(20, "## New Body\ncontent"),
                target,
                "replace",
                "scf-master-codecrafter",
                "2.1.0",
            )

            self.assertTrue(result.startswith("---\nowner: user\n---\n"))
            self.assertIn("## New Body", result)
            self.assertNotIn("old body", result)

    def test_merge_sections_new_file_generates_header_and_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "copilot-instructions.md"

            result = _scf_section_merge(
                _source(10, "## Base\nbase rules"),
                target,
                "merge_sections",
                "spark-base",
                "1.2.0",
            )

            self.assertIn("SCF:HEADER", result)
            self.assertIn("# Copilot Instructions — Workspace", result)
            self.assertIn("<!-- SCF:BEGIN:spark-base@1.2.0 -->", result)
            self.assertIn("<!-- SCF:END:spark-base -->", result)

    def test_merge_sections_updates_existing_block_with_prerelease_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "copilot-instructions.md"
            target.write_text(
                "<!-- SCF:HEADER — generato da SPARK Framework Engine -->\n\n"
                "<!-- SCF:BEGIN:scf-master-codecrafter@2.1.0-beta.1 -->\n"
                "---\nscf_merge_priority: 20\n---\n\nold body\n"
                "<!-- SCF:END:scf-master-codecrafter -->\n",
                encoding="utf-8",
            )

            result = _scf_section_merge(
                _source(20, "## Updated\nnew body"),
                target,
                "merge_sections",
                "scf-master-codecrafter",
                "2.1.0",
            )

            self.assertIn("<!-- SCF:BEGIN:scf-master-codecrafter@2.1.0 -->", result)
            self.assertNotIn("2.1.0-beta.1", result)
            self.assertIn("## Updated", result)
            self.assertEqual(result.count("SCF:BEGIN:scf-master-codecrafter@"), 1)

    def test_merge_sections_inserts_new_block_in_priority_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "copilot-instructions.md"
            target.write_text(
                "intro utente\n\n"
                "<!-- SCF:BEGIN:scf-master-codecrafter@2.1.0 -->\n"
                "---\nscf_merge_priority: 20\n---\n\nmaster\n"
                "<!-- SCF:END:scf-master-codecrafter -->\n\n"
                "<!-- SCF:BEGIN:scf-pycode-crafter@2.0.1 -->\n"
                "---\nscf_merge_priority: 30\n---\n\npython\n"
                "<!-- SCF:END:scf-pycode-crafter -->\n\n"
                "footer utente\n",
                encoding="utf-8",
            )

            result = _scf_section_merge(
                _source(10, "## Base\nbase rules"),
                target,
                "merge_sections",
                "spark-base",
                "1.2.0",
            )

            self.assertTrue(result.startswith("intro utente\n\n"))
            self.assertIn("footer utente\n", result)
            base_index = result.index("SCF:BEGIN:spark-base@1.2.0")
            master_index = result.index("SCF:BEGIN:scf-master-codecrafter@2.1.0")
            python_index = result.index("SCF:BEGIN:scf-pycode-crafter@2.0.1")
            self.assertLess(base_index, master_index)
            self.assertLess(master_index, python_index)

    def test_merge_sections_plain_file_preserves_user_text_and_appends_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "copilot-instructions.md"
            target.write_text("note utente\n", encoding="utf-8")

            result = _scf_section_merge(
                _source(20, "## Master\nmaster rules"),
                target,
                "merge_sections",
                "scf-master-codecrafter",
                "2.1.0",
            )

            self.assertTrue(result.startswith("note utente\n\n"))
            self.assertIn("SCF:BEGIN:scf-master-codecrafter@2.1.0", result)

    def test_merge_sections_corrupted_marker_preserves_text_and_appends_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "copilot-instructions.md"
            target.write_text(
                "<!-- SCF:BEGIN:spark-base@1.0.0 -->\ncorrupted without end\n",
                encoding="utf-8",
            )

            result = _scf_section_merge(
                _source(20, "## Master\nmaster rules"),
                target,
                "merge_sections",
                "scf-master-codecrafter",
                "2.1.0",
            )

            self.assertIn("corrupted without end", result)
            self.assertIn("SCF:BEGIN:scf-master-codecrafter@2.1.0", result)

    def test_user_protected_returns_existing_content_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "protected.md"
            target.write_text("utente\n", encoding="utf-8")

            result = _scf_section_merge(
                _source(20, "## Ignored\nignored"),
                target,
                "user_protected",
                "pkg-a",
                "1.0.0",
            )

            self.assertEqual(result, "utente\n")

    def test_strip_section_removes_only_requested_block_in_multi_section_file(self) -> None:
        content = (
            "intro\n\n"
            "<!-- SCF:BEGIN:spark-base@1.2.0 -->\nbase\n<!-- SCF:END:spark-base -->\n\n"
            "<!-- SCF:BEGIN:scf-master-codecrafter@2.1.0 -->\nmaster\n<!-- SCF:END:scf-master-codecrafter -->\n\n"
            "footer\n"
        )

        result = _scf_strip_section(content, "spark-base")

        self.assertIn("intro", result)
        self.assertIn("master", result)
        self.assertIn("footer", result)
        self.assertNotIn("SCF:BEGIN:spark-base", result)
        self.assertNotIn("base\n", result)


if __name__ == "__main__":
    unittest.main()