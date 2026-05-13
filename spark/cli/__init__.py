"""spark.cli — SPARK CLI launcher.

Punto di ingresso per i comandi di onboarding e gestione workspace
via ``scripts/scf``.

Uso tipico::

    python scripts/scf [init]
    python scripts/scf cli
    py scripts/scf cli          # Windows
"""
from __future__ import annotations

import sys
from pathlib import Path

from spark.cli.main import main as cli_main  # noqa: F401
from spark.cli.startup import is_startup_completed, run_startup_flow


def _run_init_entrypoint() -> None:
    """Esegue il percorso init unificato verso startup e menu principale.

    Il comando ``scripts/scf init`` deve seguire lo stesso boot path del
    launcher root: first-run opzionale e accesso finale al menu principale.
    Gli errori del first-run restano non fatali, cosi' il menu resta sempre
    raggiungibile nei percorsi non fatali.
    """
    engine_root = Path(__file__).resolve().parents[2]
    startup_base = Path.home() / ".spark"

    try:
        if not is_startup_completed(startup_base):
            run_startup_flow(
                engine_root=engine_root,
                workspace_root=Path.cwd(),
                base=startup_base,
            )
    except Exception as exc:  # noqa: BLE001
        print(
            f"[SPARK-ENGINE][WARNING] Flusso di avvio non disponibile: {exc}",
            file=sys.stderr,
        )

    cli_main()


def main() -> None:
    """Dispatch dei comandi CLI.

    Comandi supportati:

    * ``init`` (default) — esegue il boot path unificato verso il menu CLI.
    * ``cli`` — avvia il menu CLI completo (init + pacchetti + plugin + diagnostica).
    """
    args = sys.argv[1:]
    command = args[0] if args else "init"

    if command == "init":
        _run_init_entrypoint()
    elif command == "cli":
        cli_main()
    else:
        print(f"Comando sconosciuto: {command!r}")
        print("Comandi disponibili: init, cli")
        sys.exit(1)
