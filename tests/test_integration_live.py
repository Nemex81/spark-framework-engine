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
    # Inizializza lo stato runtime con github_write_authorized=True in modo che
    # il gate _is_github_write_authorized_v3() in lifecycle.py non blocchi le
    # scritture su .github/ durante i test di installazione. Senza questo file
    # tutti i tool install/remove restituiscono 'not authorized' prima ancora
    # di toccare la rete o lo store.
    runtime_dir = github_root / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "orchestrator-state.json").write_text(
        json.dumps(
            {
                "github_write_authorized": True,
                "current_phase": "",
                "current_agent": "",
                "retry_count": 0,
                "confidence": 1.0,
                "execution_mode": "autonomous",
                "last_updated": "",
                "phase_history": [],
                "active_task_id": "",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
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
    # workspace_files e plugin_files sono le categorie scritte su disco.
    # Le altre voci in "files" (changelogs, skills, prompts) sono servite
    # solo via MCP dallo store del motore e non compaiono nel workspace.
    installed_paths: list[str] = list(
        dict.fromkeys(
            master_manifest.get("workspace_files", [])
            + master_manifest.get("plugin_files", [])
        )
    )
    expected_files = {path.removeprefix(".github/") for path in installed_paths}

    base_result = asyncio.run(install_package("spark-base"))

    assert base_result["success"] is True, base_result

    result = asyncio.run(install_package("scf-master-codecrafter"))

    assert result["success"] is True, result
    for file_rel in installed_paths:
        assert (tmp_workspace.workspace_root / file_rel).is_file()

    manifest_path = tmp_workspace.github_root / ".scf-manifest.json"
    assert manifest_path.is_file()
    entries = _manifest_entries(tmp_workspace.github_root)
    # Le entry `__store__/{pkg}` sono sentinelle interne del v3 store e non
    # corrispondono a file fisici nel workspace — vanno escluse dall'assertion
    # che verifica i file scritti su disco.
    master_entries = [
        entry
        for entry in entries
        if entry["package"] == "scf-master-codecrafter"
        and not str(entry.get("file", "")).startswith("__store__/")
    ]
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
    # scf_plan_install usa `files` (19 voci: agenti + changelogs + skills + prompts).
    # Le voci store-only (changelogs, skills, prompts) appaiono come "create_new"
    # perché sono solo nello store MCP, non nel workspace. Verifichiamo che
    # tutti i file *installati* (workspace_files + plugin_files = 14) siano
    # classificati come update/extend e non finiscano in conflict/preserve_plan.
    planned_files = {item["file"] for item in replan["write_plan"] + replan["extend_plan"]}
    for rel in expected_files:
        assert f".github/{rel}" in planned_files, f".github/{rel} not in write/extend plan"
    installed_items = [
        item
        for item in replan["write_plan"] + replan["extend_plan"]
        if item["file"].removeprefix(".github/") in expected_files
    ]
    assert len(installed_items) == len(expected_files)
    assert all(
        item.get("classification") in ("update_tracked_clean", "extend_section")
        for item in installed_items
    )
    assert any(
        item["file"] == ".github/copilot-instructions.md"
        and item["classification"] == "extend_section"
        for item in replan["extend_plan"]
    )


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

    # Il file di conflitto deve corrispondere a un file nei plugin_files del
    # pacchetto master; il nome corretto dopo il rinominamento con prefisso
    # "code-" è "code-Agent-Code.md", non il vecchio "Agent-Code.md".
    conflict_rel = ".github/agents/code-Agent-Code.md"
    conflict_path = tmp_workspace.workspace_root / conflict_rel
    conflict_path.parent.mkdir(parents=True, exist_ok=True)
    conflict_path.write_text("file utente non tracciato", encoding="utf-8")
    base_existing_files = {
        file_rel for file_rel in master_manifest["files"] if (tmp_workspace.workspace_root / file_rel).exists()
    }

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
        if file_rel in base_existing_files:
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
