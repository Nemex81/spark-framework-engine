# Modulo workspace/migration — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""Migration helpers v2.x -> v3.0 (scf_migrate_workspace)."""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_log: logging.Logger = logging.getLogger("spark-framework-engine")


_V2_MIGRATION_KEEP_DIRS: tuple[str, ...] = (
    "instructions",
    "runtime",
)
_V2_MIGRATION_KEEP_FILES: tuple[str, ...] = (
    "copilot-instructions.md",
    "project-profile.md",
    ".scf-manifest.json",
    "AGENTS.md",  # legacy index, kept invariata in v3.0 baseline
)
_V2_MIGRATION_OVERRIDE_DIRS: tuple[str, ...] = (
    "agents",
    "prompts",
    "skills",
)
_V2_MIGRATION_DELETE_FILES: tuple[str, ...] = (
    ".scf-registry-cache.json",
)
_V2_MIGRATION_DELETE_PATTERNS: tuple[str, ...] = (
    "AGENTS-",  # AGENTS-{plugin}.md generated files
    "FRAMEWORK_CHANGELOG.md",
)


def _classify_v2_workspace_file(rel_path: Path) -> str:
    """Classify a workspace file under .github/ for migration to v3.0 schema.

    Args:
        rel_path: Path relative to the workspace `.github/` directory.

    Returns:
        One of: "keep", "move_to_override", "delete", "untouched".
    """
    parts = rel_path.parts
    if not parts:
        return "untouched"

    name = parts[-1]
    top = parts[0]

    if top in _V2_MIGRATION_KEEP_DIRS:
        return "keep"
    if name in _V2_MIGRATION_KEEP_FILES and len(parts) == 1:
        return "keep"

    if top in _V2_MIGRATION_OVERRIDE_DIRS:
        return "move_to_override"

    if name in _V2_MIGRATION_DELETE_FILES and len(parts) == 1:
        return "delete"
    for pattern in _V2_MIGRATION_DELETE_PATTERNS:
        if name.startswith(pattern):
            return "delete"

    return "untouched"


@dataclass(frozen=True)
class MigrationPlan:
    """Outcome of MigrationPlanner.analyze() — pure data, no side effects."""

    keep: tuple[str, ...]
    move_to_override: tuple[tuple[str, str], ...]
    delete: tuple[str, ...]
    untouched: tuple[str, ...]
    cache_relocate: tuple[str, str] | None  # (src_abs, dst_abs) or None

    def is_empty(self) -> bool:
        """Return True if the plan has no actions to execute."""
        return (
            not self.move_to_override
            and not self.delete
            and self.cache_relocate is None
        )

    def to_dict(self) -> dict[str, Any]:
        """Render the plan as a JSON-serialisable dict for tool responses."""
        return {
            "keep": list(self.keep),
            "move_to_override": [
                {"from": src, "to": dst} for src, dst in self.move_to_override
            ],
            "delete": list(self.delete),
            "untouched": list(self.untouched),
            "cache_relocate": (
                {"from": self.cache_relocate[0], "to": self.cache_relocate[1]}
                if self.cache_relocate is not None
                else None
            ),
        }


