from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

ManifestManager: Any = _module.ManifestManager
SparkFrameworkEngine: Any = _module.SparkFrameworkEngine
WorkspaceContext: Any = _module.WorkspaceContext
FrameworkInventory: Any = _module.FrameworkInventory

import spark.boot.engine as boot_engine
import spark.boot.tools_bootstrap as _tools_bootstrap


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


@pytest.fixture()
def workspace_root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def bootstrap_tool(workspace_root: Path) -> Any:
    ctx = WorkspaceContext(
        workspace_root=workspace_root,
        github_root=workspace_root / ".github",
        engine_root=_ENGINE_PATH.parent,
    )
    inventory = FrameworkInventory(ctx)
    mcp = _FakeMCP()
    engine = SparkFrameworkEngine(mcp, ctx, inventory)
    engine.register_tools()
    return mcp.tools["scf_bootstrap_workspace"]


def _authorize_github_writes(workspace_root: Path) -> None:
    state_path = workspace_root / ".github" / "runtime" / "orchestrator-state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"github_write_authorized": True}, indent=2),
        encoding="utf-8",
    )


async def test_bootstrap_extended_authorized_writes_policy_and_phase6_assets(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    _authorize_github_writes(workspace_root)

    result = await bootstrap_tool(update_mode="integrative")

    prefs_path = Path(result["policy_path"])
    agents_md = workspace_root / ".github" / "AGENTS.md"
    profile_path = workspace_root / ".github" / "project-profile.md"

    assert result["success"] is True
    assert result["status"] == "bootstrapped"
    assert result["policy_created"] is True
    assert result["github_write_authorized"] is True
    assert result["phase6_assets"]["agents_md"] == "written"
    assert prefs_path.name == "user-prefs.json"
    assert prefs_path.is_file()
    assert agents_md.is_file()
    assert profile_path.is_file()


async def test_bootstrap_preserves_missing_cross_owner_file_without_rewriting(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    manifest = ManifestManager(workspace_root / ".github")
    guide_rel = "agents/spark-guide.agent.md"
    guide_path = workspace_root / ".github" / guide_rel
    guide_path.parent.mkdir(parents=True, exist_ok=True)
    guide_path.write_text("spark-base owned guide\n", encoding="utf-8")
    manifest.upsert_many("spark-base", "1.2.0", [(guide_rel, guide_path)])
    guide_path.unlink()

    result = await bootstrap_tool()

    assert result["success"] is True
    assert result["status"] == "bootstrapped"
    assert ".github/agents/spark-guide.agent.md" in result["preserved"]
    assert not guide_path.exists()
    assert manifest.get_file_owners(guide_rel) == ["spark-base"]


async def test_bootstrap_writes_sentinel_last(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    write_order: list[str] = []

    def _record_gateway_write_bytes(
        root: Path,
        github_rel: str,
        content: bytes,
        manifest_manager: Any,
        owner: str,
        version: str,
    ) -> Path:
        write_order.append(github_rel)
        target = root / ".github" / github_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        manifest_manager.upsert(github_rel, owner, version, target)
        return target

    with patch.object(
        _tools_bootstrap,
        "_gateway_write_bytes",
        side_effect=_record_gateway_write_bytes,
    ):
        result = await bootstrap_tool()

    assert result["success"] is True
    assert write_order
    assert write_order[-1] == "agents/spark-assistant.agent.md"
    assert write_order.count("agents/spark-assistant.agent.md") == 1


# ---------------------------------------------------------------------------
# v3.1 tests: force and dry_run parameters
# ---------------------------------------------------------------------------


async def test_bootstrap_dry_run_reports_would_copy_without_writing(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    """dry_run=True: files_copied is populated but nothing is written to disk."""
    result = await bootstrap_tool(dry_run=True)

    assert result["success"] is True
    assert result["status"] == "bootstrapped"
    # files_copied shows what would be written
    assert len(result["files_copied"]) > 0
    # files_written is empty — nothing was actually written
    assert result["files_written"] == []
    # No actual files created on disk
    github_root = workspace_root / ".github"
    assert not (github_root / "agents" / "spark-assistant.agent.md").exists()
    assert not (github_root / "AGENTS.md").exists()


async def test_bootstrap_dry_run_reports_files_skipped_when_already_bootstrapped(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    """dry_run after real bootstrap: files_skipped lists all already-present files."""
    # First real bootstrap
    first = await bootstrap_tool()
    assert first["status"] == "bootstrapped"

    # Second call with dry_run=True — sentinel is present and matches, so
    # the fast-path returns already_bootstrapped with files_skipped populated.
    second = await bootstrap_tool(dry_run=True)
    assert second["success"] is True
    assert second["status"] == "already_bootstrapped"
    assert len(second["files_skipped"]) > 0
    assert second["files_copied"] == []


async def test_bootstrap_new_fields_present_on_fresh_bootstrap(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    """All v3.1 new fields must be present in a fresh bootstrap result."""
    result = await bootstrap_tool()

    assert result["status"] == "bootstrapped"
    for field in ("files_copied", "files_skipped", "files_protected", "sentinel_present", "message"):
        assert field in result, f"Missing v3.1 field: {field}"
    assert isinstance(result["files_copied"], list)
    assert isinstance(result["files_skipped"], list)
    assert isinstance(result["files_protected"], list)
    assert isinstance(result["sentinel_present"], bool)
    assert isinstance(result["message"], str)
    # After bootstrap, sentinel is present
    assert result["sentinel_present"] is True


async def test_bootstrap_returns_files_protected_for_non_sentinel_user_modified(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    """Without force, a user-modified non-sentinel file is in files_protected."""
    # First bootstrap
    first = await bootstrap_tool()
    assert first["status"] == "bootstrapped"

    # Modify a non-sentinel bootstrap file (copilot-instructions.md)
    copilot_md = workspace_root / ".github" / "copilot-instructions.md"
    assert copilot_md.is_file()
    copilot_md.write_text("# user customized content\n", encoding="utf-8")

    # Delete sentinel to force re-run through copy loop
    sentinel = workspace_root / ".github" / "agents" / "spark-assistant.agent.md"
    sentinel.unlink()

    # Second bootstrap without force — copilot-instructions.md should be protected
    second = await bootstrap_tool()
    assert second["success"] is True
    assert ".github/copilot-instructions.md" in second["files_protected"]
    assert ".github/copilot-instructions.md" not in second["files_written"]
    # User content preserved
    assert copilot_md.read_text(encoding="utf-8") == "# user customized content\n"


async def test_bootstrap_force_overwrites_user_modified_non_sentinel_file(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    """force=True overwrites a user-modified non-sentinel file."""
    # First bootstrap
    first = await bootstrap_tool()
    assert first["status"] == "bootstrapped"

    copilot_md = workspace_root / ".github" / "copilot-instructions.md"
    original_content = copilot_md.read_bytes()
    copilot_md.write_text("# user customized content\n", encoding="utf-8")

    # Delete sentinel to force re-run through copy loop
    sentinel = workspace_root / ".github" / "agents" / "spark-assistant.agent.md"
    sentinel.unlink()

    # Second bootstrap with force=True — copilot-instructions.md should be overwritten
    second = await bootstrap_tool(force=True)
    assert second["success"] is True
    assert ".github/copilot-instructions.md" not in second["files_protected"]
    assert ".github/copilot-instructions.md" in second["files_copied"]
    # Content restored to engine source
    assert copilot_md.read_bytes() == original_content


async def test_bootstrap_force_overwrites_user_modified_sentinel(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    """force=True overrides the user_modified sentinel gate and bootstraps."""
    # First bootstrap
    first = await bootstrap_tool()
    assert first["status"] == "bootstrapped"

    # Modify the sentinel so is_user_modified returns True
    sentinel = workspace_root / ".github" / "agents" / "spark-assistant.agent.md"
    sentinel.write_text("# user modified sentinel\n", encoding="utf-8")

    # Without force: user_modified
    no_force = await bootstrap_tool()
    assert no_force["status"] == "user_modified"
    assert no_force["files_protected"] == ["agents/spark-assistant.agent.md"]

    # With force=True: should proceed and NOT return user_modified
    with_force = await bootstrap_tool(force=True)
    assert with_force["status"] == "bootstrapped"
    assert with_force["success"] is True
    # Sentinel must have been overwritten
    assert sentinel.read_text(encoding="utf-8") != "# user modified sentinel\n"


async def test_bootstrap_files_skipped_populated_after_identical_rerun(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    """files_skipped is populated when files already match source SHA."""
    # First bootstrap
    first = await bootstrap_tool()
    assert first["status"] == "bootstrapped"

    # Delete sentinel to force re-run through copy loop
    sentinel = workspace_root / ".github" / "agents" / "spark-assistant.agent.md"
    sentinel.unlink()

    # Second bootstrap: all files except sentinel are present with matching SHA
    second = await bootstrap_tool()
    assert second["success"] is True
    assert len(second["files_skipped"]) > 0
    # files_protected should be empty (no user-modified files)
    assert second["files_protected"] == []
