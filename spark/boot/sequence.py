"""_build_app entry point builder — SPARK Framework Engine.

Extracted to ``spark.boot.sequence`` during Phase 0 modular refactoring.
Re-exported from ``spark.boot``.

Surgical change vs. original hub:
- ``_build_app`` gains an explicit ``engine_root: Path`` parameter (no default)
  so it is file-location-agnostic.
- ``WorkspaceLocator()`` → ``WorkspaceLocator(engine_root=engine_root)``
- ``EngineInventory()``  → ``EngineInventory(engine_root=engine_root)``
- Hub entry point: ``_build_app(engine_root=Path(__file__).resolve().parent).run(transport="stdio")``
"""
from __future__ import annotations

import logging
from pathlib import Path

from spark.boot.validation import validate_engine_manifest
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


def _build_app(engine_root: Path) -> FastMCP:
    # Import here to avoid circular import at module level; engine.py imports
    # from spark.inventory and spark.workspace which are always safe.
    from spark.boot.engine import SparkFrameworkEngine  # noqa: PLC0415

    mcp: FastMCP = FastMCP("sparkFrameworkEngine")

    locator = WorkspaceLocator(engine_root=engine_root)
    context = locator.resolve()
    _log.info("Workspace resolved: %s", context.workspace_root)

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

    app = SparkFrameworkEngine(mcp, context, inventory)
    app.register_resources()
    app.register_tools()
    _log.info("Tools registered: 44 total")

    return mcp
