"""spark_launcher — Entry point della SPARK Framework CLI.

    python spark_launcher.py    # oppure: python -m spark.cli

Non importare come modulo: la logica eseguibile e' dentro if __name__.
"""
if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Il file e' in root: .parent coincide con la root del repository.
    _REPO_ROOT = Path(__file__).resolve().parent
    # Inserisce la root solo se assente, per non duplicare sys.path.
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))

    # Versione minima richiesta: strutture match/case e union types (3.10).
    if sys.version_info < (3, 10):
        _v = f"{sys.version_info.major}.{sys.version_info.minor}"
        print(f"Errore: SPARK richiede Python 3.10+. Rilevato: {_v}. Aggiorna: https://www.python.org/downloads/")
        sys.exit(1)

    try:
        from spark.cli.main import main  # type: ignore[import]
    except ImportError as exc:
        print(f"Errore importazione spark.cli ({exc}). Esegui: pip install -e .")
        sys.exit(1)

    # Onboarding guidato per nuovi utenti: sentinel globale in ~/.spark/ per
    # garantire che la wizard venga eseguita una sola volta per macchina,
    # indipendentemente dalla directory di lavoro corrente.
    _SPARK_HOME = Path.home() / ".spark"
    # Crea la directory se assente — .touch() non crea parent dirs.
    _SPARK_HOME.mkdir(parents=True, exist_ok=True)
    _SENTINEL = _SPARK_HOME / ".scf-init-done"
    if not _SENTINEL.exists():
        try:
            from spark.boot.wizard import run_wizard  # type: ignore[import]  # noqa: PLC0415

            # Passa cwd=_SPARK_HOME: wizard controlla e scrive il sentinel li'.
            run_wizard(cwd=_SPARK_HOME)
        except Exception as _exc:  # noqa: BLE001
            print(f"[SPARK-ENGINE][WARNING] Wizard non disponibile: {_exc}", file=sys.stderr)

    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nUscita.")
        sys.exit(0)
