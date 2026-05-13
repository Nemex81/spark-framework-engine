#!/usr/bin/env python3

"""SPARK Framework — Global SCF Universal Launcher v5.2.

Auto-finds the SPARK Framework Engine root directory by traversing the
directory tree upwards, then resolves the workspace using WorkspaceLocator.

Uso (da QUALSIASI directory, anche workspace vuoto):
    scf init          # Crea .github/ in cwd se non esiste
    python scf_universal.py init
    py scf_universal.py init      # Windows

Funzionamento v5.2:
1. Trova spark-framework-engine.py risalendo la directory tree
2. Auto-setup .venv + deps engine se non disponibili (stdlib: venv + pip)
3. Se venv creato: riavvia con il Python del venv
4. Aggiunge engine root a sys.path
5. Rileva workspace_root (esplicito, locale, fallback cwd)
6. Chiama run_wizard(cwd=workspace_root)

Idempotente:
- .scf-init-done previene esecuzioni wizard duplicate
- .scf-deps-ready previene reinstallazione deps
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Costanti sentinel
# ---------------------------------------------------------------------------

#: Sentinel che indica le dipendenze engine già installate nel workspace.
_DEPS_SENTINEL: str = ".scf-deps-ready"

#: Nome directory venv locale al workspace.
_VENV_DIR: str = ".venv"

# ---------------------------------------------------------------------------
# Helpers venv
# ---------------------------------------------------------------------------


def _get_venv_python(venv_dir: Path) -> Path:
    """Restituisce il percorso Python del venv (Windows/Unix compatibile)."""
    win = venv_dir / "Scripts" / "python.exe"
    return win if win.exists() else venv_dir / "bin" / "python"


def _get_venv_pip(venv_dir: Path) -> Path:
    """Restituisce il percorso pip del venv (Windows/Unix compatibile)."""
    win = venv_dir / "Scripts" / "pip.exe"
    return win if win.exists() else venv_dir / "bin" / "pip"


def _check_engine_deps() -> bool:
    """Restituisce ``True`` se ``mcp`` è importabile nell'ambiente corrente."""
    import importlib.util  # noqa: PLC0415

    try:
        return importlib.util.find_spec("mcp") is not None
    except (ValueError, ModuleNotFoundError):
        # ValueError: modulo in sys.modules senza __spec__ (es. MagicMock stub)
        # ModuleNotFoundError: parent package non trovato
        return "mcp" in sys.modules


def _setup_workspace_deps(workspace_cwd: Path, engine_root: Path) -> Optional[Path]:
    """Crea ``.venv`` locale e installa le dipendenze engine se mancanti.

    Idempotente: salta il setup se:
    - ``mcp`` è già importabile nell'ambiente corrente, oppure
    - ``.scf-deps-ready`` esiste e ``.venv`` contiene un Python valido.

    Args:
        workspace_cwd: Directory del workspace utente (cwd al lancio).
        engine_root: Directory radice del motore SPARK.

    Returns:
        ``Path`` al Python del venv se creato/trovato, ``None`` se le deps
        erano già disponibili nell'ambiente corrente.
    """
    if _check_engine_deps():
        return None  # Deps già disponibili — nessun setup necessario

    venv_dir = workspace_cwd / _VENV_DIR
    sentinel = workspace_cwd / _DEPS_SENTINEL

    # Già configurato in precedenza: ritorna path Python venv
    if sentinel.exists() and venv_dir.exists():
        venv_python = _get_venv_python(venv_dir)
        if venv_python.exists():
            return venv_python

    # Setup necessario
    print("Dipendenze SPARK non trovate nell'ambiente corrente.")
    print(f"Configurazione automatica workspace: {workspace_cwd}")

    import subprocess  # noqa: PLC0415
    import venv as _venv  # noqa: PLC0415

    if not venv_dir.exists():
        print(f"Creazione ambiente virtuale in {venv_dir} ...")
        _venv.create(str(venv_dir), with_pip=True)

    pip_exe = _get_venv_pip(venv_dir)
    req_file = engine_root / "requirements.txt"

    print("Installazione dipendenze engine ...")
    if req_file.exists():
        subprocess.check_call(
            [str(pip_exe), "install", "-r", str(req_file)],
        )
    subprocess.check_call(
        [str(pip_exe), "install", "-e", str(engine_root)],
    )

    sentinel.touch()
    print("Setup dipendenze completato!")

    return _get_venv_python(venv_dir)


