from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

ManifestManager: Any = _module.ManifestManager
SparkFrameworkEngine: Any = _module.SparkFrameworkEngine
WorkspaceContext: Any = _module.WorkspaceContext
FrameworkInventory: Any = _module.FrameworkInventory

import spark.boot.engine as boot_engine


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


def test_bootstrap_extended_authorized_writes_policy_and_phase6_assets(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    _authorize_github_writes(workspace_root)

    result = asyncio.run(bootstrap_tool(update_mode="integrative"))

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


def test_bootstrap_preserves_missing_cross_owner_file_without_rewriting(
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

    result = asyncio.run(bootstrap_tool())

    assert result["success"] is True
    assert result["status"] == "bootstrapped"
    assert ".github/agents/spark-guide.agent.md" in result["preserved"]
    assert not guide_path.exists()
    assert manifest.get_file_owners(guide_rel) == ["spark-base"]


def test_bootstrap_writes_sentinel_last(
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
        boot_engine,
        "_gateway_write_bytes",
        side_effect=_record_gateway_write_bytes,
    ):
        result = asyncio.run(bootstrap_tool())

    assert result["success"] is True
    assert write_order
    assert write_order[-1] == "agents/spark-assistant.agent.md"
    assert write_order.count("agents/spark-assistant.agent.md") == 1
