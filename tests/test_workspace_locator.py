from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_MODULE = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _MODULE
assert _spec is not None
assert _spec.loader is not None
_spec.loader.exec_module(_MODULE)  # type: ignore[union-attr]


def test_workspace_locator_uses_workspace_folder_for_existing_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setenv("WORKSPACE_FOLDER", str(project_root))
    monkeypatch.chdir(tmp_path)

    ctx = _MODULE.WorkspaceLocator(engine_root=tmp_path).resolve()

    assert ctx.workspace_root == project_root
    assert ctx.github_root == project_root / ".github"


def test_workspace_locator_uses_workspace_flag_before_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli_root = tmp_path / "cli-project"
    env_root = tmp_path / "env-project"
    cli_root.mkdir()
    env_root.mkdir()
    monkeypatch.setenv("WORKSPACE_FOLDER", str(env_root))
    monkeypatch.setattr(sys, "argv", ["spark-framework-engine.py", "--workspace", str(cli_root)])
    monkeypatch.chdir(tmp_path)

    ctx = _MODULE.WorkspaceLocator(engine_root=tmp_path).resolve()

    assert ctx.workspace_root == cli_root
    assert ctx.github_root == cli_root / ".github"


def test_workspace_locator_discovers_workspace_from_local_vscode_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    nested = project_root / "src" / "feature"
    (project_root / ".vscode").mkdir(parents=True)
    (project_root / ".vscode" / "settings.json").write_text("{}", encoding="utf-8")
    nested.mkdir(parents=True)
    monkeypatch.delenv("WORKSPACE_FOLDER", raising=False)
    monkeypatch.chdir(nested)

    ctx = _MODULE.WorkspaceLocator(engine_root=tmp_path).resolve()

    assert ctx.workspace_root == project_root


def test_workspace_locator_discovers_workspace_from_scf_github_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    nested = project_root / "pkg"
    (project_root / ".github" / "prompts").mkdir(parents=True)
    (project_root / ".github" / "prompts" / "scf-demo.prompt.md").write_text(
        "prompt",
        encoding="utf-8",
    )
    nested.mkdir(parents=True)
    monkeypatch.delenv("WORKSPACE_FOLDER", raising=False)
    monkeypatch.chdir(nested)

    ctx = _MODULE.WorkspaceLocator(engine_root=tmp_path).resolve()

    assert ctx.workspace_root == project_root


def test_workspace_locator_ignores_home_env_without_workspace_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_home = tmp_path / "home"
    project_root = tmp_path / "project"
    fake_home.mkdir()
    (fake_home / ".github").mkdir()
    (project_root / ".vscode").mkdir(parents=True)
    (project_root / ".vscode" / "settings.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(_MODULE.Path, "home", lambda: fake_home)
    monkeypatch.setenv("WORKSPACE_FOLDER", str(fake_home))
    monkeypatch.chdir(project_root)

    ctx = _MODULE.WorkspaceLocator(engine_root=tmp_path).resolve()

    assert ctx.workspace_root == project_root


def test_workspace_locator_falls_back_to_cwd_when_no_markers_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.delenv("WORKSPACE_FOLDER", raising=False)
    monkeypatch.chdir(project_root)

    with caplog.at_level("WARNING"):
        ctx = _MODULE.WorkspaceLocator(engine_root=tmp_path).resolve()

    assert ctx.workspace_root == project_root
    assert "Falling back to cwd" in caplog.text