# ---------------------------------------------------------------------------
# Engine root discovery
# ---------------------------------------------------------------------------


def _find_engine_root(start_from: Path | None = None) -> Path:
    """Trova la directory engine risalendo l'albero.

    Strategia:
    1. Partenza: start_from (default cwd)
    2. Risali fino a trovare spark-framework-engine.py
    3. Fallback: la directory del file corrente (script in engine/)

    Raises:
        RuntimeError: Se non riesce a trovare il motore.
    """
    start = start_from or Path.cwd().resolve()
    candidate = start

    # Risali fino a 10 livelli
    for _ in range(10):
        if (candidate / "spark-framework-engine.py").is_file():
            return candidate
        if candidate.parent == candidate:  # Raggiunta root filesystem
            break
        candidate = candidate.parent

    # Fallback: se lo script è dentro la directory engine
    script_dir = Path(__file__).resolve().parent
    if (script_dir.parent / "spark-framework-engine.py").is_file():
        return script_dir.parent

    raise RuntimeError(
        f"Engine non trovato risalendo da {start}. "
        f"Assicurati di eseguire da una directory dentro il repository SPARK."
    )


# ---------------------------------------------------------------------------
# Workspace resolution
# ---------------------------------------------------------------------------


def _resolve_workspace(engine_root: Path) -> Path:
    """Risolve il workspace usando WorkspaceLocator.

    Cascata di risoluzione:
    1. CLI flag --workspace
    2. ENV ENGINE_WORKSPACE
    3. ENV WORKSPACE_FOLDER
    4. Local discovery (.vscode, .github markers)
    5. Fallback: cwd
    """
    sys.path.insert(0, str(engine_root))

    try:
        from spark.workspace.locator import WorkspaceLocator  # noqa: PLC0415

        locator = WorkspaceLocator(engine_root=engine_root)
        context = locator.resolve()
        workspace = context.workspace_root
        if workspace is None:
            raise RuntimeError("Workspace non risolto: nessun context disponibile")
        return workspace
    except ImportError:
        # Fallback stdlib: usa la directory corrente come workspace.
        # Avviene quando le deps (mcp/pydantic) non sono nell'ambiente
        # corrente ma il wizard è già avviabile (solo stdlib).
        return Path.cwd().resolve()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point CLI per lo script universale v5.2."""
    try:
        engine_root = _find_engine_root()
        workspace_cwd = Path.cwd().resolve()

        # v5.2: Auto-setup deps se non disponibili nell'ambiente corrente.
        # Se il venv viene creato, riavvia lo script con il Python del venv
        # in modo da avere mcp/pydantic disponibili nel processo figlio.
        venv_python = _setup_workspace_deps(workspace_cwd, engine_root)
        if venv_python is not None and venv_python.exists():
            print("Riavvio con ambiente configurato ...")
            import subprocess as _sp  # noqa: PLC0415

            result = _sp.run([str(venv_python)] + sys.argv)
            sys.exit(result.returncode)

        # Il launcher universale deve convergere allo stesso boot path del
        # launcher root, cosi' l'utente incontra sempre il menu principale.
        sys.path.insert(0, str(engine_root))
        from spark.cli.main import main as cli_main  # noqa: PLC0415
        from spark.cli.startup import is_startup_completed, run_startup_flow  # noqa: PLC0415

        # Risolvi workspace e, se necessario, esegui il first-run introduttivo.
        workspace_root = _resolve_workspace(engine_root)
        startup_base = Path.home() / ".spark"

        try:
            if not is_startup_completed(startup_base):
                run_startup_flow(
                    engine_root=engine_root,
                    workspace_root=workspace_root,
                    base=startup_base,
                )
        except Exception as exc:  # noqa: BLE001
            print(
                f"[SPARK-ENGINE][WARNING] Flusso di avvio non disponibile: {exc}",
                file=sys.stderr,
            )

        cli_main()

    except RuntimeError as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"ERRORE imprevisto: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
