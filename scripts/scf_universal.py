#!/usr/bin/env python3
"""SPARK Framework — Global SCF Universal Launcher v5.1.

Auto-finds the SPARK Framework Engine root directory by traversing the
directory tree upwards, then resolves the workspace using WorkspaceLocator.

Uso (da QUALSIASI directory):
    scf init          # Crea .github/ in cwd se non esiste
    python scf_universal.py init
    py scf_universal.py init      # Windows

Funzionamento:
1. Trova spark-framework-engine.py risalendo la directory tree
2. Aggiunge engine root a sys.path
3. Importa WorkspaceLocator
4. Rileva workspace_root (esplicito, locale, fallback cwd)
5. Chiama run_wizard(cwd=workspace_root)

Idempotente: il sentinel .scf-init-done previene esecuzioni duplicate.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

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
    except ImportError as e:
        raise RuntimeError(
            f"Impossibile importare WorkspaceLocator da {engine_root}: {e}"
        ) from e


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point CLI per lo script universale."""
    try:
        engine_root = _find_engine_root()
        workspace_root = _resolve_workspace(engine_root)

        # Importa run_wizard dal contesto del motore
        sys.path.insert(0, str(engine_root))
        from spark.boot.wizard import run_wizard  # noqa: PLC0415

        # Esegui wizard nel contesto del workspace risolto
        run_wizard(cwd=workspace_root)

    except RuntimeError as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"ERRORE imprevisto: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
