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

        ok, message = validate_tool_coherence(merged_text, ours_text)

        self.assertFalse(ok)
        self.assertIn("missing_tools", message)
        self.assertIn("scf_get_agent", message)


if __name__ == "__main__":
    unittest.main()