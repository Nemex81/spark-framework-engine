"""Unit tests for dependency-aware update planning and application order."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Coroutine, cast
from unittest.mock import MagicMock, patch

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

FrameworkInventory = _module.FrameworkInventory
ManifestManager = _module.ManifestManager
RegistryClient = _module.RegistryClient
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


class TestUpdatePlanner(unittest.TestCase):
    def _sha256(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _entry(self, file_rel: str, package: str, content: str, version: str) -> dict[str, str]:
        return {
            "file": file_rel,
            "package": package,
            "package_version": version,
            "installed_at": "2026-04-10T00:00:00Z",
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

    def _registry_packages(self) -> list[dict[str, str]]:
        return [
            {
                "id": "scf-master-codecrafter",
                "description": "master",
                "repo_url": "https://github.com/example/scf-master-codecrafter",
                "latest_version": "1.1.0",
                "engine_min_version": "1.5.0",
                "status": "stable",
            },
            {
                "id": "scf-pycode-crafter",
                "description": "python",
                "repo_url": "https://github.com/example/scf-pycode-crafter",
                "latest_version": "2.1.0",
                "engine_min_version": "1.5.0",
                "status": "active",
            },
        ]

    def _manifest_for(self, package_id: str) -> dict[str, Any]:
        manifests: dict[str, dict[str, Any]] = {
            "https://github.com/example/scf-master-codecrafter": {
                "package": "scf-master-codecrafter",
                "version": "1.1.0",
                "min_engine_version": "1.5.0",
                "dependencies": [],
                "conflicts": [],
                "files": [".github/agents/Agent-Orchestrator.md"],
            },
            "https://github.com/example/scf-pycode-crafter": {
                "package": "scf-pycode-crafter",
                "version": "2.1.0",
                "min_engine_version": "1.5.0",
                "dependencies": ["scf-master-codecrafter"],
                "conflicts": [],
                "files": [".github/agents/py-Agent-Code.md"],
            },
        }
        return manifests[package_id]

    def test_update_packages_returns_dependency_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            (github_root / "agents").mkdir(parents=True)
            (github_root / "agents" / "Agent-Orchestrator.md").write_text("old master", encoding="utf-8")
            (github_root / "agents" / "py-Agent-Code.md").write_text("old plugin", encoding="utf-8")
            ManifestManager(github_root).save(
                [
                    self._entry("agents/Agent-Orchestrator.md", "scf-master-codecrafter", "old master", "1.0.0"),
                    self._entry("agents/py-Agent-Code.md", "scf-pycode-crafter", "old plugin", "2.0.0"),
                ]
            )

            fake_mcp = self._build_engine(workspace_root)
            update_packages = cast(
                Callable[[], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_update_packages"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=self._registry_packages()),
                patch.object(RegistryClient, "fetch_package_manifest", side_effect=self._manifest_for),
            ):
                result = asyncio.run(update_packages())

            self.assertTrue(result["success"])
            self.assertEqual(
                [item["package"] for item in result["plan"]["order"]],
                ["scf-master-codecrafter", "scf-pycode-crafter"],
            )
            self.assertTrue(result["plan"]["can_apply"])

    def test_apply_updates_for_plugin_includes_dependency_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            (github_root / "agents").mkdir(parents=True)
            (github_root / "agents" / "Agent-Orchestrator.md").write_text("old master", encoding="utf-8")
            (github_root / "agents" / "py-Agent-Code.md").write_text("old plugin", encoding="utf-8")
            manifest = ManifestManager(github_root)
            manifest.save(
                [
                    self._entry("agents/Agent-Orchestrator.md", "scf-master-codecrafter", "old master", "1.0.0"),
                    self._entry("agents/py-Agent-Code.md", "scf-pycode-crafter", "old plugin", "2.0.0"),
                ]
            )

            fake_mcp = self._build_engine(workspace_root)
            apply_updates = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_apply_updates"],
            )

            raw_content = {
                "https://raw.githubusercontent.com/example/scf-master-codecrafter/main/.github/agents/Agent-Orchestrator.md": "new master",
                "https://raw.githubusercontent.com/example/scf-pycode-crafter/main/.github/agents/py-Agent-Code.md": "new plugin",
            }

            with (
                patch.object(RegistryClient, "list_packages", return_value=self._registry_packages()),
                patch.object(RegistryClient, "fetch_package_manifest", side_effect=self._manifest_for),
                patch.object(RegistryClient, "fetch_raw_file", side_effect=lambda url: raw_content[url]),
            ):
                result = asyncio.run(apply_updates("scf-pycode-crafter"))

            self.assertTrue(result["success"])
            self.assertEqual(
                [item["package"] for item in result["applied"]],
                ["scf-master-codecrafter", "scf-pycode-crafter"],
            )
            self.assertEqual(manifest.get_installed_versions(), {
                "scf-master-codecrafter": "1.1.0",
                "scf-pycode-crafter": "2.1.0",
            })

    def test_apply_updates_forwards_manual_conflict_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "agents" / "Agent-Orchestrator.md"
            target_file.parent.mkdir(parents=True)
            base_text = "alpha\nbase\nomega\n"
            ours_text = "alpha\nours\nomega\n"
            theirs_text = "alpha\ntheirs\nomega\n"
            target_file.write_text(ours_text, encoding="utf-8")

            manifest = ManifestManager(github_root)
            manifest.save(
                [
                    self._entry("agents/Agent-Orchestrator.md", "scf-master-codecrafter", base_text, "1.0.0"),
                ]
            )

            snapshots = _module.SnapshotManager(github_root / "runtime" / "snapshots")
            snapshot_source = workspace_root / "snapshot-base.md"
            snapshot_source.write_text(base_text, encoding="utf-8")
            self.assertTrue(
                snapshots.save_snapshot("scf-master-codecrafter", "agents/Agent-Orchestrator.md", snapshot_source)
            )

            fake_mcp = self._build_engine(workspace_root)
            apply_updates = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_apply_updates"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_packages()[0]]),
                patch.object(RegistryClient, "fetch_package_manifest", side_effect=self._manifest_for),
                patch.object(RegistryClient, "fetch_raw_file", return_value=theirs_text),
            ):
                result = asyncio.run(apply_updates("scf-master-codecrafter", conflict_mode="manual"))

            self.assertTrue(result["success"])
            self.assertEqual(result["conflict_mode"], "manual")
            self.assertEqual(result["applied"][0]["session_status"], "active")
            self.assertTrue(result["applied"][0]["requires_user_resolution"])

    def test_update_packages_blocks_missing_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            (github_root / "agents").mkdir(parents=True)
            (github_root / "agents" / "py-Agent-Code.md").write_text("old plugin", encoding="utf-8")
            ManifestManager(github_root).save(
                [
                    self._entry("agents/py-Agent-Code.md", "scf-pycode-crafter", "old plugin", "2.0.0"),
                ]
            )

            fake_mcp = self._build_engine(workspace_root)
            update_packages = cast(
                Callable[[], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_update_packages"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_packages()[1]]),
                patch.object(RegistryClient, "fetch_package_manifest", side_effect=self._manifest_for),
            ):
                result = asyncio.run(update_packages())

            self.assertTrue(result["success"])
            self.assertEqual(result["plan"]["order"], [])
            self.assertEqual(result["plan"]["blocked"][0]["reason"], "missing_dependencies")

    def test_apply_updates_aborts_before_first_write_on_preflight_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            agents_root = github_root / "agents"
            agents_root.mkdir(parents=True)
            master_file = agents_root / "Agent-Orchestrator.md"
            plugin_file = agents_root / "py-Agent-Code.md"
            conflicting_file = agents_root / "NewPlugin.md"
            master_file.write_text("old master", encoding="utf-8")
            plugin_file.write_text("old plugin", encoding="utf-8")
            conflicting_file.write_text("user-owned", encoding="utf-8")
            manifest = ManifestManager(github_root)
            manifest.save(
                [
                    self._entry("agents/Agent-Orchestrator.md", "scf-master-codecrafter", "old master", "1.0.0"),
                    self._entry("agents/py-Agent-Code.md", "scf-pycode-crafter", "old plugin", "2.0.0"),
                ]
            )

            fake_mcp = self._build_engine(workspace_root)
            apply_updates = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_apply_updates"],
            )

            manifests = {
                "https://github.com/example/scf-master-codecrafter": {
                    "package": "scf-master-codecrafter",
                    "version": "1.1.0",
                    "min_engine_version": "1.5.0",
                    "dependencies": [],
                    "conflicts": [],
                    "files": [".github/agents/Agent-Orchestrator.md"],
                },
                "https://github.com/example/scf-pycode-crafter": {
                    "package": "scf-pycode-crafter",
                    "version": "2.1.0",
                    "min_engine_version": "1.5.0",
                    "dependencies": ["scf-master-codecrafter"],
                    "conflicts": [],
                    "files": [".github/agents/NewPlugin.md"],
                },
            }

            with (
                patch.object(RegistryClient, "list_packages", return_value=self._registry_packages()),
                patch.object(RegistryClient, "fetch_package_manifest", side_effect=lambda repo_url: manifests[repo_url]),
                patch.object(RegistryClient, "fetch_raw_file", return_value="new content"),
            ):
                result = asyncio.run(apply_updates("scf-pycode-crafter"))

            self.assertFalse(result["success"])
            self.assertEqual(result["applied"], [])
            self.assertEqual(result["failed"], [])
            self.assertEqual(master_file.read_text(encoding="utf-8"), "old master")
            self.assertEqual(plugin_file.read_text(encoding="utf-8"), "old plugin")
            self.assertEqual(
                result["batch_conflicts"],
                [
                    {
                        "package": "scf-pycode-crafter",
                        "conflicts": [
                            {
                                "file": ".github/agents/NewPlugin.md",
                                "classification": "conflict_untracked_existing",
                            }
                        ],
                    }
                ],
            )

    def test_update_package_surfaces_preflight_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            agents_root = github_root / "agents"
            agents_root.mkdir(parents=True)
            master_file = agents_root / "Agent-Orchestrator.md"
            plugin_file = agents_root / "py-Agent-Code.md"
            conflicting_file = agents_root / "NewPlugin.md"
            master_file.write_text("old master", encoding="utf-8")
            plugin_file.write_text("old plugin", encoding="utf-8")
            conflicting_file.write_text("user-owned", encoding="utf-8")
            ManifestManager(github_root).save(
                [
                    self._entry("agents/Agent-Orchestrator.md", "scf-master-codecrafter", "old master", "1.0.0"),
                    self._entry("agents/py-Agent-Code.md", "scf-pycode-crafter", "old plugin", "2.0.0"),
                ]
            )

            fake_mcp = self._build_engine(workspace_root)
            update_package = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_update_package"],
            )

            manifests = {
                "https://github.com/example/scf-master-codecrafter": {
                    "package": "scf-master-codecrafter",
                    "version": "1.1.0",
                    "min_engine_version": "1.5.0",
                    "dependencies": [],
                    "conflicts": [],
                    "files": [".github/agents/Agent-Orchestrator.md"],
                },
                "https://github.com/example/scf-pycode-crafter": {
                    "package": "scf-pycode-crafter",
                    "version": "2.1.0",
                    "min_engine_version": "1.5.0",
                    "dependencies": ["scf-master-codecrafter"],
                    "conflicts": [],
                    "files": [".github/agents/NewPlugin.md"],
                },
            }

            with (
                patch.object(RegistryClient, "list_packages", return_value=self._registry_packages()),
                patch.object(RegistryClient, "fetch_package_manifest", side_effect=lambda repo_url: manifests[repo_url]),
            ):
                result = asyncio.run(update_package("scf-pycode-crafter"))

            self.assertFalse(result["success"])
            self.assertEqual(
                result["conflicts_detected"],
                [
                    {
                        "package": "scf-pycode-crafter",
                        "conflicts": [
                            {
                                "file": ".github/agents/NewPlugin.md",
                                "classification": "conflict_untracked_existing",
                            }
                        ],
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()