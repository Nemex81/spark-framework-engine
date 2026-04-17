"""Unit tests for OWN-B update policy tools and diff/backup utilities."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Coroutine
from unittest.mock import MagicMock

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

FrameworkInventory = _module.FrameworkInventory
ManifestManager = _module.ManifestManager
SparkFrameworkEngine = _module.SparkFrameworkEngine
WorkspaceContext = _module.WorkspaceContext
_scf_backup_workspace = _module._scf_backup_workspace
_scf_diff_workspace = _module._scf_diff_workspace


class FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Coroutine[Any, Any, dict[str, Any]]]] = {}

    def tool(
        self,
    ) -> Callable[
        [Callable[..., Coroutine[Any, Any, dict[str, Any]]]],
        Callable[..., Coroutine[Any, Any, dict[str, Any]]],
    ]:
        def decorator(
            func: Callable[..., Coroutine[Any, Any, dict[str, Any]]],
        ) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
            self.tools[func.__name__] = func
            return func

        return decorator


class TestUpdatePolicy(unittest.TestCase):
    def _sha256(self, content: str) -> str:
        return _module._sha256_text(content)

    def _entry(self, file_rel: str, package: str, content: str, version: str) -> dict[str, str]:
        return {
            "file": file_rel,
            "package": package,
            "package_version": version,
            "installed_at": "2026-04-17T00:00:00Z",
            "sha256": self._sha256(content),
        }

    def _build_engine(self, workspace_root: Path) -> FakeMCP:
        context = WorkspaceContext(
            workspace_root=workspace_root,
            github_root=workspace_root / ".github",
            engine_root=workspace_root / "spark-framework-engine",
        )
        inventory = FrameworkInventory(context)
        fake_mcp = FakeMCP()
        engine = SparkFrameworkEngine(fake_mcp, context, inventory)
        engine.register_tools()
        return fake_mcp

    def test_get_update_policy_returns_default_when_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            fake_mcp = self._build_engine(workspace_root)

            result = asyncio.run(fake_mcp.tools["scf_get_update_policy"]())

            self.assertTrue(result["success"])
            self.assertEqual(result["source"], "default_missing")
            self.assertEqual(result["policy"]["default_mode"], "ask")
            self.assertFalse(result["policy"]["auto_update"])

    def test_get_update_policy_returns_default_when_file_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            prefs_path = workspace_root / ".github" / "runtime" / "spark-user-prefs.json"
            prefs_path.parent.mkdir(parents=True, exist_ok=True)
            prefs_path.write_text("{not-json", encoding="utf-8")
            fake_mcp = self._build_engine(workspace_root)

            result = asyncio.run(fake_mcp.tools["scf_get_update_policy"]())

            self.assertTrue(result["success"])
            self.assertEqual(result["source"], "default_corrupt")
            self.assertEqual(result["policy"]["mode_per_package"], {})

    def test_set_update_policy_creates_file_from_scratch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            fake_mcp = self._build_engine(workspace_root)

            result = asyncio.run(
                fake_mcp.tools["scf_set_update_policy"](
                    True,
                    default_mode="replace",
                    mode_per_package={"spark-base": "conservative"},
                    mode_per_file_role={"agent": "integrative"},
                )
            )

            prefs_path = workspace_root / ".github" / "runtime" / "spark-user-prefs.json"
            self.assertTrue(result["success"])
            self.assertTrue(prefs_path.is_file())
            self.assertEqual(result["policy"]["default_mode"], "replace")
            self.assertEqual(result["policy"]["mode_per_package"], {"spark-base": "conservative"})
            self.assertEqual(result["policy"]["mode_per_file_role"], {"agent": "integrative"})
            self.assertTrue(result["policy"]["changed_by_user"])
            self.assertRegex(result["policy"]["last_changed"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

            saved_payload = json.loads(prefs_path.read_text(encoding="utf-8"))
            self.assertEqual(saved_payload["update_policy"]["default_mode"], "replace")

    def test_set_update_policy_partial_update_preserves_existing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            prefs_path = workspace_root / ".github" / "runtime" / "spark-user-prefs.json"
            prefs_path.parent.mkdir(parents=True, exist_ok=True)
            prefs_path.write_text(
                json.dumps(
                    {
                        "update_policy": {
                            "auto_update": False,
                            "default_mode": "ask",
                            "mode_per_package": {"spark-base": "replace"},
                            "mode_per_file_role": {},
                            "last_changed": "",
                            "changed_by_user": False,
                        }
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            fake_mcp = self._build_engine(workspace_root)

            result = asyncio.run(
                fake_mcp.tools["scf_set_update_policy"](
                    True,
                    mode_per_file_role={"instruction": "conservative"},
                )
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["policy"]["default_mode"], "ask")
            self.assertEqual(result["policy"]["mode_per_package"], {"spark-base": "replace"})
            self.assertEqual(
                result["policy"]["mode_per_file_role"],
                {"instruction": "conservative"},
            )
            self.assertTrue(result["policy"]["auto_update"])

    def test_set_update_policy_rejects_selective_default_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            fake_mcp = self._build_engine(workspace_root)

            result = asyncio.run(
                fake_mcp.tools["scf_set_update_policy"](
                    True,
                    default_mode="selective",
                )
            )

            self.assertFalse(result["success"])
            self.assertIn("default_mode", result["error"])

    def test_diff_workspace_classifies_expected_states(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            (github_root / "agents").mkdir(parents=True)
            (github_root / "instructions").mkdir(parents=True)
            (github_root / "prompts").mkdir(parents=True)

            clean_file = github_root / "agents" / "clean.md"
            modified_file = github_root / "instructions" / "changed.instructions.md"
            unchanged_file = github_root / "prompts" / "same.prompt.md"
            clean_file.write_text("official clean", encoding="utf-8")
            modified_file.write_text("user customized", encoding="utf-8")
            unchanged_file.write_text("same content", encoding="utf-8")

            manifest = ManifestManager(github_root)
            manifest.save(
                [
                    self._entry("agents/clean.md", "spark-base", "official clean", "1.2.0"),
                    self._entry(
                        "instructions/changed.instructions.md",
                        "spark-base",
                        "official old",
                        "1.2.0",
                    ),
                    self._entry("prompts/same.prompt.md", "spark-base", "same content", "1.2.0"),
                ]
            )

            diff = _scf_diff_workspace(
                "spark-base",
                "1.3.0",
                [
                    {"path": ".github/agents/new.md", "content": "brand new"},
                    {
                        "path": ".github/agents/clean.md",
                        "content": "official replacement",
                        "scf_file_role": "agent",
                        "scf_merge_strategy": "replace",
                        "scf_merge_priority": 10,
                    },
                    {
                        "path": ".github/instructions/changed.instructions.md",
                        "content": "official replacement",
                    },
                    {
                        "path": ".github/prompts/same.prompt.md",
                        "content": "same content",
                    },
                ],
                manifest,
            )

            by_file = {entry["file"]: entry for entry in diff}
            self.assertEqual(by_file[".github/agents/new.md"]["status"], "new")
            self.assertEqual(by_file[".github/agents/new.md"]["scf_file_role"], "agent")
            self.assertEqual(by_file[".github/agents/clean.md"]["status"], "updated_clean")
            self.assertFalse(by_file[".github/agents/clean.md"]["user_modified"])
            self.assertEqual(
                by_file[".github/instructions/changed.instructions.md"]["status"],
                "updated_user_modified",
            )
            self.assertTrue(by_file[".github/instructions/changed.instructions.md"]["user_modified"])
            self.assertEqual(by_file[".github/prompts/same.prompt.md"]["status"], "unchanged")

    def test_backup_workspace_creates_timestamped_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            agent_file = github_root / "agents" / "backup.md"
            prompt_file = github_root / "prompts" / "keep.prompt.md"
            agent_file.parent.mkdir(parents=True, exist_ok=True)
            prompt_file.parent.mkdir(parents=True, exist_ok=True)
            agent_file.write_text("agent backup", encoding="utf-8")
            prompt_file.write_text("prompt backup", encoding="utf-8")

            backup_root = _scf_backup_workspace(
                "spark-base",
                [
                    ("agents/backup.md", agent_file),
                    ("prompts/keep.prompt.md", prompt_file),
                ],
            )

            backup_path = Path(backup_root)
            self.assertTrue(backup_path.is_dir())
            self.assertRegex(str(backup_path).replace("\\", "/"), r"/\.github/runtime/backups/\d{8}-\d{6}$")
            self.assertEqual(
                (backup_path / "agents" / "backup.md").read_text(encoding="utf-8"),
                "agent backup",
            )
            self.assertEqual(
                (backup_path / "prompts" / "keep.prompt.md").read_text(encoding="utf-8"),
                "prompt backup",
            )

    def test_register_tools_exposes_update_policy_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            fake_mcp = self._build_engine(workspace_root)

            self.assertIn("scf_get_update_policy", fake_mcp.tools)
            self.assertIn("scf_set_update_policy", fake_mcp.tools)


if __name__ == "__main__":
    unittest.main()