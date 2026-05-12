"""Tests per scf_universal.py v5.2 — auto-setup workspace deps.

Verifica il comportamento di:
- _check_engine_deps()
- _get_venv_python()
- _get_venv_pip()
- _setup_workspace_deps()
- _resolve_workspace() fallback ImportError
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Loader modulo scf_universal (non è un package, va caricato da file)
# ---------------------------------------------------------------------------

def _load_scf_universal():
    """Carica scripts/scf_universal.py come modulo usando importlib."""
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "scf_universal.py"
    spec = importlib.util.spec_from_file_location("scf_universal_deps_test", script_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Tests _check_engine_deps
# ---------------------------------------------------------------------------

def test_check_engine_deps_returns_true_when_mcp_stubbed() -> None:
    """_check_engine_deps() → True quando mcp è stubbato nel conftest."""
    # Il conftest inserisce un MagicMock per 'mcp' in sys.modules,
    # quindi find_spec('mcp') trova il modulo e ritorna non-None.
    mod = _load_scf_universal()
    assert mod._check_engine_deps() is True


def test_check_engine_deps_returns_false_when_mcp_absent() -> None:
    """_check_engine_deps() → False quando mcp assente da sys.modules e find_spec=None."""
    mod = _load_scf_universal()
    original = sys.modules.get("mcp")
    try:
        sys.modules.pop("mcp", None)
        with patch("importlib.util.find_spec", return_value=None):
            result = mod._check_engine_deps()
        assert result is False
    finally:
        if original is not None:
            sys.modules["mcp"] = original


# ---------------------------------------------------------------------------
# Tests _get_venv_python / _get_venv_pip
# ---------------------------------------------------------------------------

def test_get_venv_python_returns_windows_path(tmp_path: Path) -> None:
    """_get_venv_python() → Scripts/python.exe se esiste (Windows)."""
    mod = _load_scf_universal()
    scripts = tmp_path / "Scripts"
    scripts.mkdir()
    python_exe = scripts / "python.exe"
    python_exe.touch()

    result = mod._get_venv_python(tmp_path)
    assert result == python_exe


def test_get_venv_python_falls_back_to_unix_path(tmp_path: Path) -> None:
    """_get_venv_python() → bin/python se Scripts/python.exe assente."""
    mod = _load_scf_universal()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    python_bin = bin_dir / "python"
    python_bin.touch()

    result = mod._get_venv_python(tmp_path)
    assert result == python_bin


def test_get_venv_pip_returns_windows_path(tmp_path: Path) -> None:
    """_get_venv_pip() → Scripts/pip.exe se esiste (Windows)."""
    mod = _load_scf_universal()
    scripts = tmp_path / "Scripts"
    scripts.mkdir()
    pip_exe = scripts / "pip.exe"
    pip_exe.touch()

    result = mod._get_venv_pip(tmp_path)
    assert result == pip_exe


def test_get_venv_pip_falls_back_to_unix_path(tmp_path: Path) -> None:
    """_get_venv_pip() → bin/pip se Scripts/pip.exe assente."""
    mod = _load_scf_universal()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    pip_bin = bin_dir / "pip"
    pip_bin.touch()

    result = mod._get_venv_pip(tmp_path)
    assert result == pip_bin


# ---------------------------------------------------------------------------
# Tests _setup_workspace_deps
# ---------------------------------------------------------------------------

def test_setup_workspace_deps_returns_none_when_deps_available(tmp_path: Path) -> None:
    """_setup_workspace_deps() → None se mcp già disponibile (no venv creato)."""
    mod = _load_scf_universal()
    engine_root = tmp_path / "engine"
    engine_root.mkdir()

    with patch.object(mod, "_check_engine_deps", return_value=True):
        result = mod._setup_workspace_deps(tmp_path, engine_root)

    assert result is None
    assert not (tmp_path / ".venv").exists()
    assert not (tmp_path / ".scf-deps-ready").exists()


def test_setup_workspace_deps_idempotent_with_sentinel(tmp_path: Path) -> None:
    """Con sentinel + .venv + python presenti, non esegue pip install."""
    mod = _load_scf_universal()
    engine_root = tmp_path / "engine"
    engine_root.mkdir()

    # Prepara sentinel e venv fittizio
    (tmp_path / ".scf-deps-ready").touch()
    venv_dir = tmp_path / ".venv"
    scripts = venv_dir / "Scripts"
    scripts.mkdir(parents=True)
    python_exe = scripts / "python.exe"
    python_exe.touch()

    with patch.object(mod, "_check_engine_deps", return_value=False):
        with patch("subprocess.check_call") as mock_pip:
            result = mod._setup_workspace_deps(tmp_path, engine_root)

    # Nessuna chiamata pip — già configurato
    mock_pip.assert_not_called()
    assert result == python_exe


def test_setup_workspace_deps_creates_venv_and_sentinel(tmp_path: Path) -> None:
    """Se mcp mancante e no .venv, crea venv, installa deps, crea sentinel."""
    mod = _load_scf_universal()
    engine_root = tmp_path / "engine"
    engine_root.mkdir()
    req_file = engine_root / "requirements.txt"
    req_file.write_text("mcp\n", encoding="utf-8")

    def fake_venv_create(path: str, **kw: object) -> None:
        """Simula venv.create creando la struttura minima."""
        scripts = Path(path) / "Scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        (scripts / "python.exe").touch()
        (scripts / "pip.exe").touch()

    with patch.object(mod, "_check_engine_deps", return_value=False):
        with patch("venv.create", side_effect=fake_venv_create):
            with patch("subprocess.check_call") as mock_pip:
                result = mod._setup_workspace_deps(tmp_path, engine_root)

    assert (tmp_path / ".scf-deps-ready").exists(), "Sentinel mancante"
    assert result is not None
    assert result.name == "python.exe"
    # pip deve essere chiamato almeno una volta (requirements.txt + editable)
    assert mock_pip.call_count >= 1


def test_setup_workspace_deps_skips_requirements_if_missing(tmp_path: Path) -> None:
    """Se requirements.txt assente, salta quel pip call ma installa -e engine."""
    mod = _load_scf_universal()
    engine_root = tmp_path / "engine"
    engine_root.mkdir()
    # Nessun requirements.txt

    def fake_venv_create(path: str, **kw: object) -> None:
        scripts = Path(path) / "Scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        (scripts / "python.exe").touch()
        (scripts / "pip.exe").touch()

    with patch.object(mod, "_check_engine_deps", return_value=False):
        with patch("venv.create", side_effect=fake_venv_create):
            with patch("subprocess.check_call") as mock_pip:
                mod._setup_workspace_deps(tmp_path, engine_root)

    # Solo pip install -e engine (no -r requirements.txt)
    assert mock_pip.call_count == 1
    args = mock_pip.call_args[0][0]
    assert "-e" in args


# ---------------------------------------------------------------------------
# Test _resolve_workspace — fallback ImportError
# ---------------------------------------------------------------------------

def test_resolve_workspace_falls_back_to_cwd_on_import_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_resolve_workspace() usa cwd se WorkspaceLocator non è importabile."""
    mod = _load_scf_universal()
    engine_root = tmp_path / "engine"
    engine_root.mkdir()
    (engine_root / "spark-framework-engine.py").touch()

    monkeypatch.chdir(tmp_path)

    # Forza ImportError simulando assenza di WorkspaceLocator
    with patch.dict(sys.modules, {"spark.workspace.locator": None}):
        result = mod._resolve_workspace(engine_root)

    assert result == tmp_path.resolve()
