"""Unit tests for multi-package version tracking and changelog resolution."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

FrameworkInventory = _module.FrameworkInventory
ManifestManager = _module.ManifestManager
WorkspaceContext = _module.WorkspaceContext
build_workspace_info = _module.build_workspace_info
ENGINE_VERSION = _module.ENGINE_VERSION
resolve_package_version = _module._resolve_package_version


class TestManifestManagerInstalledVersions(unittest.TestCase):
    def test_get_installed_versions_returns_sorted_deduplicated_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            github_root = Path(tmp) / ".github"
            github_root.mkdir(parents=True)
            manager = ManifestManager(github_root)
            manager.save(
                [
                    {
                        "file": "agents/a.md",
                        "package": "pkg-b",
                        "package_version": "2.0.0",
                        "installed_at": "2026-03-31T00:00:00Z",
                        "sha256": "abc",
                    },
                    {
                        "file": "agents/b.md",
                        "package": "pkg-a",
                        "package_version": "1.0.0",
                        "installed_at": "2026-03-31T00:00:00Z",
                        "sha256": "def",
                    },
                    {
                        "file": "agents/c.md",
                        "package": "pkg-b",
                        "package_version": "2.1.0",
                        "installed_at": "2026-03-31T00:00:01Z",
                        "sha256": "ghi",
                    },
                ]
            )

            self.assertEqual(
                manager.get_installed_versions(),
                {"pkg-a": "1.0.0", "pkg-b": "2.1.0"},
            )

    def test_load_accepts_schema_2_0_entries_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            github_root = Path(tmp) / ".github"
            github_root.mkdir(parents=True)
            (github_root / ".scf-manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": "2.0",
                        "entries": [
                            {
                                "file": "agents/a.md",
                                "package": "pkg-a",
                                "package_version": "1.0.0",
                                "installed_at": "2026-03-31T00:00:00Z",
                                "sha256": "abc",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            manager = ManifestManager(github_root)

            self.assertEqual(manager.get_installed_versions(), {"pkg-a": "1.0.0"})


class TestResolvePackageVersion(unittest.TestCase):
    def test_prefers_manifest_version(self) -> None:
        self.assertEqual(resolve_package_version("2.0.0", "1.9.0"), "2.0.0")

    def test_falls_back_to_registry_version(self) -> None:
        self.assertEqual(resolve_package_version("", "1.9.0"), "1.9.0")

    def test_returns_unknown_when_both_sources_missing(self) -> None:
        self.assertEqual(resolve_package_version("", ""), "unknown")


class TestFrameworkInventoryPackageChangelog(unittest.TestCase):
    def _build_inventory(self, workspace_root: Path) -> Any:
        ctx = WorkspaceContext(
            workspace_root=workspace_root,
            github_root=workspace_root / ".github",
            engine_root=workspace_root / "spark-framework-engine",
        )
        return FrameworkInventory(ctx)

    def test_get_package_changelog_reads_package_specific_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            changelogs_dir = root / ".github" / "changelogs"
            changelogs_dir.mkdir(parents=True)
            changelog = changelogs_dir / "pkg-a.md"
            changelog.write_text("# 1.0.0\n", encoding="utf-8")

            inventory = self._build_inventory(root)

            self.assertEqual(inventory.get_package_changelog("pkg-a"), "# 1.0.0\n")


class TestBuildWorkspaceInfo(unittest.TestCase):
    def _build_inventory(self, workspace_root: Path) -> Any:
        ctx = WorkspaceContext(
            workspace_root=workspace_root,
            github_root=workspace_root / ".github",
            engine_root=workspace_root / "spark-framework-engine",
        )
        return FrameworkInventory(ctx)

    def test_build_workspace_info_returns_engine_and_installed_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            github_root = root / ".github"
            github_root.mkdir(parents=True)
            (github_root / "project-profile.md").write_text(
                "---\ninitialized: true\n---\nProfile",
                encoding="utf-8",
            )
            manifest_path = github_root / ".scf-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "entries": [
                            {
                                "file": "agents/a.md",
                                "package": "pkg-a",
                                "package_version": "1.0.0",
                                "installed_at": "2026-03-31T00:00:00Z",
                                "sha256": "abc",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            ctx = WorkspaceContext(
                workspace_root=root,
                github_root=github_root,
                engine_root=root / "spark-framework-engine",
            )
            inventory = self._build_inventory(root)

            info = build_workspace_info(ctx, inventory)

            self.assertEqual(info["engine_version"], ENGINE_VERSION)
            self.assertEqual(info["installed_packages"], {"pkg-a": "1.0.0"})
            self.assertNotIn("framework_version", info)


if __name__ == "__main__":
    unittest.main()