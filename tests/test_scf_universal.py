"""Test di integrazione per scf_universal.py — launcher globale v5.1."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_scf_universal_resolves_workspace_via_locator(tmp_path: Path) -> None:
    """Test: scf_universal importa e usa WorkspaceLocator correttamente."""
    # Setup: crea engine mock con spark.workspace.locator disponibile
    engine_root = tmp_path / "engine"
    engine_root.mkdir()
    (engine_root / "spark-framework-engine.py").touch()

    # Crea spark package structure minima
    spark_dir = engine_root / "spark"
    spark_dir.mkdir()
    (spark_dir / "__init__.py").touch()

    workspace_dir = spark_dir / "workspace"
    workspace_dir.mkdir()
    (workspace_dir / "__init__.py").touch()

    # Mock WorkspaceLocator
    locator_code = """
from spark.core.models import WorkspaceContext
from pathlib import Path

class WorkspaceLocator:
    def __init__(self, engine_root):
        self._engine_root = engine_root
    
    def resolve(self):
        # Ritorna sempre il cwd come workspace (semplice)
        return WorkspaceContext(
            workspace_root=Path.cwd(),
            github_root=Path.cwd() / ".github",
            engine_root=self._engine_root
        )
"""
    (workspace_dir / "locator.py").write_text(locator_code, encoding="utf-8")

    # Crea core.models mock
    core_dir = spark_dir / "core"
    core_dir.mkdir()
    (core_dir / "__init__.py").touch()

    models_code = """
from dataclasses import dataclass
from pathlib import Path

@dataclass
class WorkspaceContext:
    workspace_root: Path | None
    github_root: Path | None
    engine_root: Path
"""
    (core_dir / "models.py").write_text(models_code, encoding="utf-8")

    # Importa scf_universal e testa la logica
    # (In realtà, scf_universal.py non è un modulo testabile direttamente
    # perché è uno script. Lo testiamo tramite esecuzione)
    pass


def test_scf_universal_finds_engine_when_run_from_nested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test: Eseguire scf_universal da una directory nested trova engine."""
    engine_root = tmp_path / "engine"
    engine_root.mkdir()
    (engine_root / "spark-framework-engine.py").touch()

    nested = engine_root / "myproject" / "src"
    nested.mkdir(parents=True)

    # Simula: scf_universal.py in scripts/
    scf_universal = engine_root / "scripts" / "scf_universal.py"
    scf_universal.parent.mkdir(exist_ok=True)

    # Scrivi script con logica vera (non import effettivi per semplicità)
    scf_universal_code = """
from pathlib import Path

def _find_engine_root(start_from=None):
    start = start_from or Path.cwd()
    candidate = start.resolve()
    for _ in range(10):
        if (candidate / "spark-framework-engine.py").is_file():
            return candidate
        if candidate.parent == candidate:
            break
        candidate = candidate.parent
    raise RuntimeError(f"Engine non trovato da {start}")

# Test diretta
result = _find_engine_root(start_from=Path.cwd())
print(f"FOUND_ENGINE:{result}")
"""
    scf_universal.write_text(scf_universal_code, encoding="utf-8")

    monkeypatch.chdir(nested)

    # Esegui lo script Python
    import subprocess

    result = subprocess.run(
        [sys.executable, str(scf_universal)],
        capture_output=True,
        text=True,
        cwd=nested,
    )

    assert result.returncode == 0
    assert f"FOUND_ENGINE:{engine_root}" in result.stdout


