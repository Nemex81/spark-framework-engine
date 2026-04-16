"""Live integration tests for SCF package installation flows."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Coroutine, cast
from unittest.mock import MagicMock

import pytest

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

FrameworkInventory = _module.FrameworkInventory
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


@dataclass(frozen=True)
class LiveWorkspace:
    workspace_root: Path
    github_root: Path
    mcp: FakeMCP

    @property
    def registry(self) -> Any:
        return RegistryClient(self.github_root)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_entries(github_root: Path) -> list[dict[str, Any]]:
    manifest_path = github_root / ".scf-manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return list(payload["entries"])


def _remote_manifest(workspace: LiveWorkspace, package_id: str) -> dict[str, Any]:
    repo_url = f"https://github.com/Nemex81/{package_id}"
    return cast(dict[str, Any], workspace.registry.fetch_package_manifest(repo_url))


def _tool(
    workspace: LiveWorkspace,
    name: str,
) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
    return cast(Callable[..., Coroutine[Any, Any, dict[str, Any]]], workspace.mcp.tools[name])


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> LiveWorkspace:
    github_root = tmp_path / ".github"
    github_root.mkdir(parents=True, exist_ok=True)
    context = WorkspaceContext(
        workspace_root=tmp_path,
        github_root=github_root,
        engine_root=tmp_path / "spark-framework-engine",
    )
    inventory = FrameworkInventory(context)
    fake_mcp = FakeMCP()
    engine = SparkFrameworkEngine(fake_mcp, context, inventory)
    engine.register_tools()
    return LiveWorkspace(workspace_root=tmp_path, github_root=github_root, mcp=fake_mcp)


@pytest.mark.integration
def test_install_clean_master_package_creates_manifest_and_replan_is_clean(
    tmp_workspace: LiveWorkspace,
) -> None:
    install_package = _tool(tmp_workspace, "scf_install_package")
    plan_install = _tool(tmp_workspace, "scf_plan_install")
    master_manifest = _remote_manifest(tmp_workspace, "scf-master-codecrafter")
    expected_files = {path.removeprefix(".github/") for path in master_manifest["files"]}

    base_result = asyncio.run(install_package("spark-base"))

    assert base_result["success"] is True, base_result

    result = asyncio.run(install_package("scf-master-codecrafter"))

    assert result["success"] is True, result
    for file_rel in master_manifest["files"]:
        assert (tmp_workspace.workspace_root / file_rel).is_file()

    manifest_path = tmp_workspace.github_root / ".scf-manifest.json"
    assert manifest_path.is_file()
    entries = _manifest_entries(tmp_workspace.github_root)
    master_entries = [entry for entry in entries if entry["package"] == "scf-master-codecrafter"]
    assert {entry["file"] for entry in master_entries} == expected_files
    for entry in master_entries:
        assert set(entry) >= {"file", "package", "package_version", "installed_at", "sha256"}
        file_on_disk = tmp_workspace.github_root / entry["file"]
        assert _sha256(file_on_disk) == entry["sha256"]

    replan = asyncio.run(plan_install("scf-master-codecrafter"))

    assert replan["success"] is True
    assert replan["conflict_plan"] == []
    assert replan["preserve_plan"] == []
    assert replan["can_install"] is True
    assert replan["can_install_with_replace"] is True
    assert len(replan["write_plan"]) == len(expected_files)
    assert all(item["classification"] == "update_tracked_clean" for item in replan["write_plan"])


@pytest.mark.integration
def test_plan_and_install_master_package_require_spark_base_first(
    tmp_workspace: LiveWorkspace,
) -> None:
    plan_install = _tool(tmp_workspace, "scf_plan_install")
    install_package = _tool(tmp_workspace, "scf_install_package")

    plan = asyncio.run(plan_install("scf-master-codecrafter"))

    assert plan["success"] is True
    assert plan["can_install"] is False
    assert any(
        "spark-base" in issue.get("missing_dependencies", [])
        for issue in plan["dependency_issues"]
    )

    result = asyncio.run(install_package("scf-master-codecrafter"))

    assert result["success"] is False
    assert "spark-base" in result["missing_dependencies"]
    assert not (tmp_workspace.github_root / ".scf-manifest.json").exists()


@pytest.mark.integration
def test_plan_install_detects_untracked_conflict_and_abort_preserves_workspace(
    tmp_workspace: LiveWorkspace,
) -> None:
    plan_install = _tool(tmp_workspace, "scf_plan_install")
    install_package = _tool(tmp_workspace, "scf_install_package")
    master_manifest = _remote_manifest(tmp_workspace, "scf-master-codecrafter")
    base_result = asyncio.run(install_package("spark-base"))

    assert base_result["success"] is True, base_result

    conflict_rel = ".github/agents/Agent-Code.md"
    conflict_path = tmp_workspace.workspace_root / conflict_rel
    conflict_path.parent.mkdir(parents=True, exist_ok=True)
    conflict_path.write_text("file utente non tracciato", encoding="utf-8")

    plan = asyncio.run(plan_install("scf-master-codecrafter"))

    assert plan["success"] is True
    assert plan["can_install"] is False
    assert plan["can_install_with_replace"] is True
    assert any(
        item["file"] == conflict_rel
        and item["classification"] == "conflict_untracked_existing"
        for item in plan["conflict_plan"]
    )

    result = asyncio.run(install_package("scf-master-codecrafter", conflict_mode="abort"))

    assert result["success"] is False
    assert conflict_path.read_text(encoding="utf-8") == "file utente non tracciato"
    manifest_path = tmp_workspace.github_root / ".scf-manifest.json"
    assert manifest_path.exists()
    entries = _manifest_entries(tmp_workspace.github_root)
    assert not any(entry["package"] == "scf-master-codecrafter" for entry in entries)
    for file_rel in master_manifest["files"]:
        target_path = tmp_workspace.workspace_root / file_rel
        if target_path == conflict_path:
            continue
        assert not target_path.exists()


@pytest.mark.integration
def test_plan_and_install_block_python_package_without_master_dependency(
    tmp_workspace: LiveWorkspace,
) -> None:
    plan_install = _tool(tmp_workspace, "scf_plan_install")
    install_package = _tool(tmp_workspace, "scf_install_package")
    python_manifest = _remote_manifest(tmp_workspace, "scf-pycode-crafter")

    plan = asyncio.run(plan_install("scf-pycode-crafter"))

    assert plan["success"] is True
    assert plan["can_install"] is False
    assert len(plan["dependency_issues"]) >= 1
    assert any(
        "scf-master-codecrafter" in issue.get("missing_dependencies", [])
        for issue in plan["dependency_issues"]
    )

    result = asyncio.run(install_package("scf-pycode-crafter"))

    assert result["success"] is False
    assert "scf-master-codecrafter" in result["missing_dependencies"]
    assert not (tmp_workspace.github_root / ".scf-manifest.json").exists()
    for file_rel in python_manifest["files"]:
        assert not (tmp_workspace.workspace_root / file_rel).exists()
