"""tests.test_cli_package_manager — Test unitari per spark.cli.package_manager.

Coprono: comportamento UX del menu (clear screen, pausa interattiva).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from spark.cli.package_manager import PackageManager


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


def _make_mgr(tmp_path: Path) -> PackageManager:
    """Crea un PackageManager con directories fittizie."""
    github_root = tmp_path / ".github"
    github_root.mkdir()
    engine_root = tmp_path / "engine"
    engine_root.mkdir()
    return PackageManager(github_root, engine_root)


# ---------------------------------------------------------------------------
# Test comportamento UX run() — FIX-2
# ---------------------------------------------------------------------------


class TestRunUX:
    """Verifica clear screen e pausa interattiva in PackageManager.run()."""

    def test_run_chiama_pausa_dopo_operazione(self, tmp_path: Path) -> None:
        """run() chiama input() per la pausa dopo ogni operazione (elif 1-4)."""
        mgr = _make_mgr(tmp_path)
        # Sequenza: "1" (scelta list), "" (pausa), "0" (esci)
        mock_input = MagicMock(side_effect=["1", "", "0"])
        with (
            patch("builtins.input", mock_input),
            patch.object(mgr, "_list_installed"),
            patch("os.system"),
        ):
            mgr.run()
        # input() deve essere chiamato 3 volte: menu, pausa, menu-exit
        assert mock_input.call_count == 3

    def test_run_no_pausa_per_scelta_invalida(self, tmp_path: Path) -> None:
        """run() non inserisce pausa per scelta non valida."""
        mgr = _make_mgr(tmp_path)
        # Sequenza: "9" (invalida), "0" (esci)
        mock_input = MagicMock(side_effect=["9", "0"])
        with (
            patch("builtins.input", mock_input),
            patch("os.system"),
        ):
            mgr.run()
        # Nessuna pausa: solo 2 input() calls (menu + exit)
        assert mock_input.call_count == 2

    def test_run_esegue_clear_prima_del_menu(self, tmp_path: Path) -> None:
        """run() chiama os.system per pulire lo schermo prima di ogni iterazione."""
        mgr = _make_mgr(tmp_path)
        with (
            patch("builtins.input", side_effect=["0"]),
            patch("os.system") as mock_sys,
        ):
            mgr.run()
        mock_sys.assert_called_once()
