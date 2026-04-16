from __future__ import annotations

import importlib.util
import json
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


def _mock_bootstrap_remote(
    monkeypatch: pytest.MonkeyPatch,
    files: dict[str, str] | None = None,
    registry_version: str = "1.1.0",
    manifest_version: str = "1.0.0",
) -> dict[str, str]:
    if files is None:
        files = {
            ".github/AGENTS.md": "agents-index\n",
            ".github/project-profile.md": "initialized: true\n",
            ".github/agents/spark-guide.agent.md": "guide\n",
        }

    registry_payload = {
        "packages": [
            {
                "id": _MODULE.SPARK_BASE_ID,
                "repo_url": "https://github.com/Nemex81/spark-base",
                "latest_version": registry_version,
            }
        ]
    }
    package_manifest_payload = {
        "version": manifest_version,
        "files": list(files.keys()),
    }
    raw_prefix = "https://raw.githubusercontent.com/Nemex81/spark-base/main/"

    def _fake_fetch(self: object, url: str) -> str:
        if url == _MODULE.REGISTRY_URL:
            return json.dumps(registry_payload)
        if url == f"{raw_prefix}package-manifest.json":
            return json.dumps(package_manifest_payload)
        if url.startswith(raw_prefix):
            file_path = url.removeprefix(raw_prefix)
            return files[file_path]
        raise AssertionError(f"Unexpected URL requested during test: {url}")

    monkeypatch.setattr(_MODULE._BootstrapInstaller, "_fetch_raw_text", _fake_fetch)
    return files


def _write_manifest(base: Path, entries: list[dict[str, str]]) -> Path:
    manifest_path = base / ".github" / ".scf-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps({"schema_version": "1.0", "entries": entries}, indent=2),
        encoding="utf-8",
    )
    return manifest_path


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
    assert "chiave 'mcp'" in message.lower()
    assert "oggetto json" in message.lower()


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


def test_bootstrap_installer_uses_cache_when_registry_fetch_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = tmp_path / "workspace"
    engine_root = tmp_path / "engine"
    project_root.mkdir()
    cache_path = engine_root / ".github" / ".scf-registry-cache.json"
    cache_path.parent.mkdir(parents=True)
    cache_payload = {
        "packages": [
            {
                "id": _MODULE.SPARK_BASE_ID,
                "repo_url": "https://github.com/Nemex81/spark-base",
                "latest_version": "1.1.0",
            }
        ]
    }
    cache_path.write_text(json.dumps(cache_payload), encoding="utf-8")

    installer = _MODULE._BootstrapInstaller(project_root, engine_root)

    def _fail_fetch_json(self: object, url: str) -> dict[str, object]:
        raise _MODULE._BootstrapError(f"network down for {url}")

    monkeypatch.setattr(_MODULE._BootstrapInstaller, "_fetch_json", _fail_fetch_json)

    payload = installer._fetch_registry()

    assert payload == cache_payload
    assert "Fetch registry fallita" in capsys.readouterr().err


def test_bootstrap_installer_installs_spark_base_and_updates_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = tmp_path / "workspace"
    engine_root = tmp_path / "engine"
    project_root.mkdir()
    engine_root.mkdir()
    files = _mock_bootstrap_remote(monkeypatch)

    installer = _MODULE._BootstrapInstaller(project_root, engine_root)

    action = installer.ensure_spark_base()

    assert action == "installato"
    for file_path, content in files.items():
        assert (project_root / file_path).read_text(encoding="utf-8") == content

    manifest = json.loads((project_root / ".github" / ".scf-manifest.json").read_text(encoding="utf-8"))
    spark_base_entries = [
        entry for entry in manifest["entries"] if entry["package"] == _MODULE.SPARK_BASE_ID
    ]
    assert manifest["schema_version"] == "1.0"
    assert len(spark_base_entries) == len(files)
    assert {entry["file"] for entry in spark_base_entries} == {
        path.removeprefix(".github/") for path in files
    }
    assert "manifest remoto dichiara 1.0.0" in capsys.readouterr().err


def test_bootstrap_installer_returns_already_present_when_manifest_tracks_spark_base(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = tmp_path / "workspace"
    engine_root = tmp_path / "engine"
    project_root.mkdir()
    engine_root.mkdir()
    _write_manifest(
        project_root,
        [
            {
                "file": "AGENTS.md",
                "package": _MODULE.SPARK_BASE_ID,
                "package_version": "1.0.0",
                "installed_at": "2026-04-16T00:00:00Z",
                "sha256": "abc",
            }
        ],
    )

    def _unexpected_fetch(self: object, url: str) -> str:
        raise AssertionError(f"Network fetch should not happen for already-installed spark-base: {url}")

    monkeypatch.setattr(_MODULE._BootstrapInstaller, "_fetch_raw_text", _unexpected_fetch)

    installer = _MODULE._BootstrapInstaller(project_root, engine_root)

    action = installer.ensure_spark_base()

    assert action == "già presente"
    assert "gia tracciato nel manifest" in capsys.readouterr().err


def test_bootstrap_installer_blocks_untracked_conflicts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "workspace"
    engine_root = tmp_path / "engine"
    project_root.mkdir()
    engine_root.mkdir()
    files = _mock_bootstrap_remote(monkeypatch)
    conflicting_path = project_root / ".github" / "AGENTS.md"
    conflicting_path.parent.mkdir(parents=True)
    conflicting_path.write_text("user version\n", encoding="utf-8")

    installer = _MODULE._BootstrapInstaller(project_root, engine_root)

    with pytest.raises(_MODULE._BootstrapError, match="evitare overwrite"):
        installer.ensure_spark_base()

    manifest_path = project_root / ".github" / ".scf-manifest.json"
    assert not manifest_path.exists()
    assert conflicting_path.read_text(encoding="utf-8") != files[".github/AGENTS.md"]


def test_bootstrap_installer_adopts_identical_untracked_files_without_rewriting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = tmp_path / "workspace"
    engine_root = tmp_path / "engine"
    project_root.mkdir()
    engine_root.mkdir()
    files = _mock_bootstrap_remote(monkeypatch)
    existing_path = project_root / ".github" / "AGENTS.md"
    existing_path.parent.mkdir(parents=True)
    existing_path.write_bytes(files[".github/AGENTS.md"].encode("utf-8"))

    installer = _MODULE._BootstrapInstaller(project_root, engine_root)

    action = installer.ensure_spark_base()

    assert action == "installato"
    assert "Adottato nel manifest senza riscrittura: .github/AGENTS.md" in capsys.readouterr().err
    manifest = json.loads((project_root / ".github" / ".scf-manifest.json").read_text(encoding="utf-8"))
    assert any(entry["file"] == "AGENTS.md" for entry in manifest["entries"])


def test_main_prints_ordered_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    workspace_file = project_root / f"{project_root.name}.code-workspace"

    monkeypatch.chdir(project_root)
    monkeypatch.setattr(_MODULE, "_configure_stdio", lambda: None)
    monkeypatch.setattr(_MODULE, "_log", lambda _level, _message: None)
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

    class _FakeBootstrapInstaller:
        def __init__(self, project_root: Path, engine_root: Path) -> None:
            self.project_root = project_root
            self.engine_root = engine_root

        def ensure_spark_base(self) -> str:
            return "installato"

    monkeypatch.setattr(_MODULE, "_BootstrapInstaller", _FakeBootstrapInstaller)

    exit_code = _MODULE.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.splitlines() == [
        f"[SPARK] .code-workspace → creato: {workspace_file.name}",
        "[SPARK] .vscode/mcp.json → creato",
        "[SPARK] spark-base → installato",
    ]