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

    # v3.0 FIX — Boot-time registry repopulate.
    # Senza questa chiamata, ``populate_mcp_registry`` viene invocata solo con
    # ``engine_manifest`` (sopra) e i pacchetti installati nel deposito
    # ``engine_root/packages/<pkg>/`` non risultano registrati nel
    # ``McpResourceRegistry`` finché non viene eseguita un'operazione
    # install/remove (che chiama ``_v3_repopulate_registry``). Conseguenza
    # pre-fix: ``scf_get_agent``/``scf_get_skill``/etc. ritornano risorse
    # solo engine-side dopo un riavvio del server. Riusiamo il metodo già
    # collaudato dell'engine per coerenza con il flusso lifecycle.
    # DEPRECATION (Round 3): il supporto per manifest schema 2.x privi di
    # ``workspace_files`` resta abilitato qui per retrocompat (``_v3_repopulate_registry``
    # tollera manifest legacy), ma sarà rimosso in v4.0; tutti i nuovi pacchetti
    # devono dichiarare ``schema_version: "3.0"`` con ``workspace_files`` esplicito.
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

    bootstrap_result = app.ensure_minimal_bootstrap()
    _log.info(
        "[SPARK-ENGINE][INFO] Auto-bootstrap status: %s",
        bootstrap_result.get("status", "unknown"),
    )

    # Trasferisci workspace_files di spark-ops nel workspace se non ancora presenti.
    # Idempotente: non sovrascrive file esistenti. Eseguito dopo ensure_minimal_bootstrap
    # affinché la dir .github/ esista già.
    _ensure_spark_ops_workspace_files(context, engine_root)

    # Esegui onboarding completo al primo avvio (idempotente)
    from spark.boot.onboarding import OnboardingManager  # noqa: PLC0415
    onboarding = OnboardingManager(context, inventory, app)
    if onboarding.is_first_run():
        onboarding_result = onboarding.run_onboarding()
        _log.info(
            "[SPARK-ENGINE][INFO] Onboarding completato: %s",
            onboarding_result.get("status", "unknown"),
        )

    sys.stderr.write("\n[SPARK] Inizializzazione completata.\n")
    sys.stderr.write(
        '[SPARK] Prossimo passo: apri VS Code e di\' a Copilot'
        ' "inizializza il workspace SPARK"\n\n'
    )
    return mcp
