"""spark.boot.wizard — SPARK Zero-Touch Init Wizard.

Guided 3-step onboarding wizard for new SPARK workspaces.

Idempotente: si interrompe immediatamente se il sentinel ``.scf-init-done``
esiste nella directory di lavoro corrente.

Accessibile NVDA: ogni passo usa ``print()`` esplicito e ``input()`` numerato
(1=Esegui, 0=Salta, q=Esci), senza unicode decorativi.

Nessuna dipendenza esterna: solo moduli stdlib (``os``, ``sys``, ``pathlib``).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------------------
# Costanti pubbliche
# ---------------------------------------------------------------------------

#: Nome del file sentinel che indica workspace gia inizializzato.
SENTINEL_FILE: str = ".scf-init-done"

#: Passi guidati esposti dalla wizard.  Ogni tupla e' ``(label, comando)``.
WIZARD_STEPS: list[tuple[str, str]] = [
    ("Lista pacchetti remoti disponibili", "mcp scf_plugin_list_remote"),
    (
        "Installa scf-master-codecrafter",
        "mcp scf_plugin_install_remote scf-master-codecrafter",
    ),
    ("Apri VSCode in Agent Mode", "code ."),
]


# ---------------------------------------------------------------------------
# Helpers interni
# ---------------------------------------------------------------------------


def _is_already_initialized(cwd: Path) -> bool:
    """Restituisce ``True`` se il sentinel esiste nella directory *cwd*."""
    return (cwd / SENTINEL_FILE).exists()


def _mark_initialized(cwd: Path) -> None:
    """Crea il file sentinel in *cwd* (idempotente se gia esiste)."""
    sentinel = cwd / SENTINEL_FILE
    sentinel.touch()


# ---------------------------------------------------------------------------
# Entry point principale
# ---------------------------------------------------------------------------


def run_wizard(
    cwd: Path | None = None,
    *,
    _input: Callable[[str], str] | None = None,
) -> dict[str, str]:
    """Esegue la wizard interattiva di onboarding SPARK.

    La funzione e' progettata per essere testabile: il parametro ``_input``
    permette di iniettare un sostituto di ``input()`` nei test unitari.

    Args:
        cwd: Directory di lavoro (default ``Path.cwd()``).
        _input: Callable alternativo a ``input()`` — usato esclusivamente
            nei test.

    Returns:
        Dizionario con l'esito di ogni passo::

            {
                "status": "already_initialized",   # se sentinel trovato
            }

        oppure, dopo l'esecuzione dei passi::

            {
                "step_1": "executed" | "skipped" | "aborted",
                "step_2": ...,
                "step_3": ...,
            }
    """
    base: Path = cwd if cwd is not None else Path.cwd()
    get_input: Callable[[str], str] = _input if _input is not None else input

    # -- Guardia idempotenza ------------------------------------------------
    if _is_already_initialized(base):
        print("SPARK gia pronto! Usa: mcp scf_get_agent spark-assistant")
        return {"status": "already_initialized"}

    # -- Intestazione -------------------------------------------------------
    print("=" * 60)
    print("SPARK Framework - Wizard di Onboarding v5.0")
    print("=" * 60)
    print(f"Passi totali: {len(WIZARD_STEPS)}")
    print("Opzioni per ogni passo: 1=Esegui  0=Salta  q=Esci")
    print()

    results: dict[str, str] = {}
    total = len(WIZARD_STEPS)

    for idx, (label, command) in enumerate(WIZARD_STEPS, 1):
        print(f"[{idx}/{total}] {label}")
        print(f"    Comando: {command}")
        choice = get_input("Scelta (1/0/q): ").strip().lower()

        if choice == "1":
            os.system(command)  # noqa: S605 — strumento CLI, non transport MCP
            results[f"step_{idx}"] = "executed"
        elif choice == "0":
            print("    -> Saltato.")
            results[f"step_{idx}"] = "skipped"
        elif choice == "q":
            print("    -> Uscita anticipata.")
            results[f"step_{idx}"] = "aborted"
            # Segna i passi rimanenti come saltati
            for remaining in range(idx + 1, total + 1):
                results[f"step_{remaining}"] = "skipped"
            break
        else:
            print(f"    -> Scelta non riconosciuta '{choice}', passo saltato.")
            results[f"step_{idx}"] = "skipped"

    # -- Sentinel e messaggio finale ----------------------------------------
    _mark_initialized(base)
    print()
    print("SPARK pronto! Risorsa di partenza: mcp scf_get_agent spark-assistant")
    return results


# ---------------------------------------------------------------------------
# Esecuzione diretta
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_wizard()
