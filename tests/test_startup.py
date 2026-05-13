"""Test diretti per spark.cli.startup."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from spark.cli import startup


def test_is_startup_completed_con_sentinel_presente(tmp_path: Path) -> None:
    """Verifica che il sentinel presente faccia ritornare True.

    Args:
        tmp_path: Directory temporanea isolata del test.
    """
    base = tmp_path / ".spark"
    base.mkdir(parents=True, exist_ok=True)
    (base / startup.SENTINEL_FILE).touch()

    assert startup.is_startup_completed(base) is True


def test_is_startup_completed_con_sentinel_assente(tmp_path: Path) -> None:
    """Verifica che l'assenza del sentinel faccia ritornare False.

    Args:
        tmp_path: Directory temporanea isolata del test.
    """
    base = tmp_path / ".spark"
    base.mkdir(parents=True, exist_ok=True)

    assert startup.is_startup_completed(base) is False


def test_is_startup_completed_propaga_errore_da_ensure_startup_base() -> None:
    """Verifica che gli errori di bootstrap del path vengano propagati."""
    with patch.object(startup, "_ensure_startup_base", side_effect=OSError("boom")):
        with pytest.raises(OSError, match="boom"):
            startup.is_startup_completed()


def test_run_startup_flow_con_sentinel_presente_restituisce_already_initialized(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Verifica l'uscita immediata quando il primo avvio è già completato.

    Args:
        tmp_path: Directory temporanea isolata del test.
        capfd: Fixture pytest per catturare stdout e stderr.
    """
    engine_root = tmp_path / "engine"
    workspace_root = tmp_path / "workspace"

    def _unexpected_input(_prompt: str) -> str:
        raise AssertionError("input() non deve essere invocato")

    with patch.object(startup, "is_startup_completed", return_value=True):
        result = startup.run_startup_flow(
            engine_root=engine_root,
            workspace_root=workspace_root,
            base=tmp_path / ".spark",
            _input=_unexpected_input,
        )

    captured = capfd.readouterr()
    assert result == {"status": "already_initialized"}
    assert captured.out == ""
    assert captured.err == ""


def test_run_startup_flow_con_input_zero_restituisce_deferred_e_non_scrive_sentinel(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Verifica il percorso deferred quando l'utente rimanda il setup.

    Args:
        tmp_path: Directory temporanea isolata del test.
        capfd: Fixture pytest per catturare stdout e stderr.
    """
    base = tmp_path / ".spark"
    result = startup.run_startup_flow(
        engine_root=tmp_path / "engine",
        workspace_root=tmp_path / "workspace",
        base=base,
        _input=lambda _prompt: "0",
    )

    captured = capfd.readouterr()
    assert result == {"status": "deferred"}
    assert (base / startup.SENTINEL_FILE).exists() is False
    assert captured.err == ""


def test_run_startup_flow_con_input_uno_restituisce_completed_e_scrive_sentinel(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Verifica il percorso completed quando l'utente conferma il setup.

    Args:
        tmp_path: Directory temporanea isolata del test.
        capfd: Fixture pytest per catturare stdout e stderr.
    """
    base = tmp_path / ".spark"
    result = startup.run_startup_flow(
        engine_root=tmp_path / "engine",
        workspace_root=tmp_path / "workspace",
        base=base,
        _input=lambda _prompt: "1",
    )

    captured = capfd.readouterr()
    assert result == {"status": "completed"}
    assert (base / startup.SENTINEL_FILE).exists() is True
    assert captured.err == ""


def test_run_startup_flow_senza_workspace_root_usa_path_cwd(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Verifica il fallback a Path.cwd() quando workspace_root è omesso.

    Args:
        tmp_path: Directory temporanea isolata del test.
        capfd: Fixture pytest per catturare stdout e stderr.
    """
    base = tmp_path / ".spark"
    fake_workspace = tmp_path / "workspace-cwd"
    fake_workspace.mkdir(parents=True, exist_ok=True)

    with patch.object(startup.Path, "cwd", return_value=fake_workspace):
        result = startup.run_startup_flow(
            engine_root=tmp_path / "engine",
            base=base,
            _input=lambda _prompt: "0",
        )

    captured = capfd.readouterr()
    assert result == {"status": "deferred"}
    assert f"Workspace corrente: {fake_workspace}" in captured.out
    assert captured.err == ""


def test_run_startup_flow_propaga_errore_da_mark_startup_completed(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Verifica che un errore in scrittura del sentinel venga propagato.

    Args:
        tmp_path: Directory temporanea isolata del test.
        capfd: Fixture pytest per catturare stdout e stderr.
    """
    with (
        patch.object(startup, "is_startup_completed", return_value=False),
        patch.object(startup, "_mark_startup_completed", side_effect=OSError("boom")),
        pytest.raises(OSError, match="boom"),
    ):
        startup.run_startup_flow(
            engine_root=tmp_path / "engine",
            workspace_root=tmp_path / "workspace",
            base=tmp_path / ".spark",
            _input=lambda _prompt: "1",
        )

    captured = capfd.readouterr()
    assert "SPARK Framework - Avvio iniziale" in captured.out
    assert captured.err == ""