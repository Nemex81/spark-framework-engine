"""spark.cli.main — Entry point del SPARK Framework CLI.

Menu principale per l'inizializzazione workspace, gestione pacchetti
e plugin remoti. Accessibile da tastiera, nessun output decorativo.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

_log: logging.Logger = logging.getLogger("spark-framework-engine")

_MENU_TEXT = """\
=== SPARK Framework CLI ===
1. Inizializza nuovo workspace (nuovo utente)
2. Gestisci pacchetti installati
3. Sfoglia e installa plugin dal registro
4. Verifica e applica aggiornamenti
5. Diagnostica e stato sistema
6. scf doctor (diagnostica avanzata)
0. Esci
Scegli [0-6]:"""


def main() -> None:
    """Entry point del SPARK CLI.

    Calcola automaticamente ``engine_root`` dalla posizione del file.
    Richiede ``github_root`` all'utente se non è rilevabile automaticamente.
    Gestisce ``KeyboardInterrupt`` e ``EOFError`` con uscita pulita.
    """
    try:
        _run_main()
    except (KeyboardInterrupt, EOFError):
        print("\nUscita.")
        sys.exit(0)


def _run_main() -> None:
    """Logica principale del menu CLI (separata da main() per testabilità)."""
    # engine_root: spark/cli/main.py → spark/cli/ → spark/ → engine_root
    engine_root = Path(__file__).resolve().parents[2]
    github_root = _resolve_github_root(engine_root)

    while True:
        print(f"\n{_MENU_TEXT} ", end="")
        try:
            choice = input().strip()
        except (KeyboardInterrupt, EOFError):
            print("\nUscita.")
            sys.exit(0)

        if choice == "0":
            print("Arrivederci.")
            break
        elif choice == "1":
            _cmd_init(engine_root)
        elif choice == "2":
            _cmd_packages(github_root, engine_root)
        elif choice == "3":
            _cmd_registry(github_root, engine_root)
        elif choice == "4":
            _cmd_updates(github_root, engine_root)
        elif choice == "5":
            _cmd_diagnostics(github_root, engine_root)
        elif choice == "6":
            _cmd_doctor(github_root, engine_root)
        else:
            print("Scelta non valida. Inserisci un numero tra 0 e 6.")


def _load_workspace_config() -> Path | None:
    """Carica il workspace_root da ~/.spark/config.json.

    Returns:
        Path assoluto di .github/ nel workspace salvato,
        oppure None se il file non esiste, è malformato,
        o il path non è più valido su disco.
    """
    config_file = Path.home() / ".spark" / "config.json"
    try:
        data = json.loads(config_file.read_text(encoding="utf-8"))
        workspace_root = Path(data["workspace_root"])
        if workspace_root.is_dir():
            return workspace_root / ".github"
        return None
    except (FileNotFoundError, json.JSONDecodeError, KeyError, OSError):
        return None


def _resolve_github_root(engine_root: Path) -> Path:
    """Determina github_root del workspace utente corrente.

    Usa ``~/.spark/config.json`` come fonte prioritaria se presente e valido;
    poi prova ``WorkspaceLocator``; come fallback usa la directory corrente / ``.github/``.

    Args:
        engine_root: Root del motore SPARK.

    Returns:
        Path assoluto di ``.github/`` del workspace utente.
    """
    # Primo tentativo: config.json persistito dallo startup wizard
    from_config = _load_workspace_config()
    if from_config is not None:
        return from_config

    # Secondo tentativo: WorkspaceLocator
    try:
        from spark.workspace import WorkspaceLocator  # noqa: PLC0415

        locator = WorkspaceLocator(engine_root=engine_root)
        context = locator.resolve()
        return context.github_root
    except Exception as exc:  # noqa: BLE001
        _log.debug("[SPARK-ENGINE][CLI] WorkspaceLocator fallback: %s", exc)
        return Path.cwd() / ".github"


def _cmd_init(engine_root: Path) -> None:
    """Avvia l'inizializzazione guidata di un nuovo workspace.

    Args:
        engine_root: Root del motore SPARK.
    """
    from spark.cli.init_manager import InitManager  # noqa: PLC0415

    InitManager(engine_root).run()


def _cmd_packages(github_root: Path, engine_root: Path) -> None:
    """Apre il sotto-menu di gestione pacchetti installati.

    Args:
        github_root: Root ``.github/`` del workspace.
        engine_root: Root del motore SPARK.
    """
    from spark.cli.package_manager import PackageManager  # noqa: PLC0415

    PackageManager(github_root, engine_root).run()


def _cmd_registry(github_root: Path, engine_root: Path) -> None:
    """Apre il sotto-menu di sfoglio e installazione plugin dal registro.

    Args:
        github_root: Root ``.github/`` del workspace.
        engine_root: Root del motore SPARK.
    """
    from spark.cli.registry_manager import RegistryManager  # noqa: PLC0415

    RegistryManager(github_root, engine_root).run()


def _cmd_updates(github_root: Path, engine_root: Path) -> None:
    """Verifica e applica aggiornamenti plugin disponibili.

    Apre il RegistryManager e chiama direttamente ``_apply_updates()``.

    Args:
        github_root: Root ``.github/`` del workspace.
        engine_root: Root del motore SPARK.
    """
    from spark.cli.registry_manager import RegistryManager  # noqa: PLC0415

    mgr = RegistryManager(github_root, engine_root)
    mgr._check_updates()
    confirm = input("Applicare gli aggiornamenti? [s/N]: ").strip().lower()
    if confirm in ("s", "si", "sì", "y", "yes"):
        mgr._apply_updates()


def _cmd_diagnostics(github_root: Path, engine_root: Path) -> None:
    """Mostra diagnostica e stato del sistema SPARK.

    Args:
        github_root: Root ``.github/`` del workspace.
        engine_root: Root del motore SPARK.
    """
    print("\nDiagnostica SPARK:")
    print(f"  engine_root: {engine_root}")
    print(f"  github_root: {github_root}")
    print(f"  github_root esiste: {github_root.is_dir()}")

    try:
        from spark.core.constants import (  # noqa: PLC0415
            _ALLOWED_UPDATE_MODES,
            _BOOTSTRAP_UPDATE_MODES,
        )

        print(f"  _ALLOWED_UPDATE_MODES: {sorted(_ALLOWED_UPDATE_MODES)}")
        print(f"  _BOOTSTRAP_UPDATE_MODES: {sorted(_BOOTSTRAP_UPDATE_MODES)}")
    except Exception as exc:  # noqa: BLE001
        _log.warning("[SPARK-ENGINE][CLI] Errore lettura update modes: %s", exc)

    try:
        import json  # noqa: PLC0415

        policy_file = github_root / "runtime" / "update_policy.json"
        if policy_file.is_file():
            with policy_file.open(encoding="utf-8") as fh:
                policy_data = json.load(fh)
            print(f"  update_policy auto_update: {policy_data.get('auto_update')}")
            print(f"  update_policy default_mode: {policy_data.get('default_mode')}")
        else:
            print("  update_policy.json: assente")
    except Exception as exc:  # noqa: BLE001
        _log.warning("[SPARK-ENGINE][CLI] Errore lettura update_policy.json: %s", exc)

    try:
        sentinel_welcome = github_root / "agents" / "Agent-Welcome.md"
        sentinel_agents = github_root / "AGENTS.md"
        print(
            "  .github/agents/Agent-Welcome.md: "
            f"{'presente' if sentinel_welcome.is_file() else 'assente'}"
        )
        print(
            "  .github/AGENTS.md: "
            f"{'presente' if sentinel_agents.is_file() else 'assente'}"
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning("[SPARK-ENGINE][CLI] Errore verifica sentinelle bootstrap: %s", exc)

    try:
        from spark.manifest.manifest import ManifestManager  # noqa: PLC0415

        manifest = ManifestManager(github_root)
        installed = manifest.get_installed_versions()
        print(f"  Pacchetti installati: {len(installed)}")
        for pkg_id, version in sorted(installed.items()):
            print(f"    - {pkg_id} ({version})")
    except Exception as exc:  # noqa: BLE001
        _log.warning("[SPARK-ENGINE][CLI] Errore diagnostica manifest: %s", exc)
        print(f"  Errore lettura manifest: {exc}")

    try:
        from spark.core.constants import ENGINE_VERSION  # noqa: PLC0415

        print(f"  ENGINE_VERSION: {ENGINE_VERSION}")
    except Exception:  # noqa: BLE001
        pass


def _cmd_doctor(github_root: Path, engine_root: Path) -> None:
    """Avvia la diagnostica avanzata scf doctor.

    Args:
        github_root: Root ``.github/`` del workspace.
        engine_root: Root del motore SPARK.
    """
    print("\nSCF Doctor — avvio diagnostica...")
    fix_input = input("Attivare modalità --fix (riparazione automatica)? [s/N]: ").strip().lower()
    fix = fix_input in ("s", "si", "sì", "y", "yes")
    report_input = input("Emettere report JSON su stdout? [s/N]: ").strip().lower()
    report = report_input in ("s", "si", "sì", "y", "yes")

    from spark.cli.doctor import run_doctor  # noqa: PLC0415

    run_doctor(github_root, engine_root, fix=fix, report=report)
