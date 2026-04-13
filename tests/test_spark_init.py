from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


_MODULE_PATH = Path(__file__).parent.parent / "spark-init.py"
_SPEC = importlib.util.spec_from_file_location("spark_init", _MODULE_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules["spark_init"] = _MODULE
_SPEC.loader.exec_module(_MODULE)


def test_build_workspace_template_returns_empty_settings_and_root_mcp(tmp_path: Path) -> None:
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    engine_script = tmp_path / "spark-framework-engine.py"

    workspace_data = _MODULE._build_workspace_template(project_root, engine_script)

    assert workspace_data["settings"] == {}
    assert "mcp" in workspace_data
    assert "servers" in workspace_data["mcp"]
    assert workspace_data["mcp"]["servers"][_MODULE.SERVER_ID]["args"] == [str(engine_script)]


def test_update_existing_workspace_moves_legacy_settings_mcp_to_root_and_preserves_other_keys(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    engine_script = tmp_path / "spark-framework-engine.py"
    workspace_path = project_root / "demo.code-workspace"
    workspace_path.write_text(
        """{
  "folders": [{"path": "."}],
  "settings": {
    "editor.tabSize": 4,
    "mcp": {
      "servers": {
        "legacy": {
          "type": "stdio"
        }
      }
    }
  },
  "extensions": {
    "recommendations": ["ms-python.python"]
  },
  "launch": {
    "configurations": []
  }
}
""",
        encoding="utf-8",
    )

    success, _message = _MODULE._update_existing_workspace(
        workspace_path,
        project_root,
        engine_script,
    )

    assert success is True

    workspace_data = _MODULE.json.loads(workspace_path.read_text(encoding="utf-8"))

    assert workspace_data["settings"] == {"editor.tabSize": 4}
    assert "mcp" in workspace_data
    assert "mcp" not in workspace_data["settings"]
    assert workspace_data["extensions"] == {
        "recommendations": ["ms-python.python"]
    }
    assert workspace_data["launch"] == {"configurations": []}
    assert workspace_data["mcp"]["servers"][_MODULE.SERVER_ID] == _MODULE._build_server_config(
        project_root,
        engine_script,
    )


def test_update_existing_workspace_returns_error_when_root_mcp_is_not_an_object(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    engine_script = tmp_path / "spark-framework-engine.py"
    workspace_path = project_root / "demo.code-workspace"
    workspace_path.write_text(
        """{
  "settings": {},
  "mcp": []
}
""",
        encoding="utf-8",
    )

    success, message = _MODULE._update_existing_workspace(
        workspace_path,
        project_root,
        engine_script,
    )

    assert success is False
    assert "la chiave 'mcp' deve essere un oggetto JSON" in message


# ---------------------------------------------------------------------------
# _write_vscode_mcp_json
# ---------------------------------------------------------------------------


def test_write_vscode_mcp_json_creates_file_when_absent(tmp_path: Path) -> None:
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    engine_script = tmp_path / "spark-framework-engine.py"

    success, action = _MODULE._write_vscode_mcp_json(
        project_root,
        engine_script,
    )

    mcp_path = project_root / ".vscode" / "mcp.json"
    assert mcp_path.exists()
    assert success is True
    assert action == "creato"
    data = _MODULE.json.loads(mcp_path.read_text(encoding="utf-8"))
    assert "servers" in data
    assert _MODULE.SERVER_ID in data["servers"]
    assert data["servers"][_MODULE.SERVER_ID]["args"] == [str(engine_script)]


def test_write_vscode_mcp_json_preserves_other_servers(tmp_path: Path) -> None:
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    engine_script = tmp_path / "spark-framework-engine.py"
    vscode_dir = project_root / ".vscode"
    vscode_dir.mkdir()
    mcp_path = vscode_dir / "mcp.json"
    mcp_path.write_text(
        '{"servers": {"other-server": {"type": "stdio"}}}',
        encoding="utf-8",
    )

    success, action = _MODULE._write_vscode_mcp_json(
        project_root,
        engine_script,
    )

    data = _MODULE.json.loads(mcp_path.read_text(encoding="utf-8"))
    assert success is True
    assert action == "aggiornato"
    assert "other-server" in data["servers"]
    assert _MODULE.SERVER_ID in data["servers"]


def test_write_vscode_mcp_json_handles_corrupted_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    engine_script = tmp_path / "spark-framework-engine.py"
    vscode_dir = project_root / ".vscode"
    vscode_dir.mkdir()
    mcp_path = vscode_dir / "mcp.json"
    mcp_path.write_text("{not valid json{{", encoding="utf-8")

    success, action = _MODULE._write_vscode_mcp_json(
        project_root,
        engine_script,
    )

    captured = capsys.readouterr()
    assert success is True
    assert action == "aggiornato"
    assert "[SPARK-INIT][ERROR]" in captured.err
    data = _MODULE.json.loads(mcp_path.read_text(encoding="utf-8"))
    assert _MODULE.SERVER_ID in data["servers"]


def test_write_vscode_mcp_json_handles_non_dict_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    engine_script = tmp_path / "spark-framework-engine.py"
    vscode_dir = project_root / ".vscode"
    vscode_dir.mkdir()
    (vscode_dir / "mcp.json").write_text("[1, 2, 3]", encoding="utf-8")

    success, action = _MODULE._write_vscode_mcp_json(
        project_root,
        engine_script,
    )

    captured = capsys.readouterr()
    assert success is True
    assert action == "aggiornato"
    assert "[SPARK-INIT][ERROR]" in captured.err
    data = _MODULE.json.loads((vscode_dir / "mcp.json").read_text(encoding="utf-8"))
    assert _MODULE.SERVER_ID in data["servers"]


def test_write_vscode_mcp_json_handles_invalid_servers_shape(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    engine_script = tmp_path / "spark-framework-engine.py"
    vscode_dir = project_root / ".vscode"
    vscode_dir.mkdir()
    mcp_path = vscode_dir / "mcp.json"
    mcp_path.write_text(
        '{"servers": []}',
        encoding="utf-8",
    )

    success, action = _MODULE._write_vscode_mcp_json(
        project_root,
        engine_script,
    )

    captured = capsys.readouterr()
    data = _MODULE.json.loads(mcp_path.read_text(encoding="utf-8"))
    assert success is True
    assert action == "aggiornato"
    assert _MODULE.SERVER_ID in data["servers"]
    assert "[SPARK-INIT][ERROR]" in captured.err


# ---------------------------------------------------------------------------
# _bootstrap_github_files
# ---------------------------------------------------------------------------


def _make_engine_with_assets(base: Path) -> tuple[Path, Path]:
    """Return (engine_root, workspace_root) after creating minimal source assets."""
    engine_root = base / "engine"
    workspace_root = base / "workspace"
    workspace_root.mkdir()
    gh = engine_root / ".github"
    (gh / "agents").mkdir(parents=True)
    (gh / "instructions").mkdir(parents=True)
    (gh / "prompts").mkdir(parents=True)
    (gh / "agents" / "spark-assistant.agent.md").write_text("agent", encoding="utf-8")
    (gh / "agents" / "spark-engine-maintainer.agent.md").write_text(
        "maintainer",
        encoding="utf-8",
    )
    (gh / "instructions" / "spark-assistant-guide.instructions.md").write_text(
        "guide", encoding="utf-8"
    )
    (gh / "prompts" / "scf-foo.prompt.md").write_text("prompt1", encoding="utf-8")
    (gh / "prompts" / "scf-bar.prompt.md").write_text("prompt2", encoding="utf-8")
    return engine_root, workspace_root


def test_bootstrap_github_files_copies_missing_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    engine_root, workspace_root = _make_engine_with_assets(tmp_path)

    messages = _MODULE._bootstrap_github_files(engine_root, workspace_root)

    assert all(msg.startswith("[SPARK] .github/") for msg in messages)
    assert all("copiato" in m for m in messages)
    assert (workspace_root / ".github" / "agents" / "spark-assistant.agent.md").exists()
    assert (
        workspace_root / ".github" / "agents" / "spark-engine-maintainer.agent.md"
    ).exists()
    assert (
        workspace_root / ".github" / "instructions" / "spark-assistant-guide.instructions.md"
    ).exists()
    assert (workspace_root / ".github" / "prompts" / "scf-foo.prompt.md").exists()
    assert (workspace_root / ".github" / "prompts" / "scf-bar.prompt.md").exists()
    assert "[SPARK-INIT][INFO] copiato:" in capsys.readouterr().err


def test_bootstrap_github_files_silent_skip_when_identical(tmp_path: Path) -> None:
    engine_root, workspace_root = _make_engine_with_assets(tmp_path)
    # Pre-copy so content is identical.
    _MODULE._bootstrap_github_files(engine_root, workspace_root)

    messages = _MODULE._bootstrap_github_files(engine_root, workspace_root)

    assert all("preservato" in m for m in messages)


def test_bootstrap_github_files_preserves_user_modified_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    engine_root, workspace_root = _make_engine_with_assets(tmp_path)
    _MODULE._bootstrap_github_files(engine_root, workspace_root)
    # Modify one destination file.
    agent_dst = workspace_root / ".github" / "agents" / "spark-assistant.agent.md"
    agent_dst.write_text("user modified content", encoding="utf-8")

    messages = _MODULE._bootstrap_github_files(engine_root, workspace_root)

    agent_msg = next(m for m in messages if "spark-assistant.agent.md" in m)
    assert "preservato" in agent_msg
    assert agent_dst.read_text(encoding="utf-8") == "user modified content"
    assert "[SPARK-INIT][INFO] preservato" in capsys.readouterr().err


def test_bootstrap_github_files_warns_on_missing_source(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    engine_root = tmp_path / "engine"
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    # Engine .github has no files at all.
    (engine_root / ".github").mkdir(parents=True)

    messages = _MODULE._bootstrap_github_files(engine_root, workspace_root)

    assert any("sorgente non trovata" in m for m in messages)
    assert "[SPARK-INIT][WARNING]" in capsys.readouterr().err


def test_main_prints_ordered_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    workspace_file = project_root / f"{project_root.name}.code-workspace"

    monkeypatch.chdir(project_root)
    monkeypatch.setattr(_MODULE, "_workspace_candidates", lambda _project_root: [])
    monkeypatch.setattr(
        _MODULE,
        "_create_workspace_file",
        lambda _workspace_path, _project_root, _engine_script: "File salvato",
    )
    monkeypatch.setattr(
        _MODULE,
        "_write_vscode_mcp_json",
        lambda _project_root, _engine_script: (True, "creato"),
    )
    monkeypatch.setattr(
        _MODULE,
        "_bootstrap_github_files",
        lambda _engine_root, _workspace_root: [
            "[SPARK] .github/agents/spark-assistant.agent.md → copiato",
            "[SPARK] .github/agents/spark-engine-maintainer.agent.md → copiato",
            "[SPARK] .github/prompts/scf-install.prompt.md → preservato",
        ],
    )

    exit_code = _MODULE.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.splitlines() == [
        f"[SPARK] .code-workspace → creato: {workspace_file.name}",
        "[SPARK] .vscode/mcp.json → creato",
        "[SPARK] .github/agents/spark-assistant.agent.md → copiato",
        "[SPARK] .github/agents/spark-engine-maintainer.agent.md → copiato",
        "[SPARK] .github/prompts/scf-install.prompt.md → preservato",
        "",
        "Setup completato. Il server SPARK è configurato in due modi:",
        f"  - Workspace : apri {workspace_file.name} in VS Code",
        "  - Cartella  : apri direttamente la cartella, funziona lo stesso",
    ]