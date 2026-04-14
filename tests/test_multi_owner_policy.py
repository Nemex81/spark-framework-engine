"""Tests for Phase 6 multi-owner per-file policies."""
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
SnapshotManager = _module.SnapshotManager
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


class TestMultiOwnerPolicy(unittest.TestCase):
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

    def _registry_package(self, package_id: str) -> dict[str, str]:
        return {
            "id": package_id,
            "description": f"Package {package_id}",
            "repo_url": f"https://github.com/example/{package_id}",
            "latest_version": "2.0.0",
            "status": "active",
            "engine_min_version": "1.0.0",
        }

    def _manifest_payload(
        self,
        package_id: str,
        file_path: str,
        policy: str,
    ) -> dict[str, Any]:
        return {
            "package": package_id,
            "version": "2.0.0",
            "min_engine_version": "1.0.0",
            "dependencies": [],
            "conflicts": [],
            "file_ownership_policy": "error",
            "file_policies": {file_path: policy},
            "files": [file_path],
        }

    def test_extend_policy_updates_only_current_section_and_preserves_outer_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "copilot-instructions.md"
            target_file.parent.mkdir(parents=True)
            existing_text = (
                "intro\n\n"
                "<!-- SCF:SECTION:pkg-a:BEGIN -->\n"
                "pkg-a rules\n"
                "<!-- SCF:SECTION:pkg-a:END -->\n\n"
                "footer\n"
            )
            target_file.write_text(existing_text, encoding="utf-8")
            manifest = ManifestManager(github_root)
            manifest.save(
                [
                    self._entry(
                        "copilot-instructions.md",
                        "pkg-a",
                        existing_text,
                        "1.0.0",
                    )
                ]
            )

            fake_mcp = self._build_engine(workspace_root)
            install_package = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-b")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value=self._manifest_payload(
                        "pkg-b",
                        ".github/copilot-instructions.md",
                        "extend",
                    ),
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="pkg-b rules v1"),
            ):
                first_result = asyncio.run(install_package("pkg-b"))

            self.assertTrue(first_result["success"])
            self.assertEqual(first_result["extended_files"], [".github/copilot-instructions.md"])
            first_text = target_file.read_text(encoding="utf-8")
            self.assertIn("intro\n\n", first_text)
            self.assertIn("pkg-a rules", first_text)
            self.assertIn("pkg-b rules v1", first_text)
            self.assertIn("footer\n", first_text)

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-b")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value=self._manifest_payload(
                        "pkg-b",
                        ".github/copilot-instructions.md",
                        "extend",
                    ),
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="pkg-b rules v2"),
            ):
                second_result = asyncio.run(install_package("pkg-b"))

            self.assertTrue(second_result["success"])
            second_text = target_file.read_text(encoding="utf-8")
            self.assertIn("intro\n\n", second_text)
            self.assertIn("pkg-a rules", second_text)
            self.assertIn("pkg-b rules v2", second_text)
            self.assertNotIn("pkg-b rules v1", second_text)
            self.assertEqual(second_text.count("<!-- SCF:SECTION:pkg-b:BEGIN -->"), 1)
            self.assertIn("footer\n", second_text)

    def test_delegate_policy_on_shared_file_skips_write_and_returns_delegated_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "copilot-instructions.md"
            target_file.parent.mkdir(parents=True)
            existing_text = "owned by pkg-a\n"
            target_file.write_text(existing_text, encoding="utf-8")
            manifest = ManifestManager(github_root)
            manifest.save(
                [
                    self._entry(
                        "copilot-instructions.md",
                        "pkg-a",
                        existing_text,
                        "1.0.0",
                    )
                ]
            )

            fake_mcp = self._build_engine(workspace_root)
            install_package = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-b")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value=self._manifest_payload(
                        "pkg-b",
                        ".github/copilot-instructions.md",
                        "delegate",
                    ),
                ),
                patch.object(
                    RegistryClient,
                    "fetch_raw_file",
                    side_effect=AssertionError("delegate must not fetch raw file content"),
                ),
            ):
                result = asyncio.run(install_package("pkg-b"))

            self.assertTrue(result["success"])
            self.assertEqual(result["installed"], [])
            self.assertEqual(result["delegated_files"], [".github/copilot-instructions.md"])
            self.assertEqual(target_file.read_text(encoding="utf-8"), existing_text)
            self.assertEqual(manifest.get_file_owners("copilot-instructions.md"), ["pkg-a"])
            snapshots = SnapshotManager(github_root / "runtime" / "snapshots")
            self.assertFalse(snapshots.snapshot_exists("pkg-b", "copilot-instructions.md"))

    def test_manifest_manager_get_file_owners_returns_both_packages_after_extend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "copilot-instructions.md"
            target_file.parent.mkdir(parents=True)
            existing_text = "<!-- SCF:SECTION:pkg-a:BEGIN -->\npkg-a\n<!-- SCF:SECTION:pkg-a:END -->\n"
            target_file.write_text(existing_text, encoding="utf-8")
            manifest = ManifestManager(github_root)
            manifest.save(
                [self._entry("copilot-instructions.md", "pkg-a", existing_text, "1.0.0")]
            )

            fake_mcp = self._build_engine(workspace_root)
            install_package = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-b")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value=self._manifest_payload(
                        "pkg-b",
                        ".github/copilot-instructions.md",
                        "extend",
                    ),
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="pkg-b"),
            ):
                result = asyncio.run(install_package("pkg-b"))

            self.assertTrue(result["success"])
            self.assertEqual(
                manifest.get_file_owners("copilot-instructions.md"),
                ["pkg-a", "pkg-b"],
            )

    def test_extend_policy_on_agent_file_is_rejected_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "agents" / "shared.agent.md"
            target_file.parent.mkdir(parents=True)
            existing_text = "agent content\n"
            target_file.write_text(existing_text, encoding="utf-8")
            manifest = ManifestManager(github_root)
            manifest.save(
                [self._entry("agents/shared.agent.md", "pkg-a", existing_text, "1.0.0")]
            )

            fake_mcp = self._build_engine(workspace_root)
            install_package = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-b")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value=self._manifest_payload(
                        "pkg-b",
                        ".github/agents/shared.agent.md",
                        "extend",
                    ),
                ),
            ):
                result = asyncio.run(install_package("pkg-b"))

            self.assertFalse(result["success"])
            self.assertIn("Policy 'extend' is not supported", result["error"])
            self.assertIn(".agent.md", result["error"])
            self.assertEqual(target_file.read_text(encoding="utf-8"), existing_text)
            self.assertEqual(manifest.get_file_owners("agents/shared.agent.md"), ["pkg-a"])

    def test_extend_policy_can_create_section_file_when_shared_target_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            github_root.mkdir(parents=True)
            manifest = ManifestManager(github_root)
            manifest.save(
                [
                    self._entry(
                        "copilot-instructions.md",
                        "pkg-a",
                        "missing source placeholder",
                        "1.0.0",
                    )
                ]
            )

            fake_mcp = self._build_engine(workspace_root)
            install_package = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-b")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value=self._manifest_payload(
                        "pkg-b",
                        ".github/copilot-instructions.md",
                        "extend",
                    ),
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="pkg-b created section"),
            ):
                result = asyncio.run(install_package("pkg-b"))

            target_file = github_root / "copilot-instructions.md"
            self.assertTrue(result["success"])
            self.assertEqual(result["extended_files"], [".github/copilot-instructions.md"])
            self.assertTrue(target_file.is_file())
            written_text = target_file.read_text(encoding="utf-8")
            self.assertIn("<!-- SCF:SECTION:pkg-b:BEGIN -->", written_text)
            self.assertIn("pkg-b created section", written_text)
            self.assertEqual(
                manifest.get_file_owners("copilot-instructions.md"),
                ["pkg-a", "pkg-b"],
            )

    def test_remove_package_on_multi_owner_extend_file_preserves_shared_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "copilot-instructions.md"
            target_file.parent.mkdir(parents=True)
            shared_text = (
                "intro\n\n"
                "<!-- SCF:SECTION:pkg-a:BEGIN -->\n"
                "pkg-a rules\n"
                "<!-- SCF:SECTION:pkg-a:END -->\n\n"
                "<!-- SCF:SECTION:pkg-b:BEGIN -->\n"
                "pkg-b rules\n"
                "<!-- SCF:SECTION:pkg-b:END -->\n"
            )
            target_file.write_text(shared_text, encoding="utf-8")

            manifest = ManifestManager(github_root)
            manifest.save(
                [
                    self._entry("copilot-instructions.md", "pkg-a", shared_text, "1.0.0"),
                    self._entry("copilot-instructions.md", "pkg-b", shared_text, "1.0.0"),
                ]
            )
            snapshots = SnapshotManager(github_root / "runtime" / "snapshots")
            self.assertTrue(
                snapshots.save_snapshot("pkg-b", "copilot-instructions.md", target_file)
            )

            fake_mcp = self._build_engine(workspace_root)
            remove_package = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_remove_package"],
            )

            result = asyncio.run(remove_package("pkg-b"))

            self.assertTrue(result["success"])
            self.assertTrue(target_file.is_file())
            updated_text = target_file.read_text(encoding="utf-8")
            self.assertIn("pkg-a rules", updated_text)
            self.assertIn("pkg-b rules", updated_text)
            self.assertEqual(
                manifest.get_file_owners("copilot-instructions.md"),
                ["pkg-a"],
            )
            self.assertEqual(result["deleted_snapshots"], ["copilot-instructions.md"])


if __name__ == "__main__":
    unittest.main()