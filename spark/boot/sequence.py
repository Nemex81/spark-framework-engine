"""_build_app entry point builder — SPARK Framework Engine.

Extracted to ``spark.boot.sequence`` during Phase 0 modular refactoring.
Re-exported from ``spark.boot``.

Surgical change vs. original hub:
- ``_build_app`` gains an explicit ``engine_root: Path`` parameter (no default)
  so it is file-location-agnostic.
- ``WorkspaceLocator()`` → ``WorkspaceLocator(engine_root=engine_root)``
- ``EngineInventory()``  → ``EngineInventory(engine_root=engine_root)``
- Hub entry point: ``_build_app(engine_root=Path(__file__).resolve().parent).run(transport="stdio")``

Fase 3 (Separazione Runtime):
- Aggiunto: ``resolve_runtime_dir`` per calcolare la dir runtime isolata per workspace.
- Aggiunto: ``_migrate_runtime_to_engine_dir`` per migrare file legacy da .github/runtime/.
- ``runtime_dir`` passato a ``SparkFrameworkEngine`` come parametro esplicito.
"""
from __future__ import annotations

import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any

from spark.boot.validation import resolve_runtime_dir, validate_engine_manifest
from spark.core.constants import _MERGE_SESSIONS_SUBDIR
from spark.inventory import FrameworkInventory
from spark.workspace import WorkspaceLocator

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as _import_exc:
    import logging as _logging
    _logging.getLogger("spark-framework-engine").critical(
        "mcp library not installed. Run: pip install mcp"
    )
    raise SystemExit(1) from _import_exc

_log: logging.Logger = logging.getLogger("spark-framework-engine")
_SPARK_OPS_COPY_LOCK_DIRNAME = ".spark-ops-copy.lock"


def _migrate_runtime_to_engine_dir(github_root: Path, runtime_dir: Path) -> bool:
    """Sposta file runtime da .github/runtime/ alla directory engine isolata.

    Idempotente: scrive il marker ``.runtime-migrated`` al termine.
    Abortisce silenziosamente se esistono sessioni di merge attive nel path
    legacy (INVARIANTE-7).

    Args:
        github_root: Root di ``.github/`` del workspace utente.
        runtime_dir: Directory di runtime target (engine-local, isolata per workspace).

    Returns:
        ``True`` se la migrazione è avvenuta (o era già stata fatta), ``False``
        se saltata per sessioni attive.
    """
    from spark.merge.sessions import MergeSessionManager  # noqa: PLC0415

    marker = runtime_dir / ".runtime-migrated"
    if marker.is_file():
        _log.info("[SPARK-ENGINE][INFO] Runtime già migrato (marker presente): %s", marker)
        return True

    old_sessions_root = github_root / "runtime" / _MERGE_SESSIONS_SUBDIR
    sessions = MergeSessionManager(old_sessions_root)
    active = sessions.list_active()
    if active:
        _log.warning(
            "[SPARK-ENGINE][WARNING] Migrazione runtime saltata: %d sessioni merge attive: %s",
            len(active),
            active,
        )
        return False

    # Sposta le directory runtime dal workspace al percorso engine-local.
    runtime_dir.mkdir(parents=True, exist_ok=True)
    for old_subdir, new_subdir in [
        ("runtime/snapshots", "snapshots"),
        ("runtime/merge-sessions", "merge-sessions"),
        ("runtime/backups", "backups"),
    ]:
        old_path = github_root / old_subdir
        new_path = runtime_dir / new_subdir
        if old_path.is_dir():
            if not new_path.exists():
                new_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_path), str(new_path))
                _log.info(
                    "[SPARK-ENGINE][INFO] Runtime migrato: %s → %s",
                    old_path,
                    new_path,
                )
            else:
                _log.info(
                    "[SPARK-ENGINE][INFO] Runtime migration: %s già presente, skip",
                    new_path,
                )

    # Sposta user-prefs: rimane in .github/ ma perde il prefisso runtime/.
    old_prefs = github_root / "runtime" / "spark-user-prefs.json"
    new_prefs = github_root / "user-prefs.json"
    if old_prefs.is_file() and not new_prefs.is_file():
        shutil.move(str(old_prefs), str(new_prefs))
        _log.info(
            "[SPARK-ENGINE][INFO] User prefs migrato: %s → %s",
            old_prefs,
            new_prefs,
        )

    marker.write_text("migrated", encoding="utf-8")
    _log.info("[SPARK-ENGINE][INFO] Migrazione runtime completata. Marker scritto: %s", marker)
    return True


