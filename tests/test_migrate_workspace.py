"""Unit tests for MigrationPlanner and _classify_v2_workspace_file (Phase 0)."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

_classify_v2_workspace_file = _module._classify_v2_workspace_file
MigrationPlanner = _module.MigrationPlanner
MigrationPlan = _module.MigrationPlan


class TestClassifyV2WorkspaceFile(unittest.TestCase):
    def test_keep_top_level_files(self) -> None:
        for name in (
            "copilot-instructions.md",
            "project-profile.md",
            ".scf-manifest.json",
            "AGENTS.md",
        ):
            self.assertEqual(_classify_v2_workspace_file(Path(name)), "keep")

    def test_keep_runtime_and_instructions_dirs(self) -> None:
        self.assertEqual(
            _classify_v2_workspace_file(Path("runtime/orchestrator-state.json")),
            "keep",
        )
        self.assertEqual(
            _classify_v2_workspace_file(Path("instructions/python.instructions.md")),
            "keep",
        )

    def test_move_to_override_for_v2_resource_dirs(self) -> None:
        for rel in (
            "agents/code-Agent-Code.agent.md",
            "prompts/scf-list.prompt.md",
            "skills/conventional-commit/SKILL.md",
        ):
            self.assertEqual(
                _classify_v2_workspace_file(Path(rel)),
                "move_to_override",
            )

    def test_delete_generated_files_and_legacy_cache(self) -> None:
        self.assertEqual(
            _classify_v2_workspace_file(Path("AGENTS-master.md")),
            "delete",
        )
        self.assertEqual(
            _classify_v2_workspace_file(Path("FRAMEWORK_CHANGELOG.md")),
            "delete",
        )

    def test_untouched_for_unknown(self) -> None:
        self.assertEqual(
            _classify_v2_workspace_file(Path("custom-folder/notes.md")),
            "untouched",
        )


class TestMigrationPlanner(unittest.TestCase):
    def _populate_v2_workspace(self, root: Path) -> None:
        gh = root / ".github"
        (gh / "agents").mkdir(parents=True)
        (gh / "agents" / "code-Agent-Code.agent.md").write_text("ours", encoding="utf-8")
        (gh / "prompts").mkdir(parents=True)
        (gh / "prompts" / "scf-list.prompt.md").write_text("p", encoding="utf-8")
        (gh / "instructions").mkdir(parents=True)
        (gh / "instructions" / "python.instructions.md").write_text("i", encoding="utf-8")
        (gh / "copilot-instructions.md").write_text("ci", encoding="utf-8")
        (gh / "AGENTS-master.md").write_text("auto-generated", encoding="utf-8")

    def test_analyze_empty_when_no_github(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = MigrationPlanner(root).analyze()
            self.assertTrue(plan.is_empty())
            self.assertEqual(plan.move_to_override, ())
            self.assertEqual(plan.delete, ())

    def test_analyze_classifies_known_v2_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._populate_v2_workspace(root)
            plan = MigrationPlanner(root).analyze()

            move_sources = {src for src, _ in plan.move_to_override}
            self.assertIn("agents/code-Agent-Code.agent.md", move_sources)
            self.assertIn("prompts/scf-list.prompt.md", move_sources)
            self.assertIn("AGENTS-master.md", plan.delete)
            self.assertIn("copilot-instructions.md", plan.keep)
            self.assertIn("instructions/python.instructions.md", plan.keep)

    def test_apply_dry_run_via_is_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            empty_plan = MigrationPlan(
                keep=(), move_to_override=(), delete=(),
                untouched=(), cache_relocate=None,
            )
            report = MigrationPlanner(root).apply(empty_plan)
            self.assertEqual(report["executed"], [])
            self.assertFalse(report["rolled_back"])

    def test_apply_moves_and_deletes_with_backup(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._populate_v2_workspace(root)
            planner = MigrationPlanner(root)
            plan = planner.analyze()
            report = planner.apply(plan)

            self.assertFalse(report["rolled_back"])
            self.assertTrue(
                (root / ".github" / "overrides" / "agents" / "code-Agent-Code.agent.md").is_file()
            )
            self.assertFalse((root / ".github" / "agents" / "code-Agent-Code.agent.md").exists())
            self.assertFalse((root / ".github" / "AGENTS-master.md").exists())
            # backup directory created
            backups = list(root.glob(".github.migrate-backup-*"))
            self.assertEqual(len(backups), 1)
            # original file preserved in backup
            self.assertTrue(
                (backups[0] / "agents" / "code-Agent-Code.agent.md").is_file()
            )

    def test_apply_idempotent_on_already_migrated(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._populate_v2_workspace(root)
            planner = MigrationPlanner(root)
            planner.apply(planner.analyze())
            # second run: nothing left to migrate
            plan2 = planner.analyze()
            self.assertEqual(plan2.move_to_override, ())
            self.assertEqual(plan2.delete, ())

    def test_apply_rollback_on_oserror(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._populate_v2_workspace(root)
            planner = MigrationPlanner(root)
            plan = planner.analyze()

            # poison: replace .github/agents source path with a non-existent target dir
            # by patching Path.replace to raise once
            original_replace = Path.replace
            calls = {"n": 0}

            def fake_replace(self, target):  # type: ignore[no-untyped-def]
                calls["n"] += 1
                if calls["n"] == 1:
                    raise OSError("injected failure")
                return original_replace(self, target)

            Path.replace = fake_replace  # type: ignore[method-assign]
            try:
                report = planner.apply(plan)
            finally:
                Path.replace = original_replace  # type: ignore[method-assign]

            self.assertTrue(report["rolled_back"])
            # rollback restores original .github/agents/...
            self.assertTrue(
                (root / ".github" / "agents" / "code-Agent-Code.agent.md").is_file()
            )

    def test_cache_relocate_when_legacy_cache_present(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github").mkdir()
            (root / ".scf-registry-cache.json").write_text("{}", encoding="utf-8")
            engine_cache = root / "engine-cache"
            planner = MigrationPlanner(root, engine_cache_dir=engine_cache)
            plan = planner.analyze()
            self.assertIsNotNone(plan.cache_relocate)
            report = planner.apply(plan)
            self.assertFalse(report["rolled_back"])
            self.assertTrue((engine_cache / "registry-cache.json").is_file())
            self.assertFalse((root / ".scf-registry-cache.json").exists())


if __name__ == "__main__":
    unittest.main()
