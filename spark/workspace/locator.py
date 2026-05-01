"""WorkspaceLocator — SPARK Framework Engine.

Extracted to ``spark.workspace.locator`` during Phase 0 modular refactoring.
Re-exported from ``spark.workspace``.

Surgical change vs. original hub:
- Added ``__init__(self, engine_root: Path)`` that stores ``engine_root``
  as ``self._engine_root``.
- ``resolve()`` now uses ``self._engine_root`` instead of
  ``Path(__file__).resolve().parent`` so the class is file-location-agnostic.
- Callers in the hub and ``_build_app`` must pass
  ``WorkspaceLocator(engine_root=Path(__file__).resolve().parent)``.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import ClassVar

from spark.core.models import WorkspaceContext

_log: logging.Logger = logging.getLogger("spark-framework-engine")


class WorkspaceLocator:
    """Resolve the active workspace using env, local config and SCF markers."""

    OVERRIDE_RESOURCE_TYPES: ClassVar[tuple[str, ...]] = (
        "agents",
        "prompts",
        "skills",
        "instructions",
    )

    def __init__(self, engine_root: Path | None = None) -> None:
        """Store the engine root so that ``resolve()`` is file-location-agnostic.

        Args:
            engine_root: Absolute path to the directory containing
                ``spark-framework-engine.py`` (the engine root).
                Callers should pass ``Path(__file__).resolve().parent``.
                When ``None`` (e.g. in unit tests), falls back to
                ``Path.cwd()`` at resolve time.
        """
        self._engine_root: Path | None = engine_root

    @staticmethod
    def get_engine_cache_dir(engine_dir: Path) -> Path:
        """Return a writable cache directory for the engine.

        Prefer ``engine_dir/cache/``; fall back to a per-user location
        (``%APPDATA%\\spark-engine\\cache`` on Windows, ``~/.cache/spark-engine``
        otherwise) when the engine directory is not writable.
        Creates the directory if missing.
        """
        primary = engine_dir / "cache"
        try:
            primary.mkdir(parents=True, exist_ok=True)
            probe = primary / ".write-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return primary
        except OSError:
            _log.warning(
                "Engine cache dir not writable (%s); using per-user fallback",
                primary,
            )

        if os.name == "nt":
            base_str = os.environ.get("APPDATA") or os.path.expanduser("~")
            fallback = Path(base_str) / "spark-engine" / "cache"
        else:
            fallback = Path(os.path.expanduser("~/.cache/spark-engine"))

        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    @staticmethod
    def get_override_dir(
        workspace: Path,
        resource_type: str,
        github_write_authorized: bool = True,
    ) -> Path:
        """Return ``workspace/.github/overrides/{resource_type}/``.

        Creates the directory only when ``github_write_authorized`` is True.
        Raises ValueError on unknown resource types.
        """
        if resource_type not in WorkspaceLocator.OVERRIDE_RESOURCE_TYPES:
            raise ValueError(
                f"Unknown override resource type: {resource_type!r}"
            )
        target = workspace / ".github" / "overrides" / resource_type
        if github_write_authorized:
            target.mkdir(parents=True, exist_ok=True)
        return target

    @staticmethod
    def _parse_workspace_flag(argv: list[str] | None = None) -> str | None:
        """Return the value of ``--workspace`` from argv if present.

        Accepts ``--workspace VALUE`` or ``--workspace=VALUE``.
        """
        args = list(sys.argv[1:] if argv is None else argv)
        i = 0
        while i < len(args):
            token = args[i]
            if token == "--workspace":
                if i + 1 < len(args):
                    return args[i + 1]
                return None
            if token.startswith("--workspace="):
                return token.split("=", 1)[1]
            i += 1
        return None

    _SCF_MARKER_FILES: tuple[str, ...] = (
        "project-profile.md",
        "copilot-instructions.md",
        "AGENTS.md",
        ".scf-manifest.json",
    )
    _SCF_MARKER_DIRS: tuple[str, ...] = (
        "agents",
        "instructions",
        "prompts",
        "skills",
    )

    def _is_user_home(self, candidate: Path) -> bool:
        try:
            return candidate == Path.home().resolve()
        except RuntimeError:
            return False

    def _has_local_workspace_config(self, candidate: Path) -> bool:
        if any(path.is_file() for path in candidate.glob("*.code-workspace")):
            return True

        vscode_dir = candidate / ".vscode"
        return any(
            (vscode_dir / file_name).is_file()
            for file_name in ("settings.json", "mcp.json")
        )

    def _has_scf_markers(self, candidate: Path) -> bool:
        github_root = candidate / ".github"
        if not github_root.is_dir():
            return False

        if any((github_root / file_name).is_file() for file_name in self._SCF_MARKER_FILES):
            return True

        return any((github_root / dir_name).is_dir() for dir_name in self._SCF_MARKER_DIRS)

    def _discover_from_cwd(self, cwd: Path) -> Path | None:
        for candidate in (cwd, *cwd.parents):
            if self._is_user_home(candidate):
                continue

            if self._has_local_workspace_config(candidate):
                _log.info("Workspace resolved via local workspace config: %s", candidate)
                return candidate

            if self._has_scf_markers(candidate):
                _log.info("Workspace resolved via SCF .github discovery: %s", candidate)
                return candidate

        return None

    def resolve(self) -> WorkspaceContext:
        workspace_root: Path | None = None

        # 2. ENGINE_WORKSPACE env var (optional)
        if workspace_root is None:
            engine_workspace = os.environ.get("ENGINE_WORKSPACE")
            if engine_workspace:
                candidate = Path(engine_workspace).expanduser().resolve()
                if candidate.is_dir():
                    workspace_root = candidate
                    _log.info("Workspace resolved via ENGINE_WORKSPACE: %s", workspace_root)

        # 3. WORKSPACE_FOLDER as alias (retrocompatibilità, non prioritaria)
        if workspace_root is None:
            workspace_folder = os.environ.get("WORKSPACE_FOLDER")
            if workspace_folder:
                candidate = Path(workspace_folder).expanduser().resolve()
                if candidate.is_dir():
                    workspace_root = candidate
                    _log.info("Workspace resolved via WORKSPACE_FOLDER: %s", workspace_root)

        # 4. Fallback: current working directory
        if workspace_root is None:
            cwd = Path.cwd().resolve()
            workspace_root = self._discover_from_cwd(cwd)
            if workspace_root is None:
                workspace_root = cwd
                _log.warning("No workspace root available from MCP Roots, ENGINE_WORKSPACE or WORKSPACE_FOLDER.")
                _log.warning("Falling back to cwd: %s", workspace_root)

        if workspace_root is None or not workspace_root.is_dir():
            _log.warning("[SPARK-ENGINE][WARNING] No workspace root available")
            workspace_root = None

        github_root = workspace_root / ".github" if workspace_root else None
        # engine_root è sempre la directory del file engine, indipendente dal workspace.
        # Valore passato esplicitamente dal chiamante (nessun Path(__file__) qui).
        # Fallback a Path.cwd() per contesti di test dove engine_root non è rilevante.
        engine_root: Path = self._engine_root if self._engine_root is not None else Path.cwd()

        # Guardia esplicita: github_root e' None se workspace_root non e' stato risolto.
        if github_root is None:
            _log.warning(
                "[SPARK-ENGINE][WARNING] .github/ non disponibile: "
                "workspace root non risolto. Server avviato in modalita' degradata."
            )
        elif not github_root.is_dir():
            _log.warning(".github/ not found in workspace: %s", github_root)

        return WorkspaceContext(
            workspace_root=workspace_root,
            github_root=github_root,
            engine_root=engine_root,
        )
