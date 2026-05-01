"""EngineInventory — SPARK Framework Engine.

Extracted to ``spark.inventory.engine`` during Phase 0 modular refactoring.
Re-exported from ``spark.inventory``.

Surgical change vs. original hub:
- ``__init__`` now takes an explicit ``engine_root: Path`` parameter instead
  of computing ``Path(__file__).resolve().parent`` internally, making the
  class file-location-agnostic.
- Callers must pass ``EngineInventory(engine_root=Path(__file__).resolve().parent)``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, ClassVar

from spark.core.models import WorkspaceContext
from spark.inventory.framework import FrameworkInventory

_log: logging.Logger = logging.getLogger("spark-framework-engine")


class EngineInventory(FrameworkInventory):
    """Discover skills/instructions under the engine's own ``.github/`` tree.

    The engine ships a curated set of universal skills and instructions that
    are hosted centrally and consumed by workspaces via dedicated MCP
    resource URIs (``engine-skills://``, ``engine-instructions://``). Unlike
    :class:`FrameworkInventory`, this inventory does NOT read from the user
    workspace: it reads from the engine root's ``.github/`` directory.

    Starting with engine v3.0 it also loads ``engine-manifest.json`` from the
    engine root (next to ``spark-framework-engine.py``) and exposes its
    contents via :attr:`engine_manifest`. The manifest declares the engine's
    own ``workspace_files`` (Copilot-loaded instructions) and ``mcp_resources``
    (MCP-only agents/instructions/prompts/skills owned by the engine itself).
    """

    ENGINE_MANIFEST_FILENAME: ClassVar[str] = "engine-manifest.json"

    def __init__(self, engine_root: Path) -> None:  # noqa: D401 - simple override
        resolved_root: Path = engine_root
        engine_github_root = resolved_root / ".github"
        synthetic_ctx = WorkspaceContext(
            workspace_root=resolved_root,
            github_root=engine_github_root,
            engine_root=resolved_root,
        )
        super().__init__(synthetic_ctx)
        self.engine_manifest: dict[str, Any] = self._load_engine_manifest(resolved_root)

    def _load_engine_manifest(self, engine_root: Path) -> dict[str, Any]:
        """Load ``engine-manifest.json`` from the engine root.

        Returns an empty dict (with a logged warning) when the file is
        missing or unreadable, so the engine can still boot during the
        v2.x → v3.0 migration window.
        """
        manifest_path = engine_root / self.ENGINE_MANIFEST_FILENAME
        if not manifest_path.is_file():
            _log.warning(
                "engine-manifest.json non trovato in %s — fallback a manifest vuoto",
                engine_root,
            )
            return {}
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _log.warning(
                "Impossibile leggere engine-manifest.json (%s): %s",
                manifest_path, exc,
            )
            return {}
        if not isinstance(data, dict):
            _log.warning(
                "engine-manifest.json non è un oggetto JSON: %s",
                type(data).__name__,
            )
            return {}
        return data

    def get_engine_workspace_files(self) -> list[str]:
        """Return the list of engine-owned workspace files (Copilot-loaded)."""
        files = self.engine_manifest.get("workspace_files", [])
        return [str(f) for f in files] if isinstance(files, list) else []

    def get_engine_mcp_resources(self) -> dict[str, list[str]]:
        """Return the engine-owned MCP resource lists by type."""
        resources = self.engine_manifest.get("mcp_resources", {})
        if not isinstance(resources, dict):
            return {"agents": [], "instructions": [], "prompts": [], "skills": []}
        out: dict[str, list[str]] = {}
        for key in ("agents", "instructions", "prompts", "skills"):
            value = resources.get(key, [])
            out[key] = [str(v) for v in value] if isinstance(value, list) else []
        return out
