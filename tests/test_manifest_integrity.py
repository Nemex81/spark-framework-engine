"""Unit tests for runtime manifest integrity verification."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Coroutine, cast
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


class TestManifestIntegrity(unittest.TestCase):
    def _make_context(self, workspace_root: Path) -> object:
        return WorkspaceContext(
            workspace_root=workspace_root,
            github_root=workspace_root / ".github",
            engine_root=workspace_root / "spark-framework-engine",
        )

    def _sha256(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _entry(self, file_rel: str, package: str, sha256: str, version: str = "1.0.0") -> dict[str, str]:
        return {
            "file": file_rel,
            "package": package,
            "package_version": version,
            "installed_at": "2026-03-31T00:00:00Z",
            "sha256": sha256,
        }

    def test_verify_integrity_reports_ok_and_orphan_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            tracked_file = github_root / "agents" / "tracked.md"
            orphan_file = github_root / "notes.md"
            github_root.mkdir(parents=True)
            tracked_file.parent.mkdir(parents=True)
            tracked_file.write_text("tracked", encoding="utf-8")
            orphan_file.write_text("orphan", encoding="utf-8")
            (github_root / ".scf-registry-cache.json").write_text("{}", encoding="utf-8")

            manager = ManifestManager(github_root)
            manager.save([
                self._entry("agents/tracked.md", "pkg-a", self._sha256("tracked")),
            ])

            report = manager.verify_integrity()

            self.assertEqual(report["ok"], ["agents/tracked.md"])
            self.assertEqual(report["missing"], [])
            self.assertEqual(report["modified"], [])
            self.assertEqual(report["duplicate_owners"], [])
            # notes.md has no spark: true → classified as user_file, not orphan_candidate
            self.assertEqual(report["orphan_candidates"], [])
            self.assertIn("notes.md", report["user_files"])

    def test_verify_integrity_reports_missing_modified_and_duplicate_owners(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            github_root.mkdir(parents=True)
            modified_file = github_root / "agents" / "modified.md"
            duplicate_file = github_root / "skills" / "shared.skill.md"
            modified_file.parent.mkdir(parents=True)
            duplicate_file.parent.mkdir(parents=True)
            modified_file.write_text("current", encoding="utf-8")
            duplicate_file.write_text("shared", encoding="utf-8")

            manager = ManifestManager(github_root)
            manager.save(
                [
                    self._entry("agents/missing.md", "pkg-a", self._sha256("missing")),
                    self._entry("agents/modified.md", "pkg-a", self._sha256("original")),
                    self._entry("skills/shared.skill.md", "pkg-a", self._sha256("shared")),
                    self._entry("skills/shared.skill.md", "pkg-b", self._sha256("shared")),
                ]
            )

            report = manager.verify_integrity()

            self.assertEqual(report["missing"], ["agents/missing.md"])
            self.assertEqual(report["modified"], ["agents/modified.md"])
            self.assertEqual(report["ok"], ["skills/shared.skill.md", "skills/shared.skill.md"])
            self.assertEqual(
                report["duplicate_owners"],
                [
                    {
                        "file": "skills/shared.skill.md",
                        "owners": ["pkg-a", "pkg-b"],
                        "entry_count": 2,
                    }
                ],
            )

    def test_scf_verify_workspace_returns_structured_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            tracked_file = github_root / "instructions" / "rule.instructions.md"
            tracked_file.parent.mkdir(parents=True)
            tracked_file.write_text("rule", encoding="utf-8")

            manager = ManifestManager(github_root)
            manager.save(
                [
                    self._entry(
                        "instructions/rule.instructions.md",
                        "pkg-a",
                        self._sha256("rule"),
                    ),
                ]
            )

            context = self._make_context(workspace_root)
            inventory = FrameworkInventory(context)
            fake_mcp = FakeMCP()
            engine = SparkFrameworkEngine(fake_mcp, context, inventory)
            engine.register_tools()

            verify_workspace = cast(
                Callable[[], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_verify_workspace"],
            )
            result: dict[str, Any] = asyncio.run(verify_workspace())

            self.assertTrue(result["summary"]["is_clean"])
            self.assertEqual(result["ok"], ["instructions/rule.instructions.md"])
            self.assertEqual(result["missing"], [])
            self.assertEqual(result["modified"], [])
            self.assertEqual(result["duplicate_owners"], [])
            self.assertEqual(result["orphan_candidates"], [])


if __name__ == "__main__":
    unittest.main()