def _ensure_spark_ops_workspace_files(context: Any, engine_root: Path) -> None:
    """Copia i workspace_files di spark-ops nel workspace utente se non presenti.

    Legge il manifest da ``packages/spark-ops/package-manifest.json`` e copia
    ogni file dichiarato in ``workspace_files`` dalla sorgente locale del package
    store verso ``context.github_root``.

    Idempotente: non sovrascrive file già presenti nel workspace.

    Args:
        context: WorkspaceContext con ``github_root`` del workspace utente.
        engine_root: Root del motore SPARK.
    """
    ops_manifest_path = engine_root / "packages" / "spark-ops" / "package-manifest.json"
    if not ops_manifest_path.is_file():
        _log.debug(
            "[SPARK-ENGINE][DEBUG] spark-ops manifest non trovato, skip boot transfer: %s",
            ops_manifest_path,
        )
        return

    try:
        ops_manifest = json.loads(ops_manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "[SPARK-ENGINE][WARNING] Errore lettura spark-ops manifest, skip boot transfer: %s",
            exc,
        )
        return

    workspace_files = ops_manifest.get("workspace_files", [])
    if not workspace_files:
        return

    ops_source_root = engine_root / "packages" / "spark-ops"
    github_root = context.github_root
    github_root.mkdir(parents=True, exist_ok=True)
    lock_dir = github_root / _SPARK_OPS_COPY_LOCK_DIRNAME

    try:
        lock_dir.mkdir(parents=False, exist_ok=False)
    except FileExistsError:
        _log.warning(
            "[SPARK-ENGINE][WARNING] spark-ops workspace transfer già in corso, skip: %s",
            lock_dir,
        )
        return

    try:
        for rel_path in workspace_files:
            # rel_path è relativo alla root del package, es. ".github/agents/spark-assistant.agent.md"
            # Il dest è dentro github_root: strip del prefisso ".github/"
            if rel_path.startswith(".github/"):
                within_github = rel_path[len(".github/"):]
            else:
                within_github = rel_path

            dest = github_root / within_github
            source = ops_source_root / rel_path

            if dest.is_file():
                _log.debug(
                    "[SPARK-ENGINE][DEBUG] spark-ops workspace file già presente, skip: %s",
                    dest,
                )
                continue

            if not source.is_file():
                _log.warning(
                    "[SPARK-ENGINE][WARNING] spark-ops source file non trovato, skip: %s",
                    source,
                )
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source), str(dest))
            _log.info(
                "[SPARK-ENGINE][INFO] spark-ops workspace file copiato: %s → %s",
                source,
                dest,
            )
    finally:
        try:
            lock_dir.rmdir()
        except OSError:
            _log.warning(
                "[SPARK-ENGINE][WARNING] impossibile rimuovere bootstrap lock dir: %s",
                lock_dir,
            )


def _boot_repopulate_registry(app: Any, inventory: Any) -> None:
    """Ripopola il registry MCP al boot con risorse dai pacchetti installati.

    Chiamata da ``_build_app`` dopo la costruzione dell'engine per garantire
    che i pacchetti installati nel deposito ``engine_root/packages/<pkg>/``
    siano registrati nel ``McpResourceRegistry`` fin dal primo avvio del server.

    Note:
        Senza questa chiamata, ``populate_mcp_registry`` viene invocata solo
        con ``engine_manifest`` e i pacchetti del deposito non risultano
        visibili a ``scf_get_agent`` / ``scf_get_skill`` / etc. dopo un
        riavvio del server.

    Note (Deprecation):
        Il supporto per manifest schema 2.x privi di ``workspace_files`` è
        mantenuto per retrocompatibilità (``_v3_repopulate_registry`` tollera
        manifest legacy), ma sarà rimosso in v4.0. Tutti i nuovi pacchetti
        devono dichiarare ``schema_version: "3.0"`` con ``workspace_files``
        esplicito.

    Args:
        app: Istanza ``SparkFrameworkEngine`` già costruita.
        inventory: ``FrameworkInventory`` associato all'engine.
    """
    try:
        app._v3_repopulate_registry()
        if inventory.mcp_registry is not None:
            _log.info(
                "[SPARK-ENGINE][INFO] MCP registry repopulated at boot: %d URI totali",
                len(inventory.mcp_registry.list_all()),
            )
    except (OSError, ValueError) as exc:
        _log.warning(
            "[SPARK-ENGINE][WARNING] Boot registry repopulate failed: %s",
            exc,
        )