class MigrationPlanner:
    """Plan and execute v2.x -> v3.0 workspace migration with rollback support."""

    def __init__(self, workspace_root: Path, engine_cache_dir: Path | None = None) -> None:
        self._workspace_root = workspace_root
        self._github_root = workspace_root / ".github"
        self._engine_cache_dir = engine_cache_dir

    def analyze(self) -> MigrationPlan:
        """Scan the workspace and build a migration plan without writing anything."""
        if not self._github_root.is_dir():
            return MigrationPlan(
                keep=(),
                move_to_override=(),
                delete=(),
                untouched=(),
                cache_relocate=None,
            )

        keep: list[str] = []
        move: list[tuple[str, str]] = []
        delete: list[str] = []
        untouched: list[str] = []

        for entry in sorted(self._github_root.rglob("*")):
            if not entry.is_file():
                continue
            try:
                rel = entry.relative_to(self._github_root)
            except ValueError:
                continue
            # skip files already inside overrides/
            if rel.parts and rel.parts[0] == "overrides":
                untouched.append(str(rel.as_posix()))
                continue
            classification = _classify_v2_workspace_file(rel)
            rel_str = rel.as_posix()
            if classification == "keep":
                keep.append(rel_str)
            elif classification == "move_to_override":
                # map agents/X.agent.md -> overrides/agents/X.agent.md
                target = Path("overrides") / rel
                move.append((rel_str, target.as_posix()))
            elif classification == "delete":
                delete.append(rel_str)
            else:
                untouched.append(rel_str)

        cache_relocate = self._plan_cache_relocate()

        return MigrationPlan(
            keep=tuple(keep),
            move_to_override=tuple(move),
            delete=tuple(delete),
            untouched=tuple(untouched),
            cache_relocate=cache_relocate,
        )

    def _plan_cache_relocate(self) -> tuple[str, str] | None:
        """Plan the relocation of .scf-registry-cache.json into engine cache dir."""
        legacy = self._workspace_root / ".scf-registry-cache.json"
        if not legacy.is_file():
            return None
        if self._engine_cache_dir is None:
            return None
        target = self._engine_cache_dir / "registry-cache.json"
        return (str(legacy), str(target))

    def apply(self, plan: MigrationPlan) -> dict[str, Any]:
        """Execute the migration plan with backup-based rollback on error.

        Returns a dict with `executed`, `errors`, `rolled_back`, `backup_dir`.
        """
        if plan.is_empty():
            return {
                "executed": [],
                "errors": [],
                "rolled_back": False,
                "backup_dir": None,
            }

        backup_dir = self._create_backup()
        executed: list[str] = []
        errors: list[str] = []

        try:
            # 1. Move v2 files into overrides/
            for src_rel, dst_rel in plan.move_to_override:
                src = self._github_root / src_rel
                dst = self._github_root / dst_rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                src.replace(dst)
                executed.append(f"moved: {src_rel} -> {dst_rel}")

            # 2. Delete v2 generated files
            for rel in plan.delete:
                target = self._github_root / rel
                if target.is_file():
                    target.unlink()
                    executed.append(f"deleted: {rel}")

            # 3. Relocate registry cache (best effort)
            if plan.cache_relocate is not None:
                src_str, dst_str = plan.cache_relocate
                src = Path(src_str)
                dst = Path(dst_str)
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(src.read_bytes())
                    src.unlink()
                    executed.append(f"cache: {src_str} -> {dst_str}")
                except OSError as exc:
                    _log.warning(
                        "[SPARK-ENGINE][WARNING] cache relocate best-effort failed: %s",
                        exc,
                    )
                    errors.append(f"cache_relocate_failed: {exc}")

        except OSError as exc:
            _log.error(
                "[SPARK-ENGINE][ERROR] migration apply failed: %s; rolling back",
                exc,
            )
            errors.append(str(exc))
            self._rollback(backup_dir)
            return {
                "executed": executed,
                "errors": errors,
                "rolled_back": True,
                "backup_dir": str(backup_dir),
            }

        return {
            "executed": executed,
            "errors": errors,
            "rolled_back": False,
            "backup_dir": str(backup_dir),
        }

    def _create_backup(self) -> Path:
        """Create a timestamped backup of .github/ for rollback purposes."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup_dir = self._workspace_root / f".github.migrate-backup-{timestamp}"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(self._github_root, backup_dir)
        return backup_dir

    def _rollback(self, backup_dir: Path) -> None:
        """Restore .github/ from backup_dir after a failed apply."""
        if not backup_dir.is_dir():
            _log.error(
                "[SPARK-ENGINE][ERROR] rollback: backup dir missing %s",
                backup_dir,
            )
            return
        if self._github_root.exists():
            shutil.rmtree(self._github_root)
        shutil.copytree(backup_dir, self._github_root)
