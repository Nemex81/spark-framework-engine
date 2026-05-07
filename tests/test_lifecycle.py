"""Unit tests for spark.packages.lifecycle — deployment_modes and store helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from spark.packages.lifecycle import (
    _get_deployment_modes,
    _list_orphan_overrides_for_package,
    _remove_package_v3_from_store,
    _v3_overrides_blocking_update,
)


# ============================================================================ #
# TestGetDeploymentModes                                                        #
# ============================================================================ #


class TestGetDeploymentModes:
    """Test normalizzazione della sezione deployment_modes dal manifest."""

    def test_missing_section_returns_fallback(self) -> None:
        result = _get_deployment_modes({})
        assert result["mcp_store"] is True
        assert result["standalone_copy"] is False
        assert result["standalone_files"] == []

    def test_malformed_section_returns_fallback(self) -> None:
        result = _get_deployment_modes({"deployment_modes": "invalid"})
        assert result["mcp_store"] is True
        assert result["standalone_copy"] is False

    def test_auto_mode_no_standalone_copy(self) -> None:
        manifest: dict[str, Any] = {
            "deployment_modes": {"mcp_store": True, "standalone_copy": False}
        }
        result = _get_deployment_modes(manifest)
        assert result["standalone_copy"] is False

    def test_auto_mode_with_standalone_copy(self) -> None:
        manifest: dict[str, Any] = {
            "deployment_modes": {
                "mcp_store": True,
                "standalone_copy": True,
                "standalone_files": [".github/agents/test.md"],
            }
        }
        result = _get_deployment_modes(manifest)
        assert result["standalone_copy"] is True
        assert len(result["standalone_files"]) == 1

    def test_auto_mode_missing_keys(self) -> None:
        manifest: dict[str, Any] = {"deployment_modes": {}}
        result = _get_deployment_modes(manifest)
        assert isinstance(result, dict)
        assert "mcp_store" in result
        assert "standalone_copy" in result
        assert "standalone_files" in result

    def test_auto_mode_empty_standalone_files(self) -> None:
        manifest: dict[str, Any] = {
            "deployment_modes": {
                "standalone_copy": True,
                "standalone_files": [],
            }
        }
        result = _get_deployment_modes(manifest)
        assert result["standalone_copy"] is True
        assert result["standalone_files"] == []

    def test_auto_mode_standalone_files_multiple(self) -> None:
        manifest: dict[str, Any] = {
            "deployment_modes": {
                "standalone_copy": True,
                "standalone_files": [
                    ".github/agents/a.md",
                    ".github/agents/b.md",
                    ".github/agents/c.md",
                ],
            }
        }
        result = _get_deployment_modes(manifest)
        assert len(result["standalone_files"]) == 3

    def test_mcp_store_false(self) -> None:
        manifest: dict[str, Any] = {
            "deployment_modes": {"mcp_store": False}
        }
        result = _get_deployment_modes(manifest)
        assert result["mcp_store"] is False

    def test_standalone_files_none_coerced_to_empty_list(self) -> None:
        manifest: dict[str, Any] = {
            "deployment_modes": {
                "standalone_copy": True,
                "standalone_files": None,
            }
        }
        result = _get_deployment_modes(manifest)
        assert isinstance(result["standalone_files"], list)
        assert result["standalone_files"] == []


# ============================================================================ #
# TestRemovePackageV3FromStore                                                  #
# ============================================================================ #


class TestRemovePackageV3FromStore:
    """Smoke test su _remove_package_v3_from_store con directory assente."""

    def test_remove_nonexistent_package(self, tmp_path: Path) -> None:
        result = _remove_package_v3_from_store(tmp_path, "nonexistent-pkg")
        assert result["removed"] is False
        assert "store_path" in result

    def test_remove_existing_package(self, tmp_path: Path) -> None:
        packages_dir = tmp_path / "packages" / "test-pkg" / ".github"
        packages_dir.mkdir(parents=True)
        (packages_dir / "AGENTS.md").write_text("# test", encoding="utf-8")
        result = _remove_package_v3_from_store(tmp_path, "test-pkg")
        assert result["removed"] is True
        assert not (tmp_path / "packages" / "test-pkg").exists()


# ============================================================================ #
# TestListOrphanOverrides                                                       #
# ============================================================================ #


class TestListOrphanOverrides:
    """Test su _list_orphan_overrides_for_package con registry mock."""

    def test_no_orphans_empty_registry(self) -> None:
        registry = MagicMock()
        registry.list_all.return_value = []
        result = _list_orphan_overrides_for_package(registry, "some-pkg")
        assert result == []

    def test_orphan_found_matching_package(self) -> None:
        registry = MagicMock()
        registry.list_all.return_value = ["agents://test-agent"]
        registry.get_metadata.return_value = {
            "package": "some-pkg",
            "override": "path/to/override",
            "resource_type": "agents",
        }
        result = _list_orphan_overrides_for_package(registry, "some-pkg")
        assert len(result) == 1
        assert result[0]["uri"] == "agents://test-agent"

    def test_orphan_not_found_different_package(self) -> None:
        registry = MagicMock()
        registry.list_all.return_value = ["agents://test-agent"]
        registry.get_metadata.return_value = {
            "package": "other-pkg",
            "override": "path/to/override",
        }
        result = _list_orphan_overrides_for_package(registry, "some-pkg")
        assert result == []

    def test_no_orphan_when_no_override_key(self) -> None:
        registry = MagicMock()
        registry.list_all.return_value = ["agents://test-agent"]
        registry.get_metadata.return_value = {
            "package": "some-pkg",
            # No 'override' key
        }
        result = _list_orphan_overrides_for_package(registry, "some-pkg")
        assert result == []


# ============================================================================ #
# TestV3OverridesBlockingUpdate                                                 #
# ============================================================================ #


class TestV3OverridesBlockingUpdate:
    """Test su _v3_overrides_blocking_update con registry mock."""

    def test_empty_resources_no_blocked(self) -> None:
        registry = MagicMock()
        pkg_manifest: dict[str, Any] = {"mcp_resources": {}}
        result = _v3_overrides_blocking_update(registry, "p", pkg_manifest)
        assert result == []

    def test_no_override_returns_empty(self) -> None:
        registry = MagicMock()
        registry.has_override.return_value = False
        pkg_manifest: dict[str, Any] = {
            "mcp_resources": {"agents": ["spark-guide"]}
        }
        result = _v3_overrides_blocking_update(registry, "p", pkg_manifest)
        assert result == []

    def test_with_override_returns_uri(self) -> None:
        registry = MagicMock()
        registry.has_override.return_value = True
        pkg_manifest: dict[str, Any] = {
            "mcp_resources": {"agents": ["spark-guide"]}
        }
        result = _v3_overrides_blocking_update(registry, "p", pkg_manifest)
        assert len(result) >= 1
