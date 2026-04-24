from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

FrameworkInventory: Any = _module.FrameworkInventory
ManifestManager: Any = _module.ManifestManager
SnapshotManager: Any = _module.SnapshotManager
SparkFrameworkEngine: Any = _module.SparkFrameworkEngine
WorkspaceContext: Any = _module.WorkspaceContext


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self):
        def _decorator(func):
            self.tools[func.__name__] = func
            return func

        return _decorator

    def resource(self, *_args, **_kwargs):
        def _decorator(func):
            return func

        return _decorator


class TestBootstrapWorkspace(unittest.TestCase):
    def _build_engine(self, workspace_root: Path) -> tuple[Any, _FakeMCP]:
        ctx = WorkspaceContext(
            workspace_root=workspace_root,
            github_root=workspace_root / ".github",
            engine_root=workspace_root / "spark-framework-engine",
        )
        inventory = FrameworkInventory(ctx)
        mcp = _FakeMCP()
        engine = SparkFrameworkEngine(mcp, ctx, inventory)
        engine.register_tools()
        return engine, mcp

    def test_bootstrap_copies_prompts_agent_and_guide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            _, mcp = self._build_engine(workspace_root)
            expected_written_files = len(list((_ENGINE_PATH.parent / ".github" / "prompts").glob("scf-*.prompt.md"))) + 3

            result = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())

            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "bootstrapped")
            self.assertTrue((workspace_root / ".github" / "agents" / "spark-assistant.agent.md").is_file())
            self.assertTrue((workspace_root / ".github" / "agents" / "spark-guide.agent.md").is_file())
            self.assertTrue((workspace_root / ".github" / "instructions" / "spark-assistant-guide.instructions.md").is_file())
            self.assertEqual(len(result["files_written"]), expected_written_files)

    def test_bootstrap_repairs_missing_guide_when_agent_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            agent_path = workspace_root / ".github" / "agents" / "spark-assistant.agent.md"
            agent_path.parent.mkdir(parents=True, exist_ok=True)
            agent_path.write_text("existing agent", encoding="utf-8")

            _, mcp = self._build_engine(workspace_root)

            result = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())

            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "bootstrapped")
            self.assertTrue((workspace_root / ".github" / "instructions" / "spark-assistant-guide.instructions.md").is_file())
            self.assertIn(".github/agents/spark-assistant.agent.md", result["preserved"])

    def test_bootstrap_idempotent_manifest_sync(self) -> None:
        """Second bootstrap on an already-populated workspace must keep the manifest in sync.

        Scenario: first run copies all files and writes the manifest. The manifest is then
        deleted to simulate a corrupt/missing state. The second run finds all files already
        present with identical SHA-256, skips them, but must still call upsert_many so that
        manifest.get_installed_versions() returns 'scf-engine-bootstrap' after both runs.
        """
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            _, mcp = self._build_engine(workspace_root)

            # First bootstrap — copies all files and writes the manifest.
            result1 = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())
            self.assertTrue(result1["success"])

            manifest_path = workspace_root / ".github" / ".scf-manifest.json"
            self.assertTrue(manifest_path.is_file(), "Manifest must exist after first bootstrap")

            snapshots = SnapshotManager(
                workspace_root / ".github" / "runtime" / "snapshots"
            )
            self.assertTrue(
                snapshots.snapshot_exists(
                    "scf-engine-bootstrap",
                    "agents/spark-assistant.agent.md",
                )
            )

            # Simulate manifest loss (corrupt / deleted externally).
            manifest_path.unlink()
            self.assertFalse(manifest_path.is_file())
            deleted_snapshots = snapshots.delete_package_snapshots("scf-engine-bootstrap")
            self.assertIn("agents/spark-assistant.agent.md", deleted_snapshots)

            # Second bootstrap — all files already present with identical SHA-256.
            # The manifest must be re-populated for files with matching hashes.
            result2 = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())
            self.assertTrue(result2["success"])

            # The manifest must now exist again and track the engine bootstrap package.
            self.assertTrue(manifest_path.is_file(), "Manifest must be recreated after second bootstrap")
            ManifestManager = _module.ManifestManager
            manifest = ManifestManager(workspace_root / ".github")
            versions = manifest.get_installed_versions()
            self.assertIn(
                "scf-engine-bootstrap",
                versions,
                "manifest must track scf-engine-bootstrap after idempotent bootstrap",
            )
            self.assertTrue(
                snapshots.snapshot_exists(
                    "scf-engine-bootstrap",
                    "agents/spark-assistant.agent.md",
                ),
                "Snapshots must be recreated for identical bootstrap files",
            )

    def test_bootstrap_returns_already_bootstrapped_when_sentinel_tracked_and_matching(self) -> None:
        """status='already_bootstrapped' when sentinel is tracked with matching SHA."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            _, mcp = self._build_engine(workspace_root)

            # First bootstrap writes all files and manifest.
            result1 = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())
            self.assertEqual(result1["status"], "bootstrapped")

            # Second bootstrap — sentinel tracked, SHA still matches.
            result2 = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())
            self.assertTrue(result2["success"])
            self.assertEqual(result2["status"], "already_bootstrapped")
            self.assertEqual(result2["files_written"], [])
            self.assertEqual(result2["preserved"], [])

    def test_bootstrap_returns_user_modified_when_sentinel_tracked_and_modified(self) -> None:
        """status='user_modified' when sentinel is tracked but user has modified it."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            _, mcp = self._build_engine(workspace_root)

            # First bootstrap.
            result1 = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())
            self.assertEqual(result1["status"], "bootstrapped")

            # Modify the sentinel on disk to simulate user edit.
            sentinel = workspace_root / ".github" / "agents" / "spark-assistant.agent.md"
            sentinel.write_text("# user modified content", encoding="utf-8")

            # Second bootstrap — sentinel tracked but SHA mismatch.
            result2 = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())
            self.assertTrue(result2["success"])
            self.assertEqual(result2["status"], "user_modified")
            self.assertIn("agents/spark-assistant.agent.md", result2["preserved"])
            self.assertEqual(result2["files_written"], [])
            # User modification preserved.
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "# user modified content")

    def test_bootstrap_does_not_retrack_spark_guide_when_owned_by_spark_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            _, mcp = self._build_engine(workspace_root)
            manifest = ManifestManager(workspace_root / ".github")

            first = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())
            self.assertEqual(first["status"], "bootstrapped")

            guide_path = workspace_root / ".github" / "agents" / "spark-guide.agent.md"
            manifest.remove_owner_entries("scf-engine-bootstrap", ["agents/spark-guide.agent.md"])
            manifest.upsert_many("spark-base", "1.2.0", [("agents/spark-guide.agent.md", guide_path)])
            guide_path.unlink()

            sentinel = workspace_root / ".github" / "agents" / "spark-assistant.agent.md"
            sentinel.unlink()

            second = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())
            self.assertEqual(second["status"], "bootstrapped")
            self.assertEqual(manifest.get_file_owners("agents/spark-guide.agent.md"), ["spark-base"])

    def test_bootstrap_install_base_installs_spark_base_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            _, mcp = self._build_engine(workspace_root)

            with (
                patch.object(
                    _module.RegistryClient,
                    "list_packages",
                    return_value=[
                        {
                            "id": "spark-base",
                            "description": "SPARK Base Layer",
                            "repo_url": "https://github.com/example/spark-base",
                            "latest_version": "1.2.0",
                            "status": "stable",
                        }
                    ],
                ),
                patch.object(
                    _module.RegistryClient,
                    "fetch_package_manifest",
                    return_value={
                        "package": "spark-base",
                        "version": "1.2.0",
                        "min_engine_version": "1.0.0",
                        "dependencies": [],
                        "conflicts": [],
                        "file_ownership_policy": "error",
                        "files": [".github/agents/spark-guide.agent.md"],
                    },
                ),
                patch.object(_module.RegistryClient, "fetch_raw_file", return_value="base guide"),
            ):
                result = asyncio.run(mcp.tools["scf_bootstrap_workspace"](install_base=True))

            manifest = ManifestManager(workspace_root / ".github")
            guide_path = workspace_root / ".github" / "agents" / "spark-guide.agent.md"

            self.assertTrue(result["success"])
            self.assertTrue(result["install_base_requested"])
            self.assertEqual(result["status"], "bootstrapped_and_installed")
            self.assertTrue(result["base_install"]["success"])
            self.assertEqual(guide_path.read_text(encoding="utf-8"), "base guide")
            self.assertEqual(manifest.get_file_owners("agents/spark-guide.agent.md"), ["spark-base"])


if __name__ == "__main__":
    unittest.main()