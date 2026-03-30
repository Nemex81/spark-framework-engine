"""Unit tests for parse_markdown_frontmatter().

Uses unittest (standard library) — no external dependencies required.
The engine module is loaded via importlib to handle the hyphenated filename.
The mcp library is mocked so the tests run even when mcp is not installed.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Load engine module safely (mock mcp to avoid SystemExit if not installed)
# ---------------------------------------------------------------------------

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

# Provide mock stubs for mcp so the module loads without the real package.
for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
# Register in sys.modules before exec so @dataclass can resolve the module namespace.
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

parse_markdown_frontmatter = _module.parse_markdown_frontmatter


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestNoFrontmatter(unittest.TestCase):
    def test_no_separator_returns_empty(self) -> None:
        self.assertEqual(parse_markdown_frontmatter("# Title\nBody text."), {})

    def test_empty_string_returns_empty(self) -> None:
        self.assertEqual(parse_markdown_frontmatter(""), {})

    def test_only_opening_separator_returns_empty(self) -> None:
        self.assertEqual(parse_markdown_frontmatter("---\nno closing separator"), {})

    def test_two_separators_no_content(self) -> None:
        self.assertEqual(parse_markdown_frontmatter("---\n---\nBody here"), {})


class TestScalarValues(unittest.TestCase):
    def test_string_value(self) -> None:
        result = parse_markdown_frontmatter("---\nname: developer\n---\n# Body")
        self.assertEqual(result["name"], "developer")

    def test_boolean_true_variants(self) -> None:
        for val in ("true", "True", "TRUE", "yes", "Yes", "YES"):
            with self.subTest(val=val):
                result = parse_markdown_frontmatter(f"---\nactive: {val}\n---")
                self.assertIs(result["active"], True)

    def test_boolean_false_variants(self) -> None:
        for val in ("false", "False", "FALSE", "no", "No", "NO"):
            with self.subTest(val=val):
                result = parse_markdown_frontmatter(f"---\nactive: {val}\n---")
                self.assertIs(result["active"], False)

    def test_integer_value(self) -> None:
        result = parse_markdown_frontmatter("---\nversion: 3\n---")
        self.assertEqual(result["version"], 3)
        self.assertIsInstance(result["version"], int)

    def test_quoted_string_double(self) -> None:
        result = parse_markdown_frontmatter('---\nname: "my agent"\n---')
        self.assertEqual(result["name"], "my agent")

    def test_quoted_string_single(self) -> None:
        result = parse_markdown_frontmatter("---\nname: 'my agent'\n---")
        self.assertEqual(result["name"], "my agent")

    def test_colon_in_value_preserved(self) -> None:
        result = parse_markdown_frontmatter("---\ntitle: hello: world\n---")
        self.assertEqual(result["title"], "hello: world")

    def test_multiple_scalars(self) -> None:
        content = "---\nname: dev\nrole: builder\nversion: 2\n---"
        result = parse_markdown_frontmatter(content)
        self.assertEqual(result["name"], "dev")
        self.assertEqual(result["role"], "builder")
        self.assertEqual(result["version"], 2)


class TestInlineLists(unittest.TestCase):
    def test_basic_inline_list(self) -> None:
        result = parse_markdown_frontmatter("---\nskills: [python, gamedev]\n---")
        self.assertEqual(result["skills"], ["python", "gamedev"])

    def test_single_item_inline_list(self) -> None:
        result = parse_markdown_frontmatter("---\nskills: [python]\n---")
        self.assertEqual(result["skills"], ["python"])

    def test_inline_list_with_extra_spaces(self) -> None:
        result = parse_markdown_frontmatter("---\nskills: [ python , gamedev ]\n---")
        self.assertEqual(result["skills"], ["python", "gamedev"])

    def test_inline_list_quoted_items(self) -> None:
        result = parse_markdown_frontmatter('---\ntags: ["gamedev", "unity"]\n---')
        self.assertEqual(result["tags"], ["gamedev", "unity"])

    def test_inline_list_adjacent_to_scalar(self) -> None:
        content = "---\nname: dev\nskills: [python, gamedev]\nrole: builder\n---"
        result = parse_markdown_frontmatter(content)
        self.assertEqual(result["skills"], ["python", "gamedev"])
        self.assertEqual(result["name"], "dev")
        self.assertEqual(result["role"], "builder")


class TestBlockLists(unittest.TestCase):
    def test_basic_block_list(self) -> None:
        content = "---\nskills:\n  - python\n  - gamedev\n---"
        result = parse_markdown_frontmatter(content)
        self.assertEqual(result["skills"], ["python", "gamedev"])

    def test_single_item_block_list(self) -> None:
        content = "---\nskills:\n  - python\n---"
        result = parse_markdown_frontmatter(content)
        self.assertEqual(result["skills"], ["python"])

    def test_block_list_followed_by_scalar(self) -> None:
        content = "---\nskills:\n  - python\n  - gamedev\nrole: developer\n---"
        result = parse_markdown_frontmatter(content)
        self.assertEqual(result["skills"], ["python", "gamedev"])
        self.assertEqual(result["role"], "developer")

    def test_scalar_followed_by_block_list(self) -> None:
        content = "---\nrole: developer\nskills:\n  - python\n  - gamedev\n---"
        result = parse_markdown_frontmatter(content)
        self.assertEqual(result["role"], "developer")
        self.assertEqual(result["skills"], ["python", "gamedev"])

    def test_multiple_block_lists(self) -> None:
        content = "---\nskills:\n  - python\ntags:\n  - gamedev\n  - unity\n---"
        result = parse_markdown_frontmatter(content)
        self.assertEqual(result["skills"], ["python"])
        self.assertEqual(result["tags"], ["gamedev", "unity"])

    def test_block_list_quoted_items(self) -> None:
        content = "---\ntags:\n  - 'gamedev'\n  - \"unity\"\n---"
        result = parse_markdown_frontmatter(content)
        self.assertEqual(result["tags"], ["gamedev", "unity"])


class TestMalformedAndIncomplete(unittest.TestCase):
    def test_key_with_empty_value_starts_block_list(self) -> None:
        # key: <nothing> should be treated as an empty block list start
        result = parse_markdown_frontmatter("---\nname:\n---")
        self.assertIn("name", result)
        self.assertIsInstance(result["name"], list)
        self.assertEqual(result["name"], [])

    def test_line_without_colon_is_skipped(self) -> None:
        result = parse_markdown_frontmatter("---\njust a line without colon\nname: test\n---")
        self.assertNotIn("just a line without colon", result)
        self.assertEqual(result["name"], "test")

    def test_comment_line_is_skipped(self) -> None:
        content = "---\n# this is a comment\nname: test\n---"
        result = parse_markdown_frontmatter(content)
        # The comment key should not appear
        self.assertNotIn("# this is a comment", result)
        self.assertEqual(result["name"], "test")

    def test_extra_whitespace_lines_ignored(self) -> None:
        content = "---\n\n   \nname: test\n\n---"
        result = parse_markdown_frontmatter(content)
        self.assertEqual(result["name"], "test")

    def test_frontmatter_with_body_content(self) -> None:
        content = "---\ntype: agent\nname: dev\n---\n# Agent Title\nBody paragraph."
        result = parse_markdown_frontmatter(content)
        self.assertEqual(result["type"], "agent")
        self.assertEqual(result["name"], "dev")
        self.assertNotIn("Agent Title", result)
        self.assertNotIn("Body paragraph.", result)


if __name__ == "__main__":
    unittest.main()
