"""tests.test_cli_main — Test unitari per spark.cli.main.

Coprono: routing comandi, KeyboardInterrupt, EOFError e diagnostica.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from spark.cli.main import _resolve_github_root, _run_main, main


# ---------------------------------------------------------------------------
# Test _resolve_github_root
# ---------------------------------------------------------------------------


class TestResolveGithubRoot:
    """Test per main._resolve_github_root."""

    def test_returns_cwd_github_on_locator_failure(self, tmp_path: Path) -> None:
        """Cade sul fallback cwd/.github quando WorkspaceLocator lancia eccezione."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()

        with patch("spark.workspace.WorkspaceLocator", side_effect=Exception("no locator")):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                result = _resolve_github_root(engine_root)

        assert result == tmp_path / ".github"

    def test_returns_context_github_root_on_success(self, tmp_path: Path) -> None:
        """Ritorna context.github_root quando WorkspaceLocator funziona."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        expected = tmp_path / "custom" / ".github"

        mock_context = MagicMock()
        mock_context.github_root = expected
        mock_locator = MagicMock()
        mock_locator.resolve.return_value = mock_context

        with patch("spark.workspace.WorkspaceLocator", return_value=mock_locator):
            result = _resolve_github_root(engine_root)

        assert result == expected


# ---------------------------------------------------------------------------
# Test main() — KeyboardInterrupt / EOFError
# ---------------------------------------------------------------------------


class TestMainExitHandling:
    """Test per gestione uscita pulita di main()."""

    def test_keyboard_interrupt_exits_cleanly(self) -> None:
        """KeyboardInterrupt non deve propagarsi fuori da main()."""
        with patch("spark.cli.main._run_main", side_effect=KeyboardInterrupt):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 0

    def test_eoferror_exits_cleanly(self) -> None:
        """EOFError non deve propagarsi fuori da main()."""
        with patch("spark.cli.main._run_main", side_effect=EOFError):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Test _run_main — routing comandi
# ---------------------------------------------------------------------------


class TestRunMainRouting:
    """Test per il routing dei comandi in _run_main."""

    def _make_locator(self, github_root: Path) -> MagicMock:
        mock_context = MagicMock()
        mock_context.github_root = github_root
        mock_locator = MagicMock()
        mock_locator.resolve.return_value = mock_context
        return mock_locator

    def test_choice_0_exits(self, tmp_path: Path) -> None:
        """Scegliere '0' esce dal loop senza chiamare altri comandi."""
        with patch("spark.workspace.WorkspaceLocator", return_value=self._make_locator(tmp_path)):
            with patch("builtins.input", side_effect=["0"]):
                _run_main()  # deve terminare senza eccezioni

    def test_choice_1_calls_init(self, tmp_path: Path) -> None:
        """Scegliere '1' chiama _cmd_init."""
        with patch("spark.workspace.WorkspaceLocator", return_value=self._make_locator(tmp_path)):
            with patch("spark.cli.main._cmd_init") as mock_init:
                with patch("builtins.input", side_effect=["1", "0"]):
                    _run_main()
            mock_init.assert_called_once()

    def test_choice_2_calls_packages(self, tmp_path: Path) -> None:
        """Scegliere '2' chiama _cmd_packages."""
        with patch("spark.workspace.WorkspaceLocator", return_value=self._make_locator(tmp_path)):
            with patch("spark.cli.main._cmd_packages") as mock_pkg:
                with patch("builtins.input", side_effect=["2", "0"]):
                    _run_main()
            mock_pkg.assert_called_once()

    def test_choice_3_calls_registry(self, tmp_path: Path) -> None:
        """Scegliere '3' chiama _cmd_registry."""
        with patch("spark.workspace.WorkspaceLocator", return_value=self._make_locator(tmp_path)):
            with patch("spark.cli.main._cmd_registry") as mock_reg:
                with patch("builtins.input", side_effect=["3", "0"]):
                    _run_main()
            mock_reg.assert_called_once()

    def test_choice_5_calls_diagnostics(self, tmp_path: Path) -> None:
        """Scegliere '5' chiama _cmd_diagnostics."""
        with patch("spark.workspace.WorkspaceLocator", return_value=self._make_locator(tmp_path)):
            with patch("spark.cli.main._cmd_diagnostics") as mock_diag:
                with patch("builtins.input", side_effect=["5", "0"]):
                    _run_main()
            mock_diag.assert_called_once()

    def test_invalid_choice_does_not_crash(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Scelta non valida stampa messaggio senza crash e torna al menu."""
        with patch("spark.workspace.WorkspaceLocator", return_value=self._make_locator(tmp_path)):
            with patch("builtins.input", side_effect=["99", "0"]):
                _run_main()
        out, _ = capsys.readouterr()
        assert "non valida" in out.lower() or "0" in out

    def test_keyboard_interrupt_in_input_exits(self, tmp_path: Path) -> None:
        """KeyboardInterrupt durante input() chiude il loop con sys.exit(0)."""
        with patch("spark.workspace.WorkspaceLocator", return_value=self._make_locator(tmp_path)):
            with patch("builtins.input", side_effect=KeyboardInterrupt):
                with pytest.raises(SystemExit) as exc_info:
                    _run_main()
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Test spark.cli dispatch (da __init__.py)
# ---------------------------------------------------------------------------


class TestCliDispatch:
    """Test per il dispatch di comandi in spark.cli.main()."""

    def test_dispatch_cli_calls_cli_main(self) -> None:
        """Comando 'cli' chiama cli_main."""
        import spark.cli as cli_module

        with patch("sys.argv", ["scf", "cli"]):
            with patch.object(cli_module, "cli_main") as mock_cli:
                cli_module.main()
            mock_cli.assert_called_once()

    def test_dispatch_unknown_command_exits_1(self) -> None:
        """Comando sconosciuto termina con sys.exit(1)."""
        import spark.cli as cli_module

        with patch("sys.argv", ["scf", "unknown-command"]):
            with pytest.raises(SystemExit) as exc_info:
                cli_module.main()
        assert exc_info.value.code == 1
