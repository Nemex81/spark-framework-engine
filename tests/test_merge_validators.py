"""Unit tests for post-merge validators used by auto and assisted flows."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

validate_completeness = _module.validate_completeness
validate_structural = _module.validate_structural
validate_tool_coherence = _module.validate_tool_coherence
run_post_merge_validators = _module.run_post_merge_validators


class TestMergeValidators(unittest.TestCase):
    def test_validate_structural_when_conflict_markers_present_returns_false(self) -> None:
        ok, message = validate_structural(
            "# Title\n<<<<<<< YOURS\nours\n=======\ntheirs\n>>>>>>> OFFICIAL\n",
            "# Title\nbase\n",
        )

        self.assertFalse(ok)
        self.assertEqual(message, "conflict_markers_present")

    def test_validate_completeness_when_ours_headings_are_preserved_returns_true(self) -> None:
        ours_text = "# Agent\n## Local Rules\nBody\n"
        merged_text = "# Agent\n## Local Rules\nBody\n## Remote Rules\nMore\n"

        ok, message = validate_completeness(merged_text, ours_text)

        self.assertTrue(ok)
        self.assertEqual(message, "")

    def test_validate_tool_coherence_for_agent_frontmatter_requires_ours_tools(self) -> None:
        ours_text = (
            "---\n"
            "tools:\n"
            "  - scf_list_agents\n"
            "  - scf_get_agent\n"
            "---\n"
            "# Agent\n"
        )
        merged_text = (
            "---\n"
            "tools:\n"
            "  - scf_list_agents\n"
            "---\n"
            "# Agent\n"
        )

        ok, message, warning = validate_tool_coherence(merged_text, ours_text)

        self.assertFalse(ok)
        self.assertIn("missing_tools", message)
        self.assertIn("scf_get_agent", message)
        self.assertEqual(warning, "")

    def test_validate_tool_coherence_duplicate_tools_returns_warning_not_error(self) -> None:
        ours_text = (
            "---\n"
            "tools:\n"
            "  - scf_list_agents\n"
            "---\n"
            "# Agent\n"
        )
        merged_text = (
            "---\n"
            "tools:\n"
            "  - scf_list_agents\n"
            "  - scf_list_agents\n"
            "---\n"
            "# Agent\n"
        )

        ok, message, warning = validate_tool_coherence(merged_text, ours_text)

        self.assertTrue(ok)
        self.assertEqual(message, "")
        self.assertIn("duplicate_tools", warning)
        self.assertIn("scf_list_agents", warning)

    def test_run_post_merge_validators_result_items_have_warning_field(self) -> None:
        merged_text = "# Agent\nsome content\n"
        base_text = "# Agent\nbase\n"
        ours_text = "# Agent\nours\n"

        result = run_post_merge_validators(merged_text, base_text, ours_text, "agents/test.md")

        for item in result["results"]:
            self.assertIn("warning", item)
            self.assertIsInstance(item["warning"], str)

    def test_run_post_merge_validators_payload_has_warnings_list(self) -> None:
        merged_text = "# Agent\nsome content\n"
        base_text = "# Agent\nbase\n"
        ours_text = "# Agent\nours\n"

        result = run_post_merge_validators(merged_text, base_text, ours_text, "agents/test.md")

        self.assertIn("warnings", result)
        self.assertIsInstance(result["warnings"], list)

    def test_run_post_merge_validators_duplicate_tools_surfaced_as_warning(self) -> None:
        ours_text = (
            "---\n"
            "tools:\n"
            "  - scf_list_agents\n"
            "---\n"
            "# Agent\n"
        )
        merged_text = (
            "---\n"
            "tools:\n"
            "  - scf_list_agents\n"
            "  - scf_list_agents\n"
            "---\n"
            "# Agent\n"
        )

        result = run_post_merge_validators(merged_text, "# Agent\n", ours_text, "agents/test.agent.md")

        self.assertTrue(result["passed"])
        self.assertIn("passed", result)
        tool_item = next(r for r in result["results"] if r["check"] == "tool_coherence")
        self.assertTrue(tool_item["passed"])
        self.assertEqual(tool_item["message"], "")
        self.assertIn("duplicate_tools", tool_item["warning"])
        self.assertIn("scf_list_agents", tool_item["warning"])
        self.assertTrue(len(result["warnings"]) >= 1)
        self.assertTrue(any("scf_list_agents" in w for w in result["warnings"]))


if __name__ == "__main__":
    unittest.main()