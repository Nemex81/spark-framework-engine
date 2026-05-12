"""spark.cli — SPARK CLI launcher.

Punto di ingresso per il singolo comando di onboarding via ``scripts/scf``.

Uso tipico::

    python scripts/scf [init]
    py scripts/scf [init]          # Windows
"""
from __future__ import annotations

import sys


def main() -> None:
    """Dispatch dei comandi CLI.

    Comandi supportati:

    * ``init`` (default) — avvia la wizard di onboarding zero-touch.
    """
    args = sys.argv[1:]
    command = args[0] if args else "init"

    if command == "init":
        from spark.boot.wizard import run_wizard  # noqa: PLC0415

        run_wizard()
    else:
        print(f"Comando sconosciuto: {command!r}")
        print("Comandi disponibili: init")
        sys.exit(1)
