"""Unit tests for spark.boot.install_helpers — pure and mocked paths."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from spark.boot.install_helpers import (
    _build_diff_summary,
    _build_install_result,
    _classify_install_files,
    _get_package_install_context,
    _normalize_file_policies,
    _read_text_if_possible,
    _resolve_effective_update_mode,
    _save_snapshots,
    _supports_stateful_merge,
)


# ============================================================================ #
# Group A — pure helpers (no I/O)                                               #
# ============================================================================ #


class TestInstallHelpersCore:
    """Test funzioni pure che non richiedono filesystem reale."""

    # ------------------------------------------------------------------ #
    # _build_install_result                                                #
    # ------------------------------------------------------------------ #

    def test_build_install_result_success(self) -> None:
        result = _build_install_result(
            True,
            package="test-pkg",
            version="1.0.0",
        )
        assert result["success"] is True
        assert result["package"] == "test-pkg"
        assert result["version"] == "1.0.0"

    def test_build_install_result_failure(self) -> None:
        result = _build_install_result(False, error="test error")
        assert result["success"] is False
        assert result["error"] == "test error"

    def test_build_install_result_has_standard_keys(self) -> None:
        result = _build_install_result(True)
        for key in ("installed", "preserved", "merge_clean", "merge_conflict"):
            assert key in result

    # ------------------------------------------------------------------ #
    # _resolve_effective_update_mode                                       #
    # ------------------------------------------------------------------ #

    def test_resolve_update_mode_no_policy(self) -> None:
        result = _resolve_effective_update_mode(
            package_id="p",
            requested_update_mode="",
            diff_records=[],
            policy_payload={},
            policy_source="",
        )
        assert isinstance(result, dict)
        assert "mode" in result

    def test_resolve_update_mode_explicit(self) -> None:
        result = _resolve_effective_update_mode(
            package_id="p",
            requested_update_mode="integrative",
            diff_records=[],
            policy_payload={},
            policy_source="",
        )
        assert result["mode"] == "integrative"
        assert result["source"] == "explicit"

    def test_resolve_update_mode_policy_default(self) -> None:
        policy_payload: dict[str, Any] = {
            "update_policy": {"default_mode": "replace", "auto_update": False}
        }
        result = _resolve_effective_update_mode(
            package_id="pkg-x",
            requested_update_mode="",
            diff_records=[],
            policy_payload=policy_payload,
            policy_source="file",
        )
        assert result["mode"] == "replace"

    # ------------------------------------------------------------------ #
    # _normalize_file_policies                                             #
    # ------------------------------------------------------------------ #

    def test_normalize_empty_dict(self) -> None:
        result = _normalize_file_policies({})
        assert isinstance(result, dict)

    def test_normalize_with_entry(self) -> None:
        result = _normalize_file_policies(
            {".github/agents/test.agent.md": "extend"}
        )
        assert isinstance(result, dict)

    def test_normalize_extend_policy(self) -> None:
        result = _normalize_file_policies(
            {".github/copilot-instructions.md": "extend"}
        )
        assert result.get(".github/copilot-instructions.md") == "extend"

    def test_normalize_non_github_path_ignored(self) -> None:
        result = _normalize_file_policies({"agents/test.md": "extend"})
        assert "agents/test.md" not in result

    def test_normalize_from_files_metadata(self) -> None:
        raw_meta = [
            {
                "path": ".github/copilot-instructions.md",
                "scf_merge_strategy": "merge_sections",
            }
        ]
        result = _normalize_file_policies({}, raw_meta)
        assert result.get(".github/copilot-instructions.md") == "extend"

    # ------------------------------------------------------------------ #
    # _build_diff_summary                                                  #
    # ------------------------------------------------------------------ #

    def test_build_diff_summary_empty(self) -> None:
        result = _build_diff_summary([])
        assert result["total"] == 0
        assert result["counts"] == {}
        assert result["files"] == []

    def test_build_diff_summary_with_records(self) -> None:
        records = [
            {
                "file": ".github/agents/test.agent.md",
                "status": "modified",
                "scf_file_role": "agent",
                "scf_merge_strategy": "replace",
                "scf_protected": False,
            }
        ]
        result = _build_diff_summary(records)
        assert result["total"] >= 1
        assert "modified" in result["counts"]

    def test_build_diff_summary_excludes_unchanged(self) -> None:
        records = [
            {"file": "a.md", "status": "unchanged"},
            {"file": "b.md", "status": "added"},
        ]
        result = _build_diff_summary(records)
        assert result["total"] == 1

    # ------------------------------------------------------------------ #
    # _supports_stateful_merge                                             #
    # ------------------------------------------------------------------ #

    def test_supports_stateful_merge_true_manual(self) -> None:
        assert _supports_stateful_merge("manual") is True

    def test_supports_stateful_merge_true_auto(self) -> None:
        assert _supports_stateful_merge("auto") is True

    def test_supports_stateful_merge_true_assisted(self) -> None:
        assert _supports_stateful_merge("assisted") is True

    def test_supports_stateful_merge_false_abort(self) -> None:
        assert _supports_stateful_merge("abort") is False

    def test_supports_stateful_merge_false_replace(self) -> None:
        assert _supports_stateful_merge("replace") is False

    # ------------------------------------------------------------------ #
    # _read_text_if_possible                                               #
    # ------------------------------------------------------------------ #

    def test_read_text_existing_file(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write("# test content\n")
            tmp_path = Path(f.name)
        try:
            content = _read_text_if_possible(tmp_path)
            assert content is not None
            assert "test content" in content
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_read_text_missing_file(self) -> None:
        result = _read_text_if_possible(Path("/nonexistent/path/file.md"))
        assert result is None


# ============================================================================ #
# Group B — helpers requiring mocks                                             #
# ============================================================================ #


class TestInstallHelpersMocked:
    """Test che richiedono mock di oggetti dipendenti."""

    # ------------------------------------------------------------------ #
    # _save_snapshots                                                       #
    # ------------------------------------------------------------------ #

    def test_save_snapshots_calls_snapshot_manager(self) -> None:
        snapshots = MagicMock()
        snapshots.save_snapshot.return_value = True
        result = _save_snapshots(
            "pkg",
            [("rel/file.md", Path("/fake/path/file.md"))],
            snapshots,
        )
        assert snapshots.save_snapshot.called is True
        assert isinstance(result, dict)
        assert "written" in result

    def test_save_snapshots_skipped_on_false(self) -> None:
        snapshots = MagicMock()
        snapshots.save_snapshot.return_value = False
        result = _save_snapshots(
            "pkg",
            [("rel/file.md", Path("/fake/path/file.md"))],
            snapshots,
        )
        assert len(result["skipped"]) == 1
        assert len(result["written"]) == 0

    def test_save_snapshots_empty_list(self) -> None:
        snapshots = MagicMock()
        result = _save_snapshots("pkg", [], snapshots)
        assert result["written"] == []
        assert result["skipped"] == []
        snapshots.save_snapshot.assert_not_called()

    # ------------------------------------------------------------------ #
    # _get_package_install_context                                         #
    # ------------------------------------------------------------------ #

    def test_get_package_install_context_not_found(self) -> None:
        registry = MagicMock()
        registry.list_packages.return_value = []
        manifest = MagicMock()
        result = _get_package_install_context(
            package_id="nonexistent",
            registry=registry,
            manifest=manifest,
        )
        assert result["success"] is False
        assert "error" in result

    def test_get_package_install_context_found(self) -> None:
        registry = MagicMock()
        registry.list_packages.return_value = [
            {
                "id": "spark-base",
                "repo_url": "https://github.com/Nemex81/spark-base",
                "latest_version": "1.5.0",
                "status": "active",
            }
        ]
        registry.fetch_package_manifest.return_value = {
            "package": "spark-base",
            "version": "1.5.0",
            "min_engine_version": "2.4.0",
            "files": [".github/AGENTS.md"],
            "dependencies": [],
            "conflicts": [],
            "file_ownership_policy": "error",
        }
        manifest = MagicMock()
        manifest.get_installed_versions.return_value = {}
        result = _get_package_install_context(
            package_id="spark-base",
            registry=registry,
            manifest=manifest,
        )
        assert result.get("success") is not False
        assert "pkg_manifest" in result or "error" in result

    def test_get_package_install_context_registry_error(self) -> None:
        registry = MagicMock()
        registry.list_packages.side_effect = RuntimeError("network error")
        manifest = MagicMock()
        result = _get_package_install_context(
            package_id="any",
            registry=registry,
            manifest=manifest,
        )
        assert result["success"] is False
        assert "error" in result

    # ------------------------------------------------------------------ #
    # _classify_install_files                                              #
    # ------------------------------------------------------------------ #

    def test_classify_install_files_empty_list(self) -> None:
        manifest = MagicMock()
        manifest.get_file_owners.return_value = []
        manifest.is_user_modified.return_value = False
        snapshots = MagicMock()
        workspace_root = Path("/tmp")
        result = _classify_install_files(
            package_id="p",
            files=[],
            manifest=manifest,
            workspace_root=workspace_root,
            snapshots=snapshots,
        )
        assert isinstance(result, dict)
        assert "records" in result
        assert "conflict_plan" in result

    def test_classify_install_files_new_file(
        self, tmp_path: Path
    ) -> None:
        manifest = MagicMock()
        manifest.get_file_owners.return_value = []
        manifest.is_user_modified.return_value = False
        snapshots = MagicMock()
        result = _classify_install_files(
            package_id="pkg-x",
            files=[".github/agents/test.agent.md"],
            manifest=manifest,
            workspace_root=tmp_path,
            snapshots=snapshots,
        )
        assert len(result["records"]) == 1
        assert result["records"][0]["classification"] == "create_new"