def _optional_spark_base_install(
    context: Any,
    engine_root: Path,
    *,
    interactive: bool = True,
) -> None:
    """Propone opzionalmente l'installazione di spark-base come plugin nel workspace.

    Verifica se spark-base è già installato nel manifest locale; in caso negativo
    e se ``interactive=True``, mostra un prompt testuale che invita l'utente a
    installarlo dal repository remoto tramite ``RegistryManager``.

    In modalità non-interattiva (``interactive=False``) o quando spark-base è già
    presente, la funzione ritorna silenziosamente senza effetti collaterali.

    Il bootstrap non viene mai bloccato da questo step: qualsiasi eccezione di rete
    o di filesystem viene catturata e registrata come warning su stderr.

    Args:
        context: ``WorkspaceContext`` con ``github_root`` e ``workspace_root``.
        engine_root: Radice del repository del motore SCF.
        interactive: Se ``False``, salta silenziosamente il prompt.
    """
    # ------------------------------------------------------------------
    # 1. Verifica presenza locale spark-base
    # ------------------------------------------------------------------
    try:
        from spark.manifest.manifest import ManifestManager  # noqa: PLC0415

        manifest = ManifestManager(context.github_root)
        installed = manifest.get_installed_versions()
        if "spark-base" in installed:
            _log.debug(
                "[SPARK-ENGINE][DEBUG] spark-base già installato, skip prompt opzionale.",
            )
            return
    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "[SPARK-ENGINE][WARNING] Errore lettura manifest per check spark-base: %s",
            exc,
        )
        return

    # ------------------------------------------------------------------
    # 2. Skip silenzioso in modalità non-interattiva
    # ------------------------------------------------------------------
    if not interactive:
        _log.debug(
            "[SPARK-ENGINE][DEBUG] Modalità non-interattiva, skip prompt spark-base opzionale.",
        )
        return

    # ------------------------------------------------------------------
    # 3. Carica registro remoto e cerca entry spark-base
    # ------------------------------------------------------------------
    from spark.cli.registry_manager import RegistryManager  # noqa: PLC0415

    mgr = RegistryManager(context.github_root, engine_root)
    registry = mgr._load_registry()
    if registry is None:
        _log.warning(
            "[SPARK-ENGINE][WARNING] Registro remoto non raggiungibile, skip prompt spark-base.",
        )
        return

    spark_base_entry = next(
        (p for p in registry.get("packages", []) if p.get("id") == "spark-base"),
        None,
    )
    if spark_base_entry is None:
        _log.warning(
            "[SPARK-ENGINE][WARNING] Voce spark-base non trovata nel registro remoto, skip.",
        )
        return

    # ------------------------------------------------------------------
    # 4. Mostra prompt interattivo
    # ------------------------------------------------------------------
    _YES: frozenset[str] = frozenset(("s", "si", "sì", "y", "yes"))
    _NO: frozenset[str] = frozenset(("n", "no"))
    prompt_text = (
        "\nspark-base non è installato nel tuo workspace.\n\n"
        "Vuoi installarlo come plugin indipendente? (consigliato)\n"
        "  [s] Sì  — installa spark-base dal repository remoto\n"
        "  [n] No  — usa spark-base via MCP tramite gli agenti\n"
        "            di spark-ops (nessuna copia locale)\n\n"
        "Scegli [s/n]: "
    )

    answer = input(prompt_text).strip().lower()
    if answer not in _YES and answer not in _NO:
        answer = input("Risposta non riconosciuta. Scegli [s/n]: ").strip().lower()
        if answer not in _YES and answer not in _NO:
            _log.warning(
                "[SPARK-ENGINE][WARNING] "
                "Risposta non riconosciuta per prompt spark-base, trattato come 'no'.",
            )
            answer = "n"

    if answer in _NO:
        print(  # noqa: T201
            "spark-base saltato, disponibile via MCP tramite gli agenti di spark-ops.",
        )
        return

    # ------------------------------------------------------------------
    # 5. Installazione
    # ------------------------------------------------------------------
    print("Installazione spark-base in corso ...")  # noqa: T201
    try:
        result = mgr._download_and_install_plugin(spark_base_entry)
        if result.get("success"):
            print(  # noqa: T201
                f"spark-base installato. File copiati: {result.get('files_copied', 0)}",
            )
        else:
            _log.warning(
                "[SPARK-ENGINE][WARNING] Installazione spark-base fallita: %s",
                result.get("error", "errore sconosciuto"),
            )
            print(  # noqa: T201
                f"Installazione spark-base fallita: {result.get('error', 'errore sconosciuto')}",
            )
    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "[SPARK-ENGINE][WARNING] Errore imprevisto installazione spark-base: %s",
            exc,
        )
        print(  # noqa: T201
            f"Errore installazione spark-base, installazione saltata: {exc}",
        )


