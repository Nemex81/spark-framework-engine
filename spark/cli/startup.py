"""spark.cli.startup - Flusso di avvio terminale per il primo lancio.

Mostra una guida introduttiva una sola volta per macchina quando il launcher
root ``spark_launcher.py`` viene eseguito da un progetto utente.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

SENTINEL_FILE = ".scf-init-done"


def _ensure_startup_base(base: Path | None = None) -> Path:
    """Risolva e crei la directory globale di startup SPARK.

    Args:
        base: Directory base opzionale. Se assente usa ``Path.home() / ".spark"``.

    Returns:
        Path assoluto della directory base di startup.
    """
    startup_base = base if base is not None else Path.home() / ".spark"
    startup_base.mkdir(parents=True, exist_ok=True)
    return startup_base


def is_startup_completed(base: Path | None = None) -> bool:
    """Indica se il flusso di primo avvio e' gia stato completato.

    Args:
        base: Directory base opzionale del sentinel.

    Returns:
        True se il sentinel globale esiste, altrimenti False.
    """
    startup_base = _ensure_startup_base(base)
    return (startup_base / SENTINEL_FILE).exists()


def _mark_startup_completed(base: Path) -> None:
    """Scrive il sentinel che chiude il flusso di primo avvio.

    Args:
        base: Directory base del sentinel globale.
    """
    (base / SENTINEL_FILE).touch(exist_ok=True)


def run_startup_flow(
    engine_root: Path,
    workspace_root: Path | None = None,
    *,
    base: Path | None = None,
    _input: Callable[[str], str] | None = None,
) -> dict[str, str]:
    """Esegue il flusso introduttivo del primo avvio da terminale.

    Il flusso e' progettato per essere breve, leggibile da screen reader e
    convergere sempre verso il menu principale del CLI root. Se l'utente sceglie
    di rimandare la guida, il sentinel non viene scritto e la schermata verra'
    riproposta al prossimo lancio.

    Args:
        engine_root: Root del repository del motore SPARK.
        workspace_root: Root del progetto utente corrente. Di default usa ``Path.cwd()``.
        base: Directory base opzionale della sentinel globale.
        _input: Callable alternativo a ``input()`` per i test.

    Returns:
        Dizionario con lo stato del flusso: ``already_initialized``, ``completed``
        oppure ``deferred``.
    """
    startup_base = _ensure_startup_base(base)
    if is_startup_completed(startup_base):
        return {"status": "already_initialized"}

    current_workspace = workspace_root if workspace_root is not None else Path.cwd()
    get_input = _input if _input is not None else input

    print("=" * 60)
    print("SPARK Framework - Avvio iniziale")
    print("=" * 60)
    print("Questa guida viene mostrata una sola volta per macchina.")
    print("Il menu principale restera' sempre il punto di accesso operativo.")
    print(f"Workspace corrente: {current_workspace}")
    print(f"Percorso motore SPARK: {engine_root}")
    print()
    print("Prossimo passo consigliato:")
    print("Scegli 1 nel menu principale per inizializzare il workspace utente.")
    print()
    print("Opzioni:")
    print("1. Continua e salva questo avvio iniziale")
    print("0. Continua senza salvare questo avvio iniziale")

    choice = get_input("Scelta (1/0): ").strip()
    if choice == "0":
        print("Avvio iniziale rimandato. Apertura del menu principale...")
        return {"status": "deferred"}

    # Il sentinel viene scritto solo dopo una conferma esplicita, cosi' un
    # rinvio continua a riproporre la guida nelle esecuzioni successive.
    _mark_startup_completed(startup_base)
    print("Avvio iniziale completato. Apertura del menu principale...")
    return {"status": "completed"}