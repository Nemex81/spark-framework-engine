"""Unit tests for FrameworkInventory.list_skills() dual-format discovery.

Covers legacy flat skills (*.skill.md), standard directory skills (SKILL.md),
name collision precedence, and empty/missing skills directory behaviour.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

FrameworkInventory: Any = _module.FrameworkInventory
WorkspaceContext: Any = _module.WorkspaceContext


class TestFrameworkInventoryListSkills(unittest.TestCase):
    def _build_inventory(self, workspace_root: Path) -> Any:
        ctx = WorkspaceContext(
            workspace_root=workspace_root,
            github_root=workspace_root / ".github",
            engine_root=workspace_root / "spark-framework-engine",
        )
        return FrameworkInventory(ctx)

    def test_discovers_flat_and_standard_formats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / ".github" / "skills"
            skills.mkdir(parents=True)

            (skills / "alpha.skill.md").write_text("---\nname: alpha\n---\nAlpha", encoding="utf-8")
            (skills / "beta").mkdir()
            (skills / "beta" / "SKILL.md").write_text("---\nname: beta\n---\nBeta", encoding="utf-8")

            inv = self._build_inventory(root)
            names = [s.name for s in inv.list_skills()]
            self.assertEqual(names, ["alpha.skill", "beta"])

    def test_flat_format_wins_on_name_collision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / ".github" / "skills"
            skills.mkdir(parents=True)

            flat_file = skills / "foo.skill.md"
            flat_file.write_text("Flat summary", encoding="utf-8")
            (skills / "foo").mkdir()
            (skills / "foo" / "SKILL.md").write_text("Standard summary", encoding="utf-8")

            inv = self._build_inventory(root)
            result = inv.list_skills()
            names = [s.name for s in result]
            self.assertEqual(names, ["foo.skill"])

            foo_entry = result[0]
            self.assertEqual(foo_entry.path, flat_file)

    def test_returns_empty_when_skills_dir_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github").mkdir(parents=True)
            inv = self._build_inventory(root)
            self.assertEqual(inv.list_skills(), [])

    def test_returns_empty_when_skills_dir_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github" / "skills").mkdir(parents=True)
            inv = self._build_inventory(root)
            self.assertEqual(inv.list_skills(), [])


if __name__ == "__main__":
    unittest.main()