def _build_app(engine_root: Path) -> FastMCP:
    # Import here to avoid circular import at module level; engine.py imports
    # from spark.inventory and spark.workspace which are always safe.
    from spark.boot.engine import SparkFrameworkEngine  # noqa: PLC0415

    mcp: FastMCP = FastMCP("sparkFrameworkEngine")

    locator = WorkspaceLocator(engine_root=engine_root)
    context = locator.resolve()
    _log.info("Workspace resolved: %s", context.workspace_root)

    runtime_dir = resolve_runtime_dir(engine_root, context.workspace_root)
    _log.info("[SPARK-ENGINE][INFO] Runtime dir: %s", runtime_dir)
    _migrate_runtime_to_engine_dir(context.github_root, runtime_dir)

    inventory = FrameworkInventory(context)
    _log.info(
        "Framework inventory: %d agents, %d skills, %d instructions, %d prompts",
        len(inventory.list_agents()), len(inventory.list_skills()),
        len(inventory.list_instructions()), len(inventory.list_prompts()),
    )

    # v3.0: popola McpResourceRegistry con risorse engine + override workspace.
    # I package_manifests del deposito centralizzato vengono integrati in Fase 5.
    # SPARK_STRICT_BOOT=1 abilita comportamento fatale su errore manifest (default off).
    engine_manifest, _manifest_status, _manifest_ok = validate_engine_manifest(engine_root)
    if not _manifest_ok:
        _log.info("[SPARK-ENGINE][INFO] Engine manifest: %s", _manifest_status)
    inventory.populate_mcp_registry(engine_manifest=engine_manifest)
    if inventory.mcp_registry is not None:
        _log.info(
            "MCP resource registry: %d URI registrati",
            len(inventory.mcp_registry.list_all()),
        )

    app = SparkFrameworkEngine(mcp, context, inventory, runtime_dir=runtime_dir)
    app.register_resources()
    app.register_tools()

    _boot_repopulate_registry(app, inventory)

    bootstrap_result = app.ensure_minimal_bootstrap()
    _log.info(
        "[SPARK-ENGINE][INFO] Auto-bootstrap status: %s",
        bootstrap_result.get("status", "unknown"),
    )

    # Trasferisci workspace_files di spark-ops nel workspace se non ancora presenti.
    # Idempotente: non sovrascrive file esistenti. Eseguito dopo ensure_minimal_bootstrap
    # affinché la dir .github/ esista già.
    _ensure_spark_ops_workspace_files(context, engine_root)

    # Proponi installazione opzionale di spark-base se non ancora presente.
    # Idempotente: skip silenzioso se spark-base è già installato o se il server è
    # avviato in modalità non-interattiva (es. MCP stdio transport, CI, pipe).
    _optional_spark_base_install(context, engine_root, interactive=sys.stdin.isatty())

    # Esegui onboarding completo al primo avvio (idempotente)
    from spark.boot.onboarding import OnboardingManager  # noqa: PLC0415
    onboarding = OnboardingManager(context, inventory, app)
    if onboarding.is_first_run():
        onboarding_result = onboarding.run_onboarding()
        _log.info(
            "[SPARK-ENGINE][INFO] Onboarding completato: %s",
            onboarding_result.get("status", "unknown"),
        )

    _log.info("[SPARK-ENGINE][INFO] Inizializzazione completata.")
    _log.info(
        "[SPARK-ENGINE][INFO] Prossimo passo: apri VS Code e di' a Copilot "
        '"inizializza il workspace SPARK"'
    )
    return mcp
