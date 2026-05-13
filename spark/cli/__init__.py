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

from spark.cli.main import main as cli_main  # noqa: F401


def main() -> None:
    """Dispatch dei comandi CLI.

    Comandi supportati:

    * ``init`` (default) — avvia la wizard di onboarding zero-touch.
    * ``cli`` — avvia il menu CLI completo (init + pacchetti + plugin + diagnostica).
    """
    args = sys.argv[1:]
    command = args[0] if args else "init"

    if command == "init":
        from spark.boot.wizard import run_wizard  # noqa: PLC0415

        run_wizard()
    elif command == "cli":
        cli_main()
    else:
        print(f"Comando sconosciuto: {command!r}")
        print("Comandi disponibili: init, cli")
        sys.exit(1)