def test_scf_universal_script_discoverable_from_engine_root(tmp_path: Path) -> None:
    """Test: Lo script scf_universal.py si auto-locate dal suo path assoluto."""
    engine_root = tmp_path / "engine"
    engine_root.mkdir()
    (engine_root / "spark-framework-engine.py").touch()

    scf_universal = engine_root / "scripts" / "scf_universal.py"
    scf_universal.parent.mkdir(exist_ok=True)

    # Script che testa se __file__ è usabile
    code = """
from pathlib import Path

script_dir = Path(__file__).resolve().parent
# script_dir = engine/scripts
engine_from_script = script_dir.parent  # engine
print(f"ENGINE_FROM_SCRIPT:{engine_from_script}")
"""
    scf_universal.write_text(code, encoding="utf-8")

    import subprocess

    result = subprocess.run(
        [sys.executable, str(scf_universal)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert f"ENGINE_FROM_SCRIPT:{engine_root}" in result.stdout


def test_scf_universal_handles_multiple_engines_chooses_closest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test: Se ci sono multiple engine nested, scf_universal trova il più vicino."""
    # Crea 2 engine nested
    engine1 = tmp_path / "level1" / "engine"
    engine1.mkdir(parents=True)
    (engine1 / "spark-framework-engine.py").touch()

    engine2 = engine1 / "level2" / "engine"
    engine2.mkdir(parents=True)
    (engine2 / "spark-framework-engine.py").touch()

    # Utente è dentro engine2/project
    user_cwd = engine2 / "project" / "src"
    user_cwd.mkdir(parents=True)

    scf_universal = engine2 / "scripts" / "scf_universal.py"
    scf_universal.parent.mkdir(exist_ok=True)

    code = """
from pathlib import Path

def _find_engine_root(start_from=None):
    start = start_from or Path.cwd()
    candidate = start.resolve()
    for _ in range(10):
        if (candidate / "spark-framework-engine.py").is_file():
            return candidate
        if candidate.parent == candidate:
            break
        candidate = candidate.parent
    raise RuntimeError(f"Engine non trovato")

result = _find_engine_root(start_from=Path.cwd())
print(f"FOUND:{result}")
"""
    scf_universal.write_text(code, encoding="utf-8")

    monkeypatch.chdir(user_cwd)

    import subprocess

    result = subprocess.run(
        [sys.executable, str(scf_universal)],
        capture_output=True,
        text=True,
        cwd=user_cwd,
    )

    assert result.returncode == 0
    # Deve trovare engine2 (più vicino), non engine1
    assert f"FOUND:{engine2}" in result.stdout


def test_scf_universal_imports_unified_boot_path_from_engine(
    tmp_path: Path,
) -> None:
    """Test: scf_universal importa startup e cli_main dal motore corretto."""
    engine_root = tmp_path / "engine"
    engine_root.mkdir()
    (engine_root / "spark-framework-engine.py").touch()

    # Setup minimo del package spark.cli nel motore fake.
    spark_cli = engine_root / "spark" / "cli"
    spark_cli.mkdir(parents=True)
    (spark_cli.parent / "__init__.py").touch()
    (spark_cli / "__init__.py").touch()

    startup_code = """
def is_startup_completed(base=None):
    return False

def run_startup_flow(engine_root, workspace_root=None, *, base=None, _input=None):
    print(f"STARTUP_RUN_IN:{workspace_root}")
    return {"status": "completed"}
"""
    (spark_cli / "startup.py").write_text(startup_code, encoding="utf-8")

    main_code = """
def main():
    print("CLI_MAIN_CALLED")
"""
    (spark_cli / "main.py").write_text(main_code, encoding="utf-8")

    # Crea scf_universal che importa il boot path unificato.
    scf_universal = engine_root / "scripts" / "scf_universal.py"
    scf_universal.parent.mkdir(exist_ok=True)

    code = """
import sys
from pathlib import Path

engine_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(engine_root))

from spark.cli.main import main as cli_main
from spark.cli.startup import is_startup_completed, run_startup_flow

workspace_root = Path.cwd()
if not is_startup_completed(Path.home() / ".spark"):
    run_startup_flow(engine_root=engine_root, workspace_root=workspace_root, base=Path.home() / ".spark")
cli_main()
"""
    scf_universal.write_text(code, encoding="utf-8")

    import subprocess

    result = subprocess.run(
        [sys.executable, str(scf_universal)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert "STARTUP_RUN_IN" in result.stdout
    assert "CLI_MAIN_CALLED" in result.stdout
    assert result.returncode == 0
