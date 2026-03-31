"""Unit tests for package installation preflight and manifest v2 metadata."""
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


class TestPackageInstallationPolicies(unittest.TestCase):
    def _sha256(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _entry(self, file_rel: str, package: str, content: str, version: str) -> dict[str, str]:
        return {
            "file": file_rel,
            "package": package,
            "package_version": version,
            "installed_at": "2026-03-31T00:00:00Z",
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
        }

    def test_scf_install_package_blocks_file_conflicts_with_other_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            shared_file = github_root / "agents" / "shared.md"
            shared_file.parent.mkdir(parents=True)
            shared_file.write_text("owned by pkg-a", encoding="utf-8")
            ManifestManager(github_root).save(
                [
                    self._entry(
                        "agents/shared.md",
                        "pkg-a",
                        "owned by pkg-a",
                        "1.0.0",
                    )
                ]
            )

            fake_mcp = self._build_engine(workspace_root)
            install_package = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-b")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value={
                        "package": "pkg-b",
                        "version": "2.0.0",
                        "min_engine_version": "1.0.0",
                        "dependencies": [],
                        "conflicts": [],
                        "file_ownership_policy": "error",
                        "files": [".github/agents/shared.md"],
                    },
                ),
            ):
                result = asyncio.run(install_package("pkg-b"))

            self.assertFalse(result["success"])
            self.assertEqual(
                result["conflicts"],
                [{"file": ".github/agents/shared.md", "owners": ["pkg-a"]}],
            )
            self.assertEqual(shared_file.read_text(encoding="utf-8"), "owned by pkg-a")

    def test_scf_install_package_allows_reinstall_for_same_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            shared_file = github_root / "agents" / "shared.md"
            shared_file.parent.mkdir(parents=True)
            shared_file.write_text("old content", encoding="utf-8")
            manifest = ManifestManager(github_root)
            manifest.save(
                [
                    self._entry(
                        "agents/shared.md",
                        "pkg-b",
                        "old content",
                        "1.0.0",
                    )
                ]
            )

            fake_mcp = self._build_engine(workspace_root)
            install_package = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-b")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value={
                        "package": "pkg-b",
                        "version": "2.0.0",
                        "min_engine_version": "1.0.0",
                        "dependencies": [],
                        "conflicts": [],
                        "file_ownership_policy": "error",
                        "files": [".github/agents/shared.md"],
                    },
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="new content"),
            ):
                result = asyncio.run(install_package("pkg-b"))

            self.assertTrue(result["success"])
            self.assertEqual(result["installed"], [".github/agents/shared.md"])
            self.assertEqual(shared_file.read_text(encoding="utf-8"), "new content")
            self.assertEqual(manifest.get_installed_versions(), {"pkg-b": "2.0.0"})

    def test_scf_install_package_blocks_missing_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            (workspace_root / ".github").mkdir(parents=True)
            fake_mcp = self._build_engine(workspace_root)
            install_package = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-b")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value={
                        "package": "pkg-b",
                        "version": "2.0.0",
                        "min_engine_version": "1.0.0",
                        "dependencies": ["pkg-core"],
                        "conflicts": [],
                        "file_ownership_policy": "error",
                        "files": [".github/agents/new.md"],
                    },
                ),
            ):
                result = asyncio.run(install_package("pkg-b"))

            self.assertFalse(result["success"])
            self.assertEqual(result["missing_dependencies"], ["pkg-core"])

    def test_scf_install_package_blocks_declared_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            github_root.mkdir(parents=True)
            legacy_file = github_root / "agents" / "legacy.md"
            legacy_file.parent.mkdir(parents=True)
            legacy_file.write_text("legacy", encoding="utf-8")
            ManifestManager(github_root).save(
                [self._entry("agents/legacy.md", "pkg-legacy", "legacy", "1.0.0")]
            )
            fake_mcp = self._build_engine(workspace_root)
            install_package = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-b")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value={
                        "package": "pkg-b",
                        "version": "2.0.0",
                        "min_engine_version": "1.0.0",
                        "dependencies": [],
                        "conflicts": ["pkg-legacy"],
                        "file_ownership_policy": "error",
                        "files": [".github/agents/new.md"],
                    },
                ),
            ):
                result = asyncio.run(install_package("pkg-b"))

            self.assertFalse(result["success"])
            self.assertEqual(result["present_conflicts"], ["pkg-legacy"])

    def test_scf_install_package_blocks_incompatible_engine_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            (workspace_root / ".github").mkdir(parents=True)
            fake_mcp = self._build_engine(workspace_root)
            install_package = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-b")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value={
                        "package": "pkg-b",
                        "version": "2.0.0",
                        "min_engine_version": "9.9.9",
                        "dependencies": [],
                        "conflicts": [],
                        "file_ownership_policy": "error",
                        "files": [".github/agents/new.md"],
                    },
                ),
            ):
                result = asyncio.run(install_package("pkg-b"))

            self.assertFalse(result["success"])
            self.assertEqual(result["required_engine_version"], "9.9.9")

    def test_scf_get_package_info_returns_manifest_v2_and_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            github_root.mkdir(parents=True)
            core_file = github_root / "agents" / "core.md"
            legacy_file = github_root / "agents" / "legacy.md"
            core_file.parent.mkdir(parents=True)
            core_file.write_text("core", encoding="utf-8")
            legacy_file.write_text("legacy", encoding="utf-8")
            ManifestManager(github_root).save(
                [
                    self._entry("agents/core.md", "pkg-core", "core", "1.5.0"),
                    self._entry("agents/legacy.md", "pkg-legacy", "legacy", "1.0.0"),
                ]
            )
            fake_mcp = self._build_engine(workspace_root)
            get_package_info = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_get_package_info"],
            )

            with (
                patch.object(RegistryClient, "list_packages", return_value=[self._registry_package("pkg-b")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value={
                        "schema_version": "2.0",
                        "package": "pkg-b",
                        "version": "2.0.0",
                        "display_name": "Package B",
                        "description": "Extended package",
                        "author": "Nemex81",
                        "min_engine_version": "1.2.0",
                        "dependencies": ["pkg-core"],
                        "conflicts": ["pkg-legacy"],
                        "file_ownership_policy": "error",
                        "changelog_path": ".github/changelogs/pkg-b.md",
                        "files": [
                            ".github/agents/b.md",
                            ".github/instructions/b.instructions.md",
                        ],
                    },
                ),
            ):
                result = asyncio.run(get_package_info("pkg-b"))

            self.assertTrue(result["success"])
            self.assertEqual(result["manifest"]["schema_version"], "2.0")
            self.assertEqual(result["manifest"]["dependencies"], ["pkg-core"])
            self.assertEqual(result["manifest"]["conflicts"], ["pkg-legacy"])
            self.assertEqual(result["manifest"]["changelog_path"], ".github/changelogs/pkg-b.md")
            self.assertTrue(result["compatibility"]["engine_compatible"])
            self.assertEqual(result["compatibility"]["missing_dependencies"], [])
            self.assertEqual(result["compatibility"]["present_conflicts"], ["pkg-legacy"])


if __name__ == "__main__":
    unittest.main()
