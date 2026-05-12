"""Tests per spark.boot.wizard — idempotenza, esito passi, quit anticipato."""
from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helper: ricarica il modulo per ogni test (evita stato condiviso tra test)
# ---------------------------------------------------------------------------

def _load_wizard():
    """Importa (o ricarica) spark.boot.wizard per garantire isolamento."""
    import spark.boot.wizard as mod  # noqa: PLC0415

    importlib.reload(mod)
    return mod


# ---------------------------------------------------------------------------
# 1. Idempotenza
# ---------------------------------------------------------------------------


def test_wizard_skips_when_sentinel_exists(tmp_path: Path) -> None:
    """Se .scf-init-done esiste in cwd, run_wizard ritorna subito already_initialized."""
    (tmp_path / ".scf-init-done").touch()
    mod = _load_wizard()
    result = mod.run_wizard(cwd=tmp_path)
    assert result == {"status": "already_initialized"}


def test_wizard_creates_sentinel_on_completion(tmp_path: Path) -> None:
    """Dopo l'esecuzione completa il sentinel .scf-init-done deve esistere."""
    mod = _load_wizard()
    inputs = iter(["0", "0", "0"])  # salta tutti i passi
    with patch.object(mod, "os") as mock_os:
        mock_os.system = MagicMock()
        mod.run_wizard(cwd=tmp_path, _input=lambda _: next(inputs))
    assert (tmp_path / ".scf-init-done").exists()


def test_wizard_does_not_overwrite_existing_sentinel(tmp_path: Path) -> None:
    """La presenza del sentinel impedisce una doppia esecuzione."""
    sentinel = tmp_path / ".scf-init-done"
    sentinel.touch()
    mod = _load_wizard()
    # Chiamata 1 — già inizializzato
    result_1 = mod.run_wizard(cwd=tmp_path)
    # Chiamata 2 — ancora già inizializzato
    result_2 = mod.run_wizard(cwd=tmp_path)
    assert result_1 == {"status": "already_initialized"}
    assert result_2 == {"status": "already_initialized"}
    assert sentinel.exists()


# ---------------------------------------------------------------------------
# 2. Esecuzione passi
# ---------------------------------------------------------------------------


def test_wizard_executes_step_on_choice_1(tmp_path: Path) -> None:
    """Input '1' chiama os.system con il comando del passo."""
    mod = _load_wizard()
    inputs = iter(["1", "0", "0"])
    captured: list[str] = []

    with patch.object(mod, "os") as mock_os:
        mock_os.system = lambda cmd: captured.append(cmd)  # type: ignore[assignment]
        result = mod.run_wizard(cwd=tmp_path, _input=lambda _: next(inputs))

    assert result["step_1"] == "executed"
    assert result["step_2"] == "skipped"
    assert result["step_3"] == "skipped"
    assert len(captured) == 1


def test_wizard_skips_step_on_choice_0(tmp_path: Path) -> None:
    """Input '0' non chiama os.system e marca il passo come skipped."""
    mod = _load_wizard()
    inputs = iter(["0", "0", "0"])

    with patch.object(mod, "os") as mock_os:
        mock_os.system = MagicMock()
        result = mod.run_wizard(cwd=tmp_path, _input=lambda _: next(inputs))

    mock_os.system.assert_not_called()
    assert all(v == "skipped" for v in result.values())


def test_wizard_executes_all_steps(tmp_path: Path) -> None:
    """Input '1' per tutti i passi chiama os.system tre volte."""
    mod = _load_wizard()
    inputs = iter(["1", "1", "1"])
    captured: list[str] = []

    with patch.object(mod, "os") as mock_os:
        mock_os.system = lambda cmd: captured.append(cmd)  # type: ignore[assignment]
        result = mod.run_wizard(cwd=tmp_path, _input=lambda _: next(inputs))

    assert all(v == "executed" for v in result.values())
    assert len(captured) == 3


# ---------------------------------------------------------------------------
# 3. Uscita anticipata
# ---------------------------------------------------------------------------


def test_wizard_quits_early_on_choice_q_at_step_1(tmp_path: Path) -> None:
    """Input 'q' al primo passo marca step_1=aborted e step_2,3=skipped."""
    mod = _load_wizard()
    inputs = iter(["q"])

    with patch.object(mod, "os") as mock_os:
        mock_os.system = MagicMock()
        result = mod.run_wizard(cwd=tmp_path, _input=lambda _: next(inputs))

    assert result["step_1"] == "aborted"
    assert result["step_2"] == "skipped"
    assert result["step_3"] == "skipped"
    mock_os.system.assert_not_called()
    # Il sentinel viene comunque creato
    assert (tmp_path / ".scf-init-done").exists()


def test_wizard_quits_early_on_choice_q_at_step_2(tmp_path: Path) -> None:
    """Input 'q' al secondo passo marca step_2=aborted, step_3=skipped."""
    mod = _load_wizard()
    inputs = iter(["0", "q"])

    with patch.object(mod, "os") as mock_os:
        mock_os.system = MagicMock()
        result = mod.run_wizard(cwd=tmp_path, _input=lambda _: next(inputs))

    assert result["step_1"] == "skipped"
    assert result["step_2"] == "aborted"
    assert result["step_3"] == "skipped"


# ---------------------------------------------------------------------------
# 4. Input non riconosciuto
# ---------------------------------------------------------------------------


def test_wizard_treats_unknown_input_as_skip(tmp_path: Path) -> None:
    """Un input non valido (es. 'x') marca il passo come skipped."""
    mod = _load_wizard()
    inputs = iter(["x", "0", "0"])

    with patch.object(mod, "os") as mock_os:
        mock_os.system = MagicMock()
        result = mod.run_wizard(cwd=tmp_path, _input=lambda _: next(inputs))

    assert result["step_1"] == "skipped"
    mock_os.system.assert_not_called()
