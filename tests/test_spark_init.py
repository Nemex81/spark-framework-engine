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
    registry_version: str = "1.2.0",
    manifest_version: str = "1.0.0",
) -> dict[str, str]:
    if files is None:
        files = {
            ".github/AGENTS.md": "agents-index\n",
            ".github/project-profile.md": "initialized: true\n",
            ".github/agents/spark-assistant.agent.md": "assistant\n",
            ".github/agents/spark-guide.agent.md": "guide\n",
            ".github/instructions/spark-assistant-guide.instructions.md": "assistant guide\n",
            ".github/prompts/scf-migrate-workspace.prompt.md": "migrate workspace\n",
            ".github/prompts/scf-update-policy.prompt.md": "update policy\n",
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


def test_ensure_engine_runtime_creates_venv_and_installs_mcp_when_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine_root = tmp_path / "engine"
    engine_root.mkdir()
    venv_python = _MODULE._engine_venv_python(engine_root)
    commands: list[tuple[list[str], str]] = []

    monkeypatch.setattr(_MODULE, "_resolve_bootstrap_python", lambda: ["python3"])
    monkeypatch.setattr(_MODULE, "_log", lambda _level, _message: None)

    def _fake_run_checked_command(args: list[str], description: str) -> None:
        commands.append((args, description))
        if args[:3] == ["python3", "-m", "venv"]:
            venv_python.parent.mkdir(parents=True, exist_ok=True)
            venv_python.write_text("", encoding="utf-8")

    monkeypatch.setattr(_MODULE, "_run_checked_command", _fake_run_checked_command)
    monkeypatch.setattr(_MODULE, "_venv_has_mcp", lambda _path: False)

    resolved_python = _MODULE._ensure_engine_runtime(engine_root)

    assert resolved_python == venv_python
    assert commands == [
        (["python3", "-m", "venv", str(engine_root / ".venv")], "Creazione virtualenv locale SPARK"),
        ([str(venv_python), "-m", "pip", "install", "--quiet", "--upgrade", "pip"], "Aggiornamento pip nel runtime locale SPARK"),
        ([str(venv_python), "-m", "pip", "install", "--quiet", "--upgrade", "mcp"], "Installazione dipendenza mcp nel runtime locale SPARK"),
    ]


def test_ensure_engine_runtime_reuses_ready_venv_without_reinstall(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine_root = tmp_path / "engine"
    venv_python = _MODULE._engine_venv_python(engine_root)
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text("", encoding="utf-8")

    monkeypatch.setattr(_MODULE, "_venv_has_mcp", lambda _path: True)
    monkeypatch.setattr(
        _MODULE,
        "_run_checked_command",
        lambda _args, _description: (_ for _ in ()).throw(AssertionError("unexpected install")),
    )

    resolved_python = _MODULE._ensure_engine_runtime(engine_root)

    assert resolved_python == venv_python


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
                "latest_version": "1.2.0",
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


def test_bootstrap_installer_fetch_json_accepts_utf8_bom(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "workspace"
    engine_root = tmp_path / "engine"
    project_root.mkdir()
    engine_root.mkdir()

    installer = _MODULE._BootstrapInstaller(project_root, engine_root)

    class _FakeResponse:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return self._payload

    def _fake_urlopen(request: object, timeout: int = 30) -> _FakeResponse:
        del request, timeout
        return _FakeResponse(b"\xef\xbb\xbf{\"version\": \"1.3.0\"}")

    monkeypatch.setattr(_MODULE.urllib.request, "urlopen", _fake_urlopen)

    payload = installer._fetch_json("https://example.invalid/package-manifest.json")

    assert payload == {"version": "1.3.0"}


def test_bootstrap_installer_fetch_raw_text_rejects_invalid_utf8(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "workspace"
    engine_root = tmp_path / "engine"
    project_root.mkdir()
    engine_root.mkdir()

    installer = _MODULE._BootstrapInstaller(project_root, engine_root)

    class _FakeResponse:
        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return b"\xff\xfe\x00\x00not-utf8"

    def _fake_urlopen(request: object, timeout: int = 30) -> _FakeResponse:
        del request, timeout
        return _FakeResponse()

    monkeypatch.setattr(_MODULE.urllib.request, "urlopen", _fake_urlopen)

    with pytest.raises(_MODULE._BootstrapError, match="Payload remoto non UTF-8"):
        installer._fetch_raw_text("https://example.invalid/bad.txt")


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
    pkg_store_dir = engine_root / "packages" / _MODULE.SPARK_BASE_ID / ".github"
    for file_path, content in files.items():
        rel_path = file_path.removeprefix(".github/")
        assert (pkg_store_dir / rel_path).read_text(encoding="utf-8") == content

    manifest = json.loads((engine_root / ".github" / ".scf-manifest.json").read_text(encoding="utf-8"))
    spark_base_entries = [
        entry for entry in manifest["entries"] if entry["package"] == _MODULE.SPARK_BASE_ID
    ]
    assert manifest["schema_version"] == "1.0"
    assert len(spark_base_entries) == len(files)
    assert {entry["file"] for entry in spark_base_entries} == {
        f"packages/{_MODULE.SPARK_BASE_ID}/.github/" + path.removeprefix(".github/") for path in files
    }
    assert "manifest remoto dichiara 1.0.0" in capsys.readouterr().err


def test_bootstrap_installer_falls_back_to_registry_version_when_manifest_version_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "workspace"
    engine_root = tmp_path / "engine"
    project_root.mkdir()
    engine_root.mkdir()
    _mock_bootstrap_remote(monkeypatch, registry_version="1.2.0", manifest_version="")

    installer = _MODULE._BootstrapInstaller(project_root, engine_root)

    action = installer.ensure_spark_base()

    assert action == "installato"
    manifest = json.loads((engine_root / ".github" / ".scf-manifest.json").read_text(encoding="utf-8"))
    assert {entry["package_version"] for entry in manifest["entries"]} == {"1.2.0"}


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
        engine_root,
        [
            {
                "file": f"packages/{_MODULE.SPARK_BASE_ID}/.github/AGENTS.md",
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


def test_bootstrap_installer_accepts_schema_2_0_runtime_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "workspace"
    engine_root = tmp_path / "engine"
    project_root.mkdir()
    engine_root.mkdir()
    _write_manifest(
        engine_root,
        [
            {
                "file": f"packages/{_MODULE.SPARK_BASE_ID}/.github/AGENTS.md",
                "package": _MODULE.SPARK_BASE_ID,
                "package_version": "1.0.0",
                "installed_at": "2026-04-16T00:00:00Z",
                "sha256": "abc",
            }
        ],
    )
    manifest_path = engine_root / ".github" / ".scf-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = "2.0"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def _unexpected_fetch(self: object, url: str) -> str:
        raise AssertionError(f"Network fetch should not happen for already-installed spark-base: {url}")

    monkeypatch.setattr(_MODULE._BootstrapInstaller, "_fetch_raw_text", _unexpected_fetch)

    installer = _MODULE._BootstrapInstaller(project_root, engine_root)

    assert installer.ensure_spark_base() == "già presente"


def test_bootstrap_installer_blocks_untracked_conflicts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "workspace"
    engine_root = tmp_path / "engine"
    project_root.mkdir()
    engine_root.mkdir()
    files = _mock_bootstrap_remote(monkeypatch)
    pkg_store_dir = engine_root / "packages" / _MODULE.SPARK_BASE_ID / ".github"
    conflicting_path = pkg_store_dir / "AGENTS.md"
    conflicting_path.parent.mkdir(parents=True, exist_ok=True)
    conflicting_path.write_text("user version\n", encoding="utf-8")

    installer = _MODULE._BootstrapInstaller(project_root, engine_root)

    with pytest.raises(_MODULE._BootstrapError, match="evitare overwrite"):
        installer.ensure_spark_base()

    manifest_path = engine_root / ".github" / ".scf-manifest.json"
    assert not manifest_path.exists()
    assert conflicting_path.read_text(encoding="utf-8") != files[".github/AGENTS.md"]


def test_bootstrap_installer_replace_mode_overwrites_untracked_conflicts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "workspace"
    engine_root = tmp_path / "engine"
    project_root.mkdir()
    engine_root.mkdir()
    files = _mock_bootstrap_remote(monkeypatch)
    pkg_store_dir = engine_root / "packages" / _MODULE.SPARK_BASE_ID / ".github"
    conflicting_path = pkg_store_dir / "AGENTS.md"
    conflicting_path.parent.mkdir(parents=True, exist_ok=True)
    conflicting_path.write_text("user version\n", encoding="utf-8")

    installer = _MODULE._BootstrapInstaller(project_root, engine_root)

    action = installer.ensure_spark_base(conflict_mode="replace")

    assert action == "installato"
    assert conflicting_path.read_text(encoding="utf-8") == files[".github/AGENTS.md"]


def test_bootstrap_installer_preserve_mode_tracks_existing_conflicts_as_local_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "workspace"
    engine_root = tmp_path / "engine"
    project_root.mkdir()
    engine_root.mkdir()
    _mock_bootstrap_remote(monkeypatch)
    pkg_store_dir = engine_root / "packages" / _MODULE.SPARK_BASE_ID / ".github"
    conflicting_path = pkg_store_dir / "AGENTS.md"
    conflicting_path.parent.mkdir(parents=True, exist_ok=True)
    conflicting_path.write_text("user version\n", encoding="utf-8")

    installer = _MODULE._BootstrapInstaller(project_root, engine_root)

    action = installer.ensure_spark_base(conflict_mode="preserve")

    assert action == "installato"
    assert conflicting_path.read_text(encoding="utf-8") == "user version\n"
    manifest = json.loads((engine_root / ".github" / ".scf-manifest.json").read_text(encoding="utf-8"))
    assert any(entry["file"].endswith("AGENTS.md") for entry in manifest["entries"])


def test_bootstrap_installer_integrate_mode_merges_existing_and_remote_text(
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
    conflicting_path.write_text("agents-index\nlocal-note\n", encoding="utf-8")

    installer = _MODULE._BootstrapInstaller(project_root, engine_root)

    action = installer.ensure_spark_base(conflict_mode="integrate")

    assert action == "installato"
    merged_text = conflicting_path.read_text(encoding="utf-8")
    assert "agents-index" in merged_text
    assert "local-note" in merged_text
    assert files[".github/AGENTS.md"].strip() in merged_text


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
    pkg_store_dir = engine_root / "packages" / _MODULE.SPARK_BASE_ID / ".github"
    existing_path = pkg_store_dir / "AGENTS.md"
    existing_path.parent.mkdir(parents=True, exist_ok=True)
    existing_path.write_bytes(files[".github/AGENTS.md"].encode("utf-8"))

    installer = _MODULE._BootstrapInstaller(project_root, engine_root)

    action = installer.ensure_spark_base()

    assert action == "installato"
    # Il log ora riporta il path completo del file adottato
    assert f"Adottato nel manifest senza riscrittura: {existing_path}" in capsys.readouterr().err
    manifest = json.loads((engine_root / ".github" / ".scf-manifest.json").read_text(encoding="utf-8"))
    assert any(entry["file"].endswith("AGENTS.md") for entry in manifest["entries"])


def test_main_prompts_for_conflict_mode_and_retries_bootstrap(
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
    monkeypatch.setattr(
        _MODULE,
        "_ensure_engine_runtime",
        lambda _engine_root: _MODULE._engine_venv_python(tmp_path / "engine"),
    )
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
    monkeypatch.setattr("builtins.input", lambda: "p")

    class _FakeBootstrapInstaller:
        calls: list[str] = []

        def __init__(self, project_root: Path, engine_root: Path) -> None:
            self.project_root = project_root
            self.engine_root = engine_root

        def ensure_spark_base(self, conflict_mode: str = "abort") -> str:
            self.calls.append(conflict_mode)
            if len(self.calls) == 1:
                raise _MODULE._BootstrapConflictError(
                    "conflict",
                    [_MODULE._BootstrapConflict(".github/AGENTS.md", "exists")],
                )
            return "installato"

    monkeypatch.setattr(_MODULE, "_BootstrapInstaller", _FakeBootstrapInstaller)
    monkeypatch.setattr(
        _MODULE,
        "_propagate_spark_base_to_workspace",
        lambda _engine_root, _workspace_root: {"written": [], "preserved": []},
    )
    monkeypatch.setattr(_MODULE, "_write_spark_start_file", lambda _workspace_root: None)

    exit_code = _MODULE.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert _FakeBootstrapInstaller.calls == ["abort", "preserve"]
    assert captured.out.splitlines() == [
        f"[SPARK] .code-workspace → creato: {workspace_file.name}",
        "[SPARK] .vscode/mcp.json → creato",
        "[SPARK] spark-base → installato",
        "[SPARK] SPARK-START.md → apri Copilot e segui le istruzioni",
    ]


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
    monkeypatch.setattr(
        _MODULE,
        "_propagate_spark_base_to_workspace",
        lambda _engine_root, _workspace_root: {"written": [], "preserved": []},
    )
    monkeypatch.setattr(_MODULE, "_write_spark_start_file", lambda _workspace_root: None)

    exit_code = _MODULE.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.splitlines() == [
        f"[SPARK] .code-workspace → creato: {workspace_file.name}",
        "[SPARK] .vscode/mcp.json → creato",
        "[SPARK] spark-base → installato",
        "[SPARK] SPARK-START.md → apri Copilot e segui le istruzioni",
    ]


# ---------------------------------------------------------------------------
# Tests: _propagate_spark_base_to_workspace
# ---------------------------------------------------------------------------


def test_propagate_writes_new_files(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine"
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    src_github = engine_root / "packages" / "spark-base" / ".github"
    src_github.mkdir(parents=True)
    (src_github / "AGENTS.md").write_text("agents\n", encoding="utf-8")
    (src_github / "project-profile.md").write_text("profile\n", encoding="utf-8")

    result = _MODULE._propagate_spark_base_to_workspace(engine_root, workspace_root)

    dst_github = workspace_root / ".github"
    assert (dst_github / "AGENTS.md").read_text(encoding="utf-8") == "agents\n"
    assert (dst_github / "project-profile.md").read_text(encoding="utf-8") == "profile\n"
    assert sorted(result["written"]) == ["AGENTS.md", "project-profile.md"]
    assert result["preserved"] == []


def test_propagate_skip_identical(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine"
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    src_github = engine_root / "packages" / "spark-base" / ".github"
    src_github.mkdir(parents=True)
    content = "same content\n"
    (src_github / "AGENTS.md").write_text(content, encoding="utf-8")
    dst_github = workspace_root / ".github"
    dst_github.mkdir(parents=True)
    dst_file = dst_github / "AGENTS.md"
    dst_file.write_text(content, encoding="utf-8")
    mtime_before = dst_file.stat().st_mtime

    result = _MODULE._propagate_spark_base_to_workspace(engine_root, workspace_root)

    assert result["written"] == []
    assert result["preserved"] == []
    assert dst_file.stat().st_mtime == mtime_before  # file not touched


def test_propagate_preserve_modified(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine"
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    src_github = engine_root / "packages" / "spark-base" / ".github"
    src_github.mkdir(parents=True)
    (src_github / "AGENTS.md").write_text("upstream content\n", encoding="utf-8")
    dst_github = workspace_root / ".github"
    dst_github.mkdir(parents=True)
    dst_file = dst_github / "AGENTS.md"
    original_content = "user modified content\n"
    dst_file.write_text(original_content, encoding="utf-8")

    result = _MODULE._propagate_spark_base_to_workspace(engine_root, workspace_root)

    assert result["written"] == []
    assert result["preserved"] == ["AGENTS.md"]
    # user content preserved
    assert dst_file.read_text(encoding="utf-8") == original_content


def test_propagate_missing_src_root(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine"
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    # packages/spark-base/.github does NOT exist

    result = _MODULE._propagate_spark_base_to_workspace(engine_root, workspace_root)

    assert result["written"] == []
    assert result["preserved"] == []
    # no .github created in workspace
    assert not (workspace_root / ".github").exists()


def test_propagate_creates_nested_dirs(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine"
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    src_github = engine_root / "packages" / "spark-base" / ".github"
    nested_dir = src_github / "agents"
    nested_dir.mkdir(parents=True)
    (nested_dir / "spark-assistant.agent.md").write_text("assistant\n", encoding="utf-8")

    result = _MODULE._propagate_spark_base_to_workspace(engine_root, workspace_root)

    dst_nested = workspace_root / ".github" / "agents"
    assert dst_nested.is_dir()
    assert (dst_nested / "spark-assistant.agent.md").read_text(encoding="utf-8") == "assistant\n"
    assert result["written"] == ["agents/spark-assistant.agent.md"]
    assert result["preserved"] == []


# ---------------------------------------------------------------------------
# Tests: _write_spark_start_file
# ---------------------------------------------------------------------------


def test_write_spark_start_creates_file(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    _MODULE._write_spark_start_file(workspace_root)

    dest = workspace_root / "SPARK-START.md"
    assert dest.exists()
    content = dest.read_text(encoding="utf-8")
    assert "spark-assistant" in content
    assert "inizializza il workspace" in content


def test_write_spark_start_idempotent(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    dest = workspace_root / "SPARK-START.md"
    custom_content = "# Custom content — do not overwrite\n"
    dest.write_text(custom_content, encoding="utf-8")

    _MODULE._write_spark_start_file(workspace_root)

    assert dest.read_text(encoding="utf-8") == custom_content
