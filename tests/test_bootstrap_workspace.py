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

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

FrameworkInventory: Any = _module.FrameworkInventory
ManifestManager: Any = _module.ManifestManager
SnapshotManager: Any = _module.SnapshotManager
SparkFrameworkEngine: Any = _module.SparkFrameworkEngine
WorkspaceContext: Any = _module.WorkspaceContext
resolve_runtime_dir: Any = _module.resolve_runtime_dir


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
        # Post v3 FIX 2: il bootstrap copia SOLO il perimetro Cat. A definito
        # in ``workspace_files`` del manifest spark-base + 2 sentinel di
        # discovery (AGENTS.md, Agent-Welcome.md).
        # Prompts e instructions operative NON vengono più copiati nel
        # workspace: sono Cat. B serviti via MCP. Il nome del test resta per
        # compat storica ma il contratto verifica il nuovo perimetro.
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            _, mcp = self._build_engine(workspace_root)

            result = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())

            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "bootstrapped")
            # File Cat. A obbligatori (workspace_files del manifest).
            self.assertTrue((workspace_root / ".github" / "copilot-instructions.md").is_file())
            self.assertTrue((workspace_root / ".github" / "project-profile.md").is_file())
            self.assertTrue(
                (workspace_root / ".github" / "instructions" / "spark-assistant-guide.instructions.md").is_file()
            )
            self.assertTrue(
                (workspace_root / ".github" / "instructions" / "framework-guard.instructions.md").is_file()
            )
            # Sentinel di discovery sempre presenti.
            self.assertTrue((workspace_root / ".github" / "AGENTS.md").is_file())
            self.assertTrue((workspace_root / ".github" / "agents" / "Agent-Welcome.md").is_file())
            # Cat. B NON deve finire nel workspace: i prompt non vengono
            # copiati durante il bootstrap.
            prompts_dir = workspace_root / ".github" / "prompts"
            if prompts_dir.is_dir():
                copied_prompts = list(prompts_dir.glob("*.prompt.md"))
                self.assertEqual(
                    copied_prompts,
                    [],
                    f"Bootstrap should not copy prompts (Cat. B), found: {copied_prompts}",
                )

    def test_bootstrap_repairs_missing_guide_when_agent_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            agent_path = workspace_root / ".github" / "agents" / "Agent-Welcome.md"
            agent_path.parent.mkdir(parents=True, exist_ok=True)
            agent_path.write_text("existing agent", encoding="utf-8")

            _, mcp = self._build_engine(workspace_root)

            result = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())

            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "bootstrapped")
            self.assertTrue((workspace_root / ".github" / "instructions" / "spark-assistant-guide.instructions.md").is_file())
            self.assertIn(".github/agents/Agent-Welcome.md", result["preserved"])

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

            runtime_dir = resolve_runtime_dir(_ENGINE_PATH.parent, workspace_root)
            snapshots = SnapshotManager(runtime_dir / "snapshots")
            self.assertTrue(
                snapshots.snapshot_exists(
                    "scf-engine-bootstrap",
                    "agents/Agent-Welcome.md",
                )
            )

            # Simulate manifest loss (corrupt / deleted externally).
            manifest_path.unlink()
            self.assertFalse(manifest_path.is_file())
            deleted_snapshots = snapshots.delete_package_snapshots("scf-engine-bootstrap")
            self.assertIn("agents/Agent-Welcome.md", deleted_snapshots)

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
                    "agents/Agent-Welcome.md",
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
            sentinel = workspace_root / ".github" / "agents" / "Agent-Welcome.md"
            sentinel.write_text("# user modified content", encoding="utf-8")

            # Second bootstrap — sentinel tracked but SHA mismatch.
            result2 = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())
            self.assertTrue(result2["success"])
            self.assertEqual(result2["status"], "user_modified")
            self.assertIn("agents/Agent-Welcome.md", result2["preserved"])
            self.assertEqual(result2["files_written"], [])
            # User modification preserved.
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "# user modified content")

    def test_bootstrap_does_not_retrack_agent_welcome_when_owned_by_spark_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            _, mcp = self._build_engine(workspace_root)
            manifest = ManifestManager(workspace_root / ".github")

            first = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())
            self.assertEqual(first["status"], "bootstrapped")

            welcome_path = workspace_root / ".github" / "agents" / "Agent-Welcome.md"
            manifest.remove_owner_entries("scf-engine-bootstrap", ["agents/Agent-Welcome.md"])
            manifest.upsert_many("spark-base", "1.2.0", [("agents/Agent-Welcome.md", welcome_path)])
            welcome_path.unlink()

            second = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())
            self.assertEqual(second["status"], "bootstrapped")
            self.assertEqual(manifest.get_file_owners("agents/Agent-Welcome.md"), ["spark-base"])

    def test_bootstrap_repairs_missing_root_asset_when_sentinel_is_still_tracked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            _, mcp = self._build_engine(workspace_root)

            first = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())
            self.assertEqual(first["status"], "bootstrapped")

            copilot_instructions = workspace_root / ".github" / "copilot-instructions.md"
            copilot_instructions.unlink()

            second = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())

            self.assertTrue(second["success"])
            self.assertEqual(second["status"], "bootstrapped")
            self.assertIn(".github/copilot-instructions.md", second["files_written"])
            self.assertTrue(copilot_instructions.is_file())

    def test_bootstrap_extended_requires_authorization_after_policy_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            _, mcp = self._build_engine(workspace_root)

            result = asyncio.run(mcp.tools["scf_bootstrap_workspace"](update_mode="integrative"))

            prefs_path = workspace_root / ".github" / "user-prefs.json"
            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "authorization_required")
            self.assertEqual(result["action_required"], "authorize_github_write")
            self.assertTrue(result["policy_created"])
            self.assertTrue(prefs_path.is_file())
            self.assertEqual(result["files_written"], [])
            self.assertFalse((workspace_root / ".github" / "agents" / "Agent-Welcome.md").exists())

    def test_bootstrap_extended_writes_assets_and_policy_when_authorized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            self._authorize_github_writes(workspace_root)
            _, mcp = self._build_engine(workspace_root)

            result = asyncio.run(mcp.tools["scf_bootstrap_workspace"](update_mode="integrative"))

            prefs_path = workspace_root / ".github" / "user-prefs.json"
            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "bootstrapped")
            self.assertTrue(result["policy_created"])
            self.assertTrue(result["github_write_authorized"])
            self.assertTrue(prefs_path.is_file())
            self.assertTrue((workspace_root / ".github" / "agents" / "Agent-Welcome.md").is_file())

            payload = json.loads(prefs_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["update_policy"]["auto_update"])
            self.assertEqual(payload["update_policy"]["default_mode"], "integrative")

    def test_bootstrap_legacy_workspace_requires_authorization_before_policy_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            sentinel = workspace_root / ".github" / "AGENTS.md"
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