"""Integration tests for Phase 2 manual merge install/update behavior."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Coroutine, cast
from unittest.mock import MagicMock, patch

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

FrameworkInventory = _module.FrameworkInventory
ManifestManager = _module.ManifestManager
SnapshotManager = _module.SnapshotManager
SparkFrameworkEngine = _module.SparkFrameworkEngine
RegistryClient = _module.RegistryClient
WorkspaceContext = _module.WorkspaceContext
resolve_runtime_dir = _module.resolve_runtime_dir


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


class TestMergeIntegration(unittest.TestCase):
    def _sha256(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _entry(self, file_rel: str, package: str, content: str, version: str) -> dict[str, str]:
        return {
            "file": file_rel,
            "package": package,
            "package_version": version,
            "installed_at": "2026-04-14T00:00:00Z",
            "sha256": self._sha256(content),
        }

    def _make_context(self, workspace_root: Path) -> object:
        return WorkspaceContext(
            workspace_root=workspace_root,
            github_root=workspace_root / ".github",
            engine_root=workspace_root / "spark-framework-engine",
        )

    def _build_engine(self, workspace_root: Path) -> FakeMCP:
        context = self._make_context(workspace_root)
        inventory = FrameworkInventory(context)
        fake_mcp = FakeMCP()
        engine = SparkFrameworkEngine(fake_mcp, context, inventory)
        engine.register_tools()
        return fake_mcp

    def _runtime_dir(self, workspace_root: Path) -> Path:
        """Compute the engine-local runtime dir for this workspace (mirrors sequence.py)."""
        return resolve_runtime_dir(workspace_root / "spark-framework-engine", workspace_root)

    def _authorize_github_writes(self, workspace_root: Path) -> None:
        state_path = workspace_root / ".github" / "runtime" / "orchestrator-state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"github_write_authorized": True}, indent=2),
            encoding="utf-8",
        )

    def _registry_package(self, package_id: str, version: str = "2.0.0") -> dict[str, str]:
        return {
            "id": package_id,
            "description": f"Package {package_id}",
            "repo_url": f"https://github.com/example/{package_id}",
            "latest_version": version,
            "status": "active",
            "engine_min_version": "1.0.0",
        }

    def test_update_package_manual_when_conflict_creates_session_and_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "agents" / "shared.md"
            target_file.parent.mkdir(parents=True)
            base_text = "alpha\nbase\nomega\n"
            ours_text = "alpha\nours\nomega\n"
            theirs_text = "alpha\ntheirs\nomega\n"
            target_file.write_text(ours_text, encoding="utf-8")

            manifest = ManifestManager(github_root)
            manifest.save([self._entry("agents/shared.md", "pkg-a", base_text, "1.0.0")])
            snapshots = SnapshotManager(self._runtime_dir(workspace_root) / "snapshots")
            snapshot_source = workspace_root / "snapshot-base.md"
            snapshot_source.write_text(base_text, encoding="utf-8")
            self.assertTrue(snapshots.save_snapshot("pkg-a", "agents/shared.md", snapshot_source))
            self._authorize_github_writes(workspace_root)

            fake_mcp = self._build_engine(workspace_root)
            update_package = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_update_package"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-a")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value={
                        "package": "pkg-a",
                        "version": "2.0.0",
                        "min_engine_version": "1.0.0",
                        "dependencies": [],
                        "conflicts": [],
                        "file_ownership_policy": "error",
                        "files": [".github/agents/shared.md"],
                    },
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value=theirs_text),
            ):
                result = asyncio.run(
                    update_package("pkg-a", conflict_mode="manual", update_mode="integrative")
                )

            self.assertTrue(result["success"])
            self.assertTrue(result["requires_user_resolution"])
            self.assertIsNotNone(result["session_id"])
            self.assertEqual(result["session_status"], "active")
            self.assertEqual(result["merge_clean"], [])
            self.assertEqual(result["merged_files"], [".github/agents/shared.md"])
            self.assertEqual(result["updated_files"], [])
            self.assertEqual(result["merge_conflict"][0]["file"], ".github/agents/shared.md")
            self.assertIn("<<<<<<< YOURS", target_file.read_text(encoding="utf-8"))

            session_path = self._runtime_dir(workspace_root) / "merge-sessions" / f"{result['session_id']}.json"
            self.assertTrue(session_path.is_file())
            session_payload = json.loads(session_path.read_text(encoding="utf-8"))
            self.assertEqual(session_payload["package"], "pkg-a")
            self.assertEqual(session_payload["files"][0]["manifest_rel"], "agents/shared.md")

    def test_install_package_manual_when_same_change_both_returns_merge_clean_without_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "agents" / "shared.md"
            target_file.parent.mkdir(parents=True)
            base_text = "alpha\nbase\n"
            merged_text = "alpha\ngamma\n"
            target_file.write_text(merged_text, encoding="utf-8")

            manifest = ManifestManager(github_root)
            manifest.save([self._entry("agents/shared.md", "pkg-a", base_text, "1.0.0")])
            snapshots = SnapshotManager(self._runtime_dir(workspace_root) / "snapshots")
            snapshot_source = workspace_root / "snapshot-base.md"
            snapshot_source.write_text(base_text, encoding="utf-8")
            self.assertTrue(snapshots.save_snapshot("pkg-a", "agents/shared.md", snapshot_source))

            fake_mcp = self._build_engine(workspace_root)
            install_package = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-a")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value={
                        "package": "pkg-a",
                        "version": "2.0.0",
                        "min_engine_version": "1.0.0",
                        "dependencies": [],
                        "conflicts": [],
                        "file_ownership_policy": "error",
                        "files": [".github/agents/shared.md"],
                    },
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value=merged_text),
            ):
                result = asyncio.run(install_package("pkg-a", conflict_mode="manual"))

            self.assertTrue(result["success"])
            self.assertEqual(result["session_id"], None)
            self.assertFalse(result["requires_user_resolution"])
            self.assertEqual(result["merge_conflict"], [])
            self.assertEqual(result["merge_clean"][0]["file"], ".github/agents/shared.md")
            self.assertEqual(target_file.read_text(encoding="utf-8"), merged_text)
            # Fresh ManifestManager instance to avoid stale mtime-based cache from
            # the pre-install instance (same race condition as test_package_installation_policies).
            self.assertEqual(ManifestManager(github_root).get_installed_versions(), {"pkg-a": "2.0.0"})
            self.assertEqual(
                snapshots.load_snapshot("pkg-a", "agents/shared.md"),
                merged_text,
            )

    def test_install_package_manual_when_snapshot_missing_preserves_file_without_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "agents" / "shared.md"
            target_file.parent.mkdir(parents=True)
            base_text = "alpha\nbase\n"
            ours_text = "alpha\nours\n"
            target_file.write_text(ours_text, encoding="utf-8")

            manifest = ManifestManager(github_root)
            manifest.save([self._entry("agents/shared.md", "pkg-a", base_text, "1.0.0")])

            fake_mcp = self._build_engine(workspace_root)
            install_package = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-a")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value={
                        "package": "pkg-a",
                        "version": "2.0.0",
                        "min_engine_version": "1.0.0",
                        "dependencies": [],
                        "conflicts": [],
                        "file_ownership_policy": "error",
                        "files": [".github/agents/shared.md"],
                    },
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="alpha\ntheirs\n"),
            ):
                result = asyncio.run(install_package("pkg-a", conflict_mode="manual"))

            self.assertTrue(result["success"])
            self.assertEqual(result["preserved"], [".github/agents/shared.md"])
            self.assertEqual(result["session_id"], None)
            self.assertEqual(result["merge_clean"], [])
            self.assertEqual(result["merge_conflict"], [])
            self.assertEqual(target_file.read_text(encoding="utf-8"), ours_text)
            self.assertEqual(manifest.get_installed_versions(), {"pkg-a": "1.0.0"})

    def test_install_package_abort_preserves_but_replace_overwrites_merge_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "agents" / "shared.md"
            target_file.parent.mkdir(parents=True)
            base_text = "alpha\nbase\n"
            ours_text = "alpha\nours\n"
            target_file.write_text(ours_text, encoding="utf-8")

            manifest = ManifestManager(github_root)
            manifest.save([self._entry("agents/shared.md", "pkg-a", base_text, "1.0.0")])
            snapshots = SnapshotManager(self._runtime_dir(workspace_root) / "snapshots")
            snapshot_source = workspace_root / "snapshot-base.md"
            snapshot_source.write_text(base_text, encoding="utf-8")
            self.assertTrue(snapshots.save_snapshot("pkg-a", "agents/shared.md", snapshot_source))

            fake_mcp = self._build_engine(workspace_root)
            install_package = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )

            target_file.write_text(ours_text, encoding="utf-8")
            manifest.save([self._entry("agents/shared.md", "pkg-a", base_text, "1.0.0")])
            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-a")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value={
                        "package": "pkg-a",
                        "version": "2.0.0",
                        "min_engine_version": "1.0.0",
                        "dependencies": [],
                        "conflicts": [],
                        "file_ownership_policy": "error",
                        "files": [".github/agents/shared.md"],
                    },
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="alpha\ntheirs\n"),
            ):
                abort_result = asyncio.run(install_package("pkg-a", conflict_mode="abort"))

            self.assertTrue(abort_result["success"])
            self.assertEqual(abort_result["preserved"], [".github/agents/shared.md"])
            self.assertEqual(abort_result["session_id"], None)
            self.assertEqual(abort_result["resolution_applied"], "none")
            self.assertEqual(target_file.read_text(encoding="utf-8"), ours_text)

            target_file.write_text(ours_text, encoding="utf-8")
            manifest.save([self._entry("agents/shared.md", "pkg-a", base_text, "1.0.0")])
            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-a")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value={
                        "package": "pkg-a",
                        "version": "2.0.0",
                        "min_engine_version": "1.0.0",
                        "dependencies": [],
                        "conflicts": [],
                        "file_ownership_policy": "error",
                        "files": [".github/agents/shared.md"],
                    },
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="alpha\ntheirs\n"),
            ):
                replace_result = asyncio.run(install_package("pkg-a", conflict_mode="replace"))

            self.assertTrue(replace_result["success"])
            self.assertEqual(replace_result["preserved"], [])
            self.assertEqual(replace_result["replaced_files"], [".github/agents/shared.md"])
            self.assertEqual(replace_result["resolution_applied"], "replace")
            self.assertEqual(target_file.read_text(encoding="utf-8"), "alpha\ntheirs\n")

    def test_update_package_auto_when_safe_conflict_resolves_without_active_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "agents" / "shared.md"
            target_file.parent.mkdir(parents=True)
            base_text = "# Agent\nBody\n"
            ours_text = "## Local\n# Agent\nBody\n"
            theirs_text = "# Agent\nBody\n## Remote\n"
            target_file.write_text(ours_text, encoding="utf-8")

            manifest = ManifestManager(github_root)
            manifest.save([self._entry("agents/shared.md", "pkg-a", base_text, "1.0.0")])
            snapshots = SnapshotManager(self._runtime_dir(workspace_root) / "snapshots")
            snapshot_source = workspace_root / "snapshot-base.md"
            snapshot_source.write_text(base_text, encoding="utf-8")
            self.assertTrue(snapshots.save_snapshot("pkg-a", "agents/shared.md", snapshot_source))
            self._authorize_github_writes(workspace_root)

            fake_mcp = self._build_engine(workspace_root)
            update_package = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_update_package"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-a")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value={
                        "package": "pkg-a",
                        "version": "2.0.0",
                        "min_engine_version": "1.0.0",
                        "dependencies": [],
                        "conflicts": [],
                        "file_ownership_policy": "error",
                        "files": [".github/agents/shared.md"],
                    },
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value=theirs_text),
            ):
                result = asyncio.run(
                    update_package("pkg-a", conflict_mode="auto", update_mode="integrative")
                )

            self.assertTrue(result["success"])
            self.assertFalse(result["requires_user_resolution"])
            self.assertEqual(result["resolution_applied"], "auto")
            self.assertEqual(result["merge_conflict"], [])
            self.assertEqual(result["merge_clean"][0]["status"], "auto_resolved")
            self.assertNotIn("<<<<<<< YOURS", target_file.read_text(encoding="utf-8"))
            if result["session_id"] is not None:
                session_path = self._runtime_dir(workspace_root) / "merge-sessions" / f"{result['session_id']}.json"
                session_payload = json.loads(session_path.read_text(encoding="utf-8"))
                self.assertEqual(session_payload["status"], "auto_completed")

    def test_update_package_auto_when_ambiguous_conflict_falls_back_to_manual_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "agents" / "shared.md"
            target_file.parent.mkdir(parents=True)
            base_text = "alpha\nbase\nomega\n"
            ours_text = "alpha\nours\nomega\n"
            theirs_text = "alpha\ntheirs\nomega\n"
            target_file.write_text(ours_text, encoding="utf-8")

            manifest = ManifestManager(github_root)
            manifest.save([self._entry("agents/shared.md", "pkg-a", base_text, "1.0.0")])
            snapshots = SnapshotManager(self._runtime_dir(workspace_root) / "snapshots")
            snapshot_source = workspace_root / "snapshot-base.md"
            snapshot_source.write_text(base_text, encoding="utf-8")
            self.assertTrue(snapshots.save_snapshot("pkg-a", "agents/shared.md", snapshot_source))
            self._authorize_github_writes(workspace_root)

            fake_mcp = self._build_engine(workspace_root)
            update_package = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_update_package"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-a")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value={
                        "package": "pkg-a",
                        "version": "2.0.0",
                        "min_engine_version": "1.0.0",
                        "dependencies": [],
                        "conflicts": [],
                        "file_ownership_policy": "error",
                        "files": [".github/agents/shared.md"],
                    },
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value=theirs_text),
            ):
                result = asyncio.run(
                    update_package("pkg-a", conflict_mode="auto", update_mode="integrative")
                )

            self.assertTrue(result["success"])
            self.assertTrue(result["requires_user_resolution"])
            self.assertEqual(result["session_status"], "active")
            self.assertEqual(result["resolution_applied"], "manual")
            self.assertGreaterEqual(result["remaining_conflicts"], 1)
            self.assertIn("<<<<<<< YOURS", target_file.read_text(encoding="utf-8"))

    def test_update_package_assisted_when_conflict_creates_active_session_and_keeps_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "agents" / "shared.md"
            target_file.parent.mkdir(parents=True)
            base_text = "alpha\nbase\nomega\n"
            ours_text = "alpha\nours\nomega\n"
            theirs_text = "alpha\ntheirs\nomega\n"
            target_file.write_text(ours_text, encoding="utf-8")

            manifest = ManifestManager(github_root)
            manifest.save([self._entry("agents/shared.md", "pkg-a", base_text, "1.0.0")])
            snapshots = SnapshotManager(self._runtime_dir(workspace_root) / "snapshots")
            snapshot_source = workspace_root / "snapshot-base.md"
            snapshot_source.write_text(base_text, encoding="utf-8")
            self.assertTrue(snapshots.save_snapshot("pkg-a", "agents/shared.md", snapshot_source))
            self._authorize_github_writes(workspace_root)

            fake_mcp = self._build_engine(workspace_root)
            update_package = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_update_package"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-a")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value={
                        "package": "pkg-a",
                        "version": "2.0.0",
                        "min_engine_version": "1.0.0",
                        "dependencies": [],
                        "conflicts": [],
                        "file_ownership_policy": "error",
                        "files": [".github/agents/shared.md"],
                    },
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value=theirs_text),
            ):
                result = asyncio.run(
                    update_package("pkg-a", conflict_mode="assisted", update_mode="integrative")
                )

            self.assertTrue(result["success"])
            self.assertTrue(result["requires_user_resolution"])
            self.assertEqual(result["session_status"], "active")
            self.assertEqual(result["resolution_applied"], "assisted")
            self.assertEqual(result["updated_files"], [])
            self.assertIn("<<<<<<< YOURS", target_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()