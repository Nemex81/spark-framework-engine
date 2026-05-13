"""Test unitari per spark_launcher.py.

Copertura:
- Esistenza del file in root del repository.
- Assenza di codice eseguibile a livello di modulo.
- Presenza del check versione Python.
- Comportamento su ImportError di spark.cli.
- Comportamento su KeyboardInterrupt.
- Risoluzione corretta di _REPO_ROOT.
"""
from __future__ import annotations

import ast
import collections
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Percorso assoluto del launcher nella root del repository.
_ROOT = Path(__file__).resolve().parents[1]
_LAUNCHER = _ROOT / "spark_launcher.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _launcher_source() -> str:
    """Ritorna il sorgente del launcher come stringa."""
    return _LAUNCHER.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test: struttura file
# ---------------------------------------------------------------------------


class TestLauncherFile:
    """Verifica struttura e posizione del file."""

    def test_launcher_exists_in_root(self) -> None:
        """Il file spark_launcher.py deve trovarsi nella root del repository."""
        assert _LAUNCHER.exists(), f"File non trovato: {_LAUNCHER}"

    def test_no_module_level_executable_code(self) -> None:
        """Nessuna istruzione eseguibile deve trovarsi fuori da 'if __name__'.

        Sono ammessi solo: stringhe di docstring e la guard if __name__.
        """
        tree = ast.parse(_launcher_source())
        for node in ast.iter_child_nodes(tree):
            # Docstring come primo nodo (Expr con Constant) è accettata.
            if isinstance(node, ast.Expr) and isinstance(
                node.value, ast.Constant
            ):
                continue
            # La guard if __name__ == "__main__" è l'unica istruzione ammessa.
            if isinstance(node, ast.If):
                test = node.test
                if (
                    isinstance(test, ast.Compare)
                    and isinstance(test.left, ast.Name)
                    and test.left.id == "__name__"
                ):
                    continue
            pytest.fail(
                f"Codice eseguibile a livello di modulo trovato: {ast.dump(node)}"
            )

    def test_python_version_check_present(self) -> None:
        """Il sorgente deve contenere un controllo su sys.version_info."""
        source = _launcher_source()
        assert "version_info" in source, (
            "Controllo versione Python assente in spark_launcher.py"
        )
        assert "(3, 10)" in source, (
            "Soglia Python 3.10 non trovata nel controllo versione"
        )

    def test_repo_root_resolution_uses_parent(self) -> None:
        """_REPO_ROOT deve essere calcolato con Path(__file__).resolve().parent."""
        source = _launcher_source()
        assert "Path(__file__).resolve().parent" in source, (
            "Risoluzione _REPO_ROOT non usa Path(__file__).resolve().parent"
        )


# ---------------------------------------------------------------------------
# Test: comportamento runtime (eseguito tramite exec della guard)
# ---------------------------------------------------------------------------


def _exec_launcher_guard(extra_globals: dict) -> None:
    """Esegue il corpo della guard if __name__ == '__main__' del launcher.

    Imposta __name__ = '__main__' nel namespace di esecuzione.
    """
    source = _launcher_source()
    tree = ast.parse(source)
    # Estrae il corpo della prima (e unica) if __name__ == '__main__'
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.If):
            test = node.test
            if (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "__name__"
            ):
                body_src = ast.unparse(ast.Module(body=node.body, type_ignores=[]))
                # __file__ deve essere nel namespace perche' il launcher usa
                # Path(__file__).resolve().parent per calcolare _REPO_ROOT.
                exec_globals = {
                    "__name__": "__main__",
                    "__file__": str(_LAUNCHER),
                    **extra_globals,
                }
                exec(compile(body_src, str(_LAUNCHER), "exec"), exec_globals)  # noqa: S102
                return
    pytest.fail("Guard if __name__ == '__main__' non trovata nel launcher")


class TestLauncherBehavior:
    """Verifica comportamento runtime del launcher."""

    def test_import_error_exits_with_code_1(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Su ImportError di spark.cli.main deve stampare un messaggio e uscire con 1."""
        # sys.modules[name] = None fa sollevare ImportError all'import machinery
        # senza interferire con altri moduli gia' importati.
        with (
            patch.dict(sys.modules, {"spark.cli.main": None}),
            pytest.raises(SystemExit) as exc_info,
        ):
            _exec_launcher_guard({})

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Errore" in captured.out

    def test_keyboard_interrupt_exits_cleanly(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Su KeyboardInterrupt deve uscire con 0 e stampare un messaggio."""
        mock_main = MagicMock(side_effect=KeyboardInterrupt)

        # Crea un modulo fittizio per spark.cli.main con la funzione main mockata.
        fake_module = types.ModuleType("spark.cli.main")
        fake_module.main = mock_main  # type: ignore[attr-defined]

        with (
            patch.dict(sys.modules, {"spark.cli.main": fake_module}),
            pytest.raises(SystemExit) as exc_info,
        ):
            _exec_launcher_guard({})

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Uscita" in captured.out

    def test_python_version_guard_exits_with_1(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Se la versione Python è < 3.10 deve uscire con 1 e indicare il requisito."""
        # sys.version_info.__class__ non è istanziabile in CPython (tipo C interno).
        # Un namedtuple replica sia il confronto tupla < (3, 10) sia l'accesso
        # per attributo (.major, .minor) usato dal launcher nel messaggio di errore.
        _FakeVersionInfo = collections.namedtuple(
            "version_info", ["major", "minor", "micro", "releaselevel", "serial"]
        )
        fake_version_info = _FakeVersionInfo(2, 7, 18, "final", 0)

        with (
            patch.object(sys, "version_info", fake_version_info),
            pytest.raises(SystemExit) as exc_info,
        ):
            _exec_launcher_guard({})

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "3.10" in captured.out


# ---------------------------------------------------------------------------
# Test: onboarding first-run (sentinel ~/.spark/.scf-init-done)
# ---------------------------------------------------------------------------


class TestLauncherOnboarding:
    """Verifica il flusso wizard-before-menu per nuovi utenti.

    Il sentinel è in Path.home() / '.spark' / '.scf-init-done' (globale per
    macchina) — indipendente dalla directory di lavoro corrente. Nei test si
    mocka Path.home() per isolare il filesystem reale dell'utente.
    """

    def _fake_home(self, tmp_path: Path) -> Path:
        """Ritorna un home fittizio sotto tmp_path per i test."""
        fake = tmp_path / "fakehome"
        fake.mkdir(exist_ok=True)
        return fake

    def test_wizard_called_when_no_sentinel(
        self,
        tmp_path: Path,
    ) -> None:
        """run_wizard() deve essere chiamata quando .scf-init-done è assente.

        Il sentinel globale ~/.spark/.scf-init-done non esiste → wizard invocata
        con cwd=Path.home() / '.spark'.
        """
        fake_home = self._fake_home(tmp_path)
        # ~/.spark/ non esiste ancora → sentinel assente
        wizard_calls: list[Path] = []

        fake_wizard = types.ModuleType("spark.boot.wizard")

        def _fake_run_wizard(cwd: Path | None = None, **_kw: object) -> dict:
            wizard_calls.append(cwd if cwd is not None else Path.cwd())
            return {}

        fake_wizard.run_wizard = _fake_run_wizard  # type: ignore[attr-defined]

        fake_main_mod = types.ModuleType("spark.cli.main")
        fake_main_mod.main = MagicMock(side_effect=SystemExit(0))  # type: ignore[attr-defined]

        with (
            patch.object(Path, "home", return_value=fake_home),
            patch.dict(
                sys.modules,
                {"spark.boot.wizard": fake_wizard, "spark.cli.main": fake_main_mod},
            ),
            pytest.raises(SystemExit),
        ):
            _exec_launcher_guard({})

        assert len(wizard_calls) == 1, "run_wizard() non è stata chiamata"
        # Il launcher deve passare cwd=~/.spark/ alla wizard
        assert wizard_calls[0] == fake_home / ".spark", (
            f"run_wizard() chiamata con cwd sbagliato: {wizard_calls[0]}"
        )

    def test_wizard_skipped_when_sentinel_exists(
        self,
        tmp_path: Path,
    ) -> None:
        """run_wizard() NON deve essere chiamata se .scf-init-done esiste.

        Il sentinel globale ~/.spark/.scf-init-done presente → wizard saltata.
        """
        fake_home = self._fake_home(tmp_path)
        # Crea sentinel in ~/.spark/.scf-init-done
        spark_home = fake_home / ".spark"
        spark_home.mkdir(parents=True, exist_ok=True)
        (spark_home / ".scf-init-done").touch()

        wizard_calls: list[bool] = []

        fake_wizard = types.ModuleType("spark.boot.wizard")
        fake_wizard.run_wizard = lambda *_a, **_kw: wizard_calls.append(True)  # type: ignore[attr-defined]

        fake_main_mod = types.ModuleType("spark.cli.main")
        fake_main_mod.main = MagicMock(side_effect=SystemExit(0))  # type: ignore[attr-defined]

        with (
            patch.object(Path, "home", return_value=fake_home),
            patch.dict(
                sys.modules,
                {"spark.boot.wizard": fake_wizard, "spark.cli.main": fake_main_mod},
            ),
            pytest.raises(SystemExit),
        ):
            _exec_launcher_guard({})

        assert wizard_calls == [], (
            "run_wizard() non deve essere chiamata se il sentinel è presente"
        )
