"""tests.test_cli_main — Test unitari per spark.cli.main.

Coprono: routing comandi, KeyboardInterrupt, EOFError e diagnostica.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from spark.cli.main import _load_workspace_config, _resolve_github_root, _run_main, main


# ---------------------------------------------------------------------------
# Test _resolve_github_root
# ---------------------------------------------------------------------------


class TestResolveGithubRoot:
    """Test per main._resolve_github_root."""

    def test_returns_cwd_github_on_locator_failure(self, tmp_path: Path) -> None:
        """Cade sul fallback cwd/.github quando WorkspaceLocator lancia eccezione."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()

        with patch("spark.cli.main._load_workspace_config", return_value=None):
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
            with patch("spark.cli.main._load_workspace_config", return_value=None):
                result = _resolve_github_root(engine_root)

        assert result == expected

    def test_m1_config_json_presente_e_valido(self, tmp_path: Path) -> None:
        """M1: config.json valido — usa il path salvato senza WorkspaceLocator.

        Args:
            tmp_path: Directory temporanea isolata del test.
        """
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        github_dir = tmp_path / "workspace" / ".github"
        github_dir.mkdir(parents=True)

        with (
            patch("spark.cli.main._load_workspace_config", return_value=github_dir),
            patch("spark.workspace.WorkspaceLocator") as mock_locator_cls,
        ):
            result = _resolve_github_root(engine_root)

        assert result == github_dir
        mock_locator_cls.assert_not_called()

    def test_m2_config_json_assente_usa_workspace_locator(self, tmp_path: Path) -> None:
        """M2: config.json assente — fallback a WorkspaceLocator.

        Args:
            tmp_path: Directory temporanea isolata del test.
        """
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        expected = tmp_path / "other" / ".github"

        mock_context = MagicMock()
        mock_context.github_root = expected
        mock_locator = MagicMock()
        mock_locator.resolve.return_value = mock_context

        with (
            patch("spark.cli.main._load_workspace_config", return_value=None),
            patch("spark.workspace.WorkspaceLocator", return_value=mock_locator),
        ):
            result = _resolve_github_root(engine_root)

        assert result == expected

    def test_m3_config_json_path_non_valido_usa_workspace_locator(self, tmp_path: Path) -> None:
        """M3: config.json con path non esistente — fallback a WorkspaceLocator.

        Args:
            tmp_path: Directory temporanea isolata del test.
        """
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        expected = tmp_path / "ws" / ".github"

        mock_context = MagicMock()
        mock_context.github_root = expected
        mock_locator = MagicMock()
        mock_locator.resolve.return_value = mock_context

        # _load_workspace_config ritorna None quando il path non è valido
        with (
            patch("spark.cli.main._load_workspace_config", return_value=None),
            patch("spark.workspace.WorkspaceLocator", return_value=mock_locator),
        ):
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

    def test_dispatch_init_runs_startup_flow_then_cli_main(
        self,
        tmp_path: Path,
    ) -> None:
        """Comando init usa il boot path unificato prima di aprire il menu."""
        import spark.cli as cli_module

        fake_home = tmp_path / "fakehome"
        fake_home.mkdir(exist_ok=True)
        fake_workspace = tmp_path / "workspace"
        fake_workspace.mkdir(exist_ok=True)
        events: list[str] = []

        with (
            patch("sys.argv", ["scf", "init"]),
            patch.object(cli_module.Path, "home", return_value=fake_home),
            patch.object(cli_module.Path, "cwd", return_value=fake_workspace),
            patch.object(cli_module, "is_startup_completed", return_value=False),
            patch.object(
                cli_module,
                "run_startup_flow",
                side_effect=lambda **_kwargs: events.append("startup"),
            ) as mock_startup,
            patch.object(
                cli_module,
                "cli_main",
                side_effect=lambda: events.append("cli"),
            ) as mock_cli,
        ):
            cli_module.main()

        expected_engine_root = Path(cli_module.__file__).resolve().parents[2]
        mock_startup.assert_called_once_with(
            engine_root=expected_engine_root,
            workspace_root=fake_workspace,
            base=fake_home / ".spark",
        )
        mock_cli.assert_called_once_with()
        assert events == ["startup", "cli"]

    def test_dispatch_init_skips_startup_when_sentinel_exists(
        self,
    ) -> None:
        """Comando init salta il first-run se il sentinel è già presente."""
        import spark.cli as cli_module

        with (
            patch("sys.argv", ["scf", "init"]),
            patch.object(cli_module, "is_startup_completed", return_value=True),
            patch.object(cli_module, "run_startup_flow") as mock_startup,
            patch.object(cli_module, "cli_main") as mock_cli,
        ):
            cli_module.main()

        mock_startup.assert_not_called()
        mock_cli.assert_called_once_with()

    def test_dispatch_init_logs_warning_and_calls_cli_main_on_startup_error(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Comando init non deve bloccare il menu se il first-run fallisce."""
        import spark.cli as cli_module

        with (
            patch("sys.argv", ["scf", "init"]),
            patch.object(cli_module, "is_startup_completed", return_value=False),
            patch.object(
                cli_module,
                "run_startup_flow",
                side_effect=RuntimeError("boom"),
            ),
            patch.object(cli_module, "cli_main") as mock_cli,
        ):
            cli_module.main()

        captured = capsys.readouterr()
        assert "[SPARK-ENGINE][WARNING] Flusso di avvio non disponibile: boom" in captured.err
        mock_cli.assert_called_once_with()

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


# ---------------------------------------------------------------------------
# Test _load_workspace_config (CICLO 5)
# ---------------------------------------------------------------------------


class TestLoadWorkspaceConfig:
    """Test per main._load_workspace_config."""

    def test_m1_config_presente_e_valido(self, tmp_path: Path) -> None:
        """Config presente con path valido — ritorna workspace/.github.

        Args:
            tmp_path: Directory temporanea isolata del test.
        """
        workspace = tmp_path / "my_workspace"
        workspace.mkdir()
        spark_dir = tmp_path / ".spark"
        spark_dir.mkdir()
        (spark_dir / "config.json").write_text(
            json.dumps({"workspace_root": str(workspace)}), encoding="utf-8"
        )

        with patch.object(Path, "home", return_value=tmp_path):
            result = _load_workspace_config()

        assert result == workspace / ".github"

    def test_m2_config_assente_ritorna_none(self, tmp_path: Path) -> None:
        """Nessun config.json — ritorna None silenziosamente.

        Args:
            tmp_path: Directory temporanea isolata del test.
        """
        with patch.object(Path, "home", return_value=tmp_path):
            result = _load_workspace_config()

        assert result is None

    def test_m3_config_con_path_non_esistente_ritorna_none(self, tmp_path: Path) -> None:
        """Config con path non più valido su disco — ritorna None.

        Args:
            tmp_path: Directory temporanea isolata del test.
        """
        spark_dir = tmp_path / ".spark"
        spark_dir.mkdir()
        (spark_dir / "config.json").write_text(
            json.dumps({"workspace_root": str(tmp_path / "nonexistent")}), encoding="utf-8"
        )

        with patch.object(Path, "home", return_value=tmp_path):
            result = _load_workspace_config()

        assert result is None

    def test_config_malformato_ritorna_none(self, tmp_path: Path) -> None:
        """Config JSON malformato — ritorna None senza eccezioni.

        Args:
            tmp_path: Directory temporanea isolata del test.
        """
        spark_dir = tmp_path / ".spark"
        spark_dir.mkdir()
        (spark_dir / "config.json").write_text("{ invalid json }", encoding="utf-8")

        with patch.object(Path, "home", return_value=tmp_path):
            result = _load_workspace_config()

        assert result is None
