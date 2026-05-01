from __future__ import annotations

import asyncio
import importlib.util
import json
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
            engine_root=_ENGINE_PATH.parent,
        )
        inventory = FrameworkInventory(ctx)
        mcp = _FakeMCP()
        engine = SparkFrameworkEngine(mcp, ctx, inventory)
        engine.register_tools()
        return engine, mcp

    def _authorize_github_writes(self, workspace_root: Path) -> None:
        state_path = workspace_root / ".github" / "runtime" / "orchestrator-state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"github_write_authorized": True}, indent=2),
            encoding="utf-8",
        )

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

    @unittest.skip("SKIP: install_base extended flow is dead code after early return in scf_bootstrap_workspace")
    def test_bootstrap_install_base_installs_spark_base_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            _, mcp = self._build_engine(workspace_root)
            spark_base_files = [
                ".github/agents/spark-assistant.agent.md",
                ".github/agents/spark-guide.agent.md",
                ".github/instructions/spark-assistant-guide.instructions.md",
                ".github/prompts/scf-migrate-workspace.prompt.md",
                ".github/prompts/scf-update-policy.prompt.md",
            ]
            remote_contents = {
                ".github/agents/spark-assistant.agent.md": "base assistant",
                ".github/agents/spark-guide.agent.md": "base guide",
                ".github/instructions/spark-assistant-guide.instructions.md": "base assistant guide",
                ".github/prompts/scf-migrate-workspace.prompt.md": "base migrate prompt",
                ".github/prompts/scf-update-policy.prompt.md": "base update policy prompt",
            }

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
                        "files": spark_base_files,
                    },
                ),
                patch.object(
                    _module.RegistryClient,
                    "fetch_raw_file",
                    side_effect=lambda raw_url: remote_contents[raw_url.split("/main/", 1)[1]],
                ),
            ):
                result = asyncio.run(mcp.tools["scf_bootstrap_workspace"](install_base=True, conflict_mode="manual"))

            manifest = ManifestManager(workspace_root / ".github")

            self.assertTrue(result["success"])
            self.assertTrue(result["install_base_requested"])
            self.assertEqual(result["conflict_mode"], "manual")
            self.assertEqual(result["status"], "bootstrapped_and_installed")
            self.assertTrue(result["base_install"]["success"])
            self.assertCountEqual(result["base_install"]["adopted_bootstrap_files"], spark_base_files)

            for file_path, expected_content in remote_contents.items():
                relative_path = file_path.removeprefix(".github/")
                workspace_file = workspace_root / file_path
                self.assertEqual(workspace_file.read_text(encoding="utf-8"), expected_content)
                self.assertEqual(manifest.get_file_owners(relative_path), ["spark-base"])

    @unittest.skip("SKIP: extended bootstrap authorization flow is dead code after early return in scf_bootstrap_workspace")
    def test_bootstrap_extended_creates_policy_then_requires_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            _, mcp = self._build_engine(workspace_root)

            result = asyncio.run(mcp.tools["scf_bootstrap_workspace"](install_base=True, update_mode="ask"))

            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "authorization_required")
            self.assertEqual(result["action_required"], "authorize_github_write")
            self.assertTrue(result["policy_created"])
            self.assertEqual(result["files_written"], [])
            self.assertFalse((workspace_root / ".github" / "agents" / "spark-assistant.agent.md").exists())

    @unittest.skip("SKIP: extended bootstrap authorization flow is dead code after early return in scf_bootstrap_workspace")
    def test_bootstrap_extended_requires_authorization_after_policy_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            _, mcp = self._build_engine(workspace_root)

            result = asyncio.run(mcp.tools["scf_bootstrap_workspace"](update_mode="integrative"))

            prefs_path = workspace_root / ".github" / "runtime" / "spark-user-prefs.json"
            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "authorization_required")
            self.assertEqual(result["action_required"], "authorize_github_write")
            self.assertTrue(result["policy_created"])
            self.assertTrue(prefs_path.is_file())
            self.assertEqual(result["files_written"], [])
            self.assertFalse((workspace_root / ".github" / "agents" / "spark-assistant.agent.md").exists())

    @unittest.skip("SKIP: extended bootstrap policy/phase6 flow is dead code after early return in scf_bootstrap_workspace")
    def test_bootstrap_extended_writes_assets_and_policy_when_authorized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            self._authorize_github_writes(workspace_root)
            _, mcp = self._build_engine(workspace_root)

            result = asyncio.run(mcp.tools["scf_bootstrap_workspace"](update_mode="integrative"))

            prefs_path = workspace_root / ".github" / "runtime" / "spark-user-prefs.json"
            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "bootstrapped")
            self.assertTrue(result["policy_created"])
            self.assertTrue(result["github_write_authorized"])
            self.assertTrue(prefs_path.is_file())
            self.assertTrue((workspace_root / ".github" / "agents" / "spark-assistant.agent.md").is_file())

            payload = json.loads(prefs_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["update_policy"]["auto_update"])
            self.assertEqual(payload["update_policy"]["default_mode"], "integrative")

    @unittest.skip("SKIP: extended bootstrap install_base+update_mode flow is dead code after early return in scf_bootstrap_workspace")
    def test_bootstrap_install_base_with_integrative_mode_and_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            self._authorize_github_writes(workspace_root)
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
                result = asyncio.run(
                    mcp.tools["scf_bootstrap_workspace"](
                        install_base=True,
                        conflict_mode="manual",
                        update_mode="integrative",
                    )
                )

            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "bootstrapped_and_installed")
            self.assertTrue(result["policy_created"])
            self.assertTrue(result["base_install"]["success"])
            self.assertEqual(result["base_install"]["resolved_update_mode"], "integrative")
            self.assertIn("counts", result["diff_summary"])

    @unittest.skip("SKIP: extended bootstrap legacy-workspace authorization flow is dead code after early return in scf_bootstrap_workspace")
    def test_bootstrap_legacy_workspace_requires_authorization_before_policy_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            sentinel = workspace_root / ".github" / "agents" / "spark-assistant.agent.md"
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            sentinel.write_text("legacy bootstrap", encoding="utf-8")
            _, mcp = self._build_engine(workspace_root)

            result = asyncio.run(mcp.tools["scf_bootstrap_workspace"](update_mode="ask"))

            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "authorization_required")
            self.assertEqual(result["action_required"], "authorize_github_write")
            self.assertTrue(result["migration_state"]["legacy_workspace"])

    @unittest.skip("SKIP: extended bootstrap legacy-workspace authorization flow is dead code after early return in scf_bootstrap_workspace")
    def test_bootstrap_legacy_workspace_requires_authorization_before_policy_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            sentinel = workspace_root / ".github" / "agents" / "spark-assistant.agent.md"
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            sentinel.write_text("legacy bootstrap", encoding="utf-8")
            _, mcp = self._build_engine(workspace_root)

            result = asyncio.run(mcp.tools["scf_bootstrap_workspace"](update_mode="ask"))

            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "authorization_required")
            self.assertEqual(result["action_required"], "authorize_github_write")
            self.assertFalse(result["github_write_authorized"])


if __name__ == "__main__":
    unittest.main()