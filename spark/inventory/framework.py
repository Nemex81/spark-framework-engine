"""FrameworkInventory + build_workspace_info — SPARK Framework Engine.

Extracted to ``spark.inventory.framework`` during Phase 0 modular refactoring.
Re-exported from ``spark.inventory``.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, Mapping

from spark.core.constants import (
    _CHANGELOGS_SUBDIR,
    _RESOURCE_TYPES,
    ENGINE_VERSION,
)
from spark.core.models import FrameworkFile, WorkspaceContext
from spark.core.utils import parse_markdown_frontmatter
from spark.manifest import ManifestManager
from spark.registry import (
    McpResourceRegistry,
    PackageResourceStore,
    _resource_filename_candidates,
)

_log: logging.Logger = logging.getLogger("spark-framework-engine")


class FrameworkInventory:
    """Discover framework files under .github/ and scripts/ dynamically."""

    def __init__(self, context: WorkspaceContext) -> None:
        self._ctx = context
        # mcp_registry / resource_store sono popolati on-demand da
        # populate_mcp_registry(); rimangono None fino a quel momento per
        # mantenere il costo del costruttore minimo (compatibilità v2.x).
        self.mcp_registry: McpResourceRegistry | None = None
        self.resource_store: PackageResourceStore | None = None

    def populate_mcp_registry(
        self,
        engine_manifest: Mapping[str, Any] | None = None,
        package_manifests: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> "McpResourceRegistry":
        """Costruisce e popola ``self.mcp_registry`` con risorse engine + pacchetti.

        Parametri:
            engine_manifest: contenuto di ``engine-manifest.json`` (engine root).
            package_manifests: dict ``{package_id: manifest_dict}`` per i
                pacchetti i cui file vivono nel deposito centralizzato
                ``engine_dir/packages/{pkg}/.github/...``.

        Dopo aver registrato le risorse engine+pacchetti, esegue uno scan
        di ``workspace/.github/overrides/{type}/`` e applica gli override
        trovati al registry.
        """
        registry = McpResourceRegistry()
        store = PackageResourceStore(self._ctx.engine_root)
        self.mcp_registry = registry
        self.resource_store = store

        # 1) Risorse engine-proprie (engine-manifest.json)
        if engine_manifest:
            self._register_engine_resources(registry, engine_manifest)

        # 2) Risorse dei pacchetti (deposito centralizzato)
        if package_manifests:
            for package_id, manifest in package_manifests.items():
                self._register_package_resources(
                    registry, store, package_id, manifest
                )

        # 3) Override del workspace
        self._scan_workspace_overrides(registry)

        _log.info(
            "[SPARK-ENGINE][INFO] MCP registry populated: %d agents, %d prompts, %d instructions, %d skills",
            len(registry.list_by_type("agents")),
            len(registry.list_by_type("prompts")),
            len(registry.list_by_type("instructions")),
            len(registry.list_by_type("skills")),
        )
        return registry

    def _register_engine_resources(
        self,
        registry: "McpResourceRegistry",
        engine_manifest: Mapping[str, Any],
    ) -> None:
        engine_root = self._ctx.engine_root
        resources = engine_manifest.get("mcp_resources") or {}
        if not isinstance(resources, Mapping):
            return
        package_id = str(engine_manifest.get("package", "spark-framework-engine"))
        for resource_type in _RESOURCE_TYPES:
            names = resources.get(resource_type) or []
            if not isinstance(names, list):
                continue
            for name in names:
                path = self._find_engine_resource_path(
                    engine_root, resource_type, str(name)
                )
                if path is None:
                    continue
                uri = McpResourceRegistry.make_uri(resource_type, str(name))
                registry.register(uri, path, package_id, resource_type)

    def _find_engine_resource_path(
        self, engine_root: Path, resource_type: str, name: str
    ) -> Path | None:
        base = engine_root / ".github" / resource_type
        if not base.is_dir():
            return None
        for candidate in _resource_filename_candidates(resource_type, name):
            target = base / candidate
            if target.is_file():
                return target.resolve()
        return None

    def _register_package_resources(
        self,
        registry: "McpResourceRegistry",
        store: "PackageResourceStore",
        package_id: str,
        manifest: Mapping[str, Any],
    ) -> None:
        resources = manifest.get("mcp_resources") or {}
        if not isinstance(resources, Mapping):
            return
        for resource_type in _RESOURCE_TYPES:
            names = resources.get(resource_type) or []
            if not isinstance(names, list):
                continue
            for name in names:
                path = store.resolve(package_id, resource_type, str(name))
                if path is None:
                    continue
                uri = McpResourceRegistry.make_uri(resource_type, str(name))
                registry.register(uri, path, package_id, resource_type)

    def _scan_workspace_overrides(self, registry: "McpResourceRegistry") -> None:
        overrides_root = self._ctx.github_root / "overrides"
        if not overrides_root.is_dir():
            return
        for resource_type in _RESOURCE_TYPES:
            type_dir = overrides_root / resource_type
            if not type_dir.is_dir():
                continue
            for child in type_dir.iterdir():
                name = self._override_name_from_path(resource_type, child)
                if name is None:
                    continue
                uri = McpResourceRegistry.make_uri(resource_type, name)
                registry.register_override(uri, child)

    @staticmethod
    def _override_name_from_path(resource_type: str, path: Path) -> str | None:
        if resource_type == "agents":
            if path.is_file() and path.name.endswith(".agent.md"):
                return path.name[: -len(".agent.md")]
            if path.is_file() and path.name.endswith(".md"):
                return path.name[: -len(".md")]
            return None
        if resource_type == "prompts":
            if path.is_file() and path.name.endswith(".prompt.md"):
                return path.name[: -len(".prompt.md")]
            return None
        if resource_type == "instructions":
            if path.is_file() and path.name.endswith(".instructions.md"):
                return path.name[: -len(".instructions.md")]
            return None
        if resource_type == "skills":
            if path.is_file() and path.name.endswith(".skill.md"):
                return path.name[: -len(".skill.md")]
            if path.is_dir() and (path / "SKILL.md").is_file():
                return path.name
            return None
        return None

    def _build_framework_file(self, path: Path, category: str) -> FrameworkFile:
        name = path.stem
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            _log.warning("Cannot read %s: %s", path, exc)
            content = ""
        metadata = parse_markdown_frontmatter(content)
        summary = ""
        for raw in content.splitlines():
            stripped = raw.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                summary = stripped[:160]
                break
        return FrameworkFile(
            name=name, path=path, category=category, summary=summary, metadata=metadata
        )

    def _list_by_pattern(self, directory: Path, glob_pattern: str, category: str) -> list[FrameworkFile]:
        if not directory.is_dir():
            return []
        return sorted(
            [self._build_framework_file(p, category) for p in directory.glob(glob_pattern)],
            key=lambda ff: ff.name,
        )

    def list_agents(self) -> list[FrameworkFile]:
        return self._list_by_pattern(self._ctx.github_root / "agents", "*.md", "agent")

    def list_skills(self) -> list[FrameworkFile]:
        """Discover SCF skills in both supported formats.

        Format 1 (legacy): .github/skills/*.skill.md
        Format 2 (standard): .github/skills/skill-name/SKILL.md

        On name collisions, the legacy flat format takes precedence.
        """
        skills_root = self._ctx.github_root / "skills"

        # Pass 1: legacy flat format.
        flat = self._list_by_pattern(skills_root, "*.skill.md", "skill")
        seen: set[str] = {ff.name.removesuffix(".skill") for ff in flat}

        # Pass 2: standard Agent Skills format in subdirectories.
        standard: list[FrameworkFile] = []
        if skills_root.is_dir():
            for skill_dir in sorted(skills_root.iterdir()):
                skill_file = skill_dir / "SKILL.md"
                if skill_dir.is_dir() and skill_file.is_file():
                    ff = self._build_framework_file(skill_file, "skill")
                    named_ff = FrameworkFile(
                        name=skill_dir.name,
                        path=ff.path,
                        category=ff.category,
                        summary=ff.summary,
                        metadata=ff.metadata,
                    )
                    key = named_ff.name.removesuffix(".skill")
                    if key not in seen:
                        standard.append(named_ff)
                        seen.add(key)

        combined = flat + standard
        return sorted(combined, key=lambda ff: ff.name)

    def list_instructions(self) -> list[FrameworkFile]:
        return self._list_by_pattern(self._ctx.github_root / "instructions", "*.instructions.md", "instruction")

    def list_prompts(self) -> list[FrameworkFile]:
        """Return prompt files as read-only inventory. NOT registered as MCP Prompts.

        VS Code already exposes .github/prompts/*.prompt.md as native slash commands.
        Registering them as MCP Prompts would cause duplicate entries in the / picker.
        This behaviour is correct for VS Code. Alternative MCP clients (Claude Desktop,
        other IDEs) will see prompts only as generic text resources via prompts://list
        and prompts://{name}, not as native MCP Prompt artefacts. Known portability
        constraint of the v1 design.
        """
        return self._list_by_pattern(self._ctx.github_root / "prompts", "*.prompt.md", "prompt")

    def get_project_profile(self) -> FrameworkFile | None:
        path = self._ctx.github_root / "project-profile.md"
        return self._build_framework_file(path, "config") if path.is_file() else None

    def get_global_instructions(self) -> FrameworkFile | None:
        path = self._ctx.github_root / "copilot-instructions.md"
        return self._build_framework_file(path, "config") if path.is_file() else None

    def get_model_policy(self) -> FrameworkFile | None:
        path = self._ctx.github_root / "instructions" / "model-policy.instructions.md"
        return self._build_framework_file(path, "instruction") if path.is_file() else None

    def get_agents_index(self) -> FrameworkFile | None:
        path = self._ctx.github_root / "AGENTS.md"
        return self._build_framework_file(path, "index") if path.is_file() else None

    def get_package_changelog(self, package_id: str) -> str | None:
        """Return the changelog text for a package."""
        changelog_path = self._ctx.github_root / _CHANGELOGS_SUBDIR / f"{package_id}.md"
        try:
            if changelog_path.is_file():
                return changelog_path.read_text(encoding="utf-8")
        except OSError as exc:
            _log.warning("Cannot read package changelog %s: %s", changelog_path, exc)
        return None

    def list_agents_indexes(self) -> list[FrameworkFile]:
        """Return every AGENTS*.md index file found in the .github root."""
        if not self._ctx.github_root.is_dir():
            return []
        return sorted(
            [
                self._build_framework_file(path, "index")
                for path in self._ctx.github_root.glob("AGENTS*.md")
                if path.is_file()
            ],
            key=lambda framework_file: framework_file.name,
        )

    def get_orchestrator_state(self) -> dict[str, Any]:
        """Return orchestrator runtime state from .github/runtime/orchestrator-state.json."""
        state_path = self._ctx.github_root / "runtime" / "orchestrator-state.json"
        if not state_path.is_file():
            return {
                "current_phase": "",
                "current_agent": "",
                "retry_count": 0,
                "confidence": 1.0,
                "execution_mode": "autonomous",
                "last_updated": "",
                "phase_history": [],
                "active_task_id": "",
            }
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _log.warning("orchestrator-state.json unreadable: %s", exc)
            return {}

    def set_orchestrator_state(self, patch: dict[str, Any]) -> dict[str, Any]:
        """Update orchestrator runtime state with a partial merge and UTC timestamp."""
        state_path = self._ctx.github_root / "runtime" / "orchestrator-state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        current = self.get_orchestrator_state()
        current.update(patch)
        current["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        state_path.write_text(
            json.dumps(current, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return current


def build_workspace_info(context: WorkspaceContext, inventory: FrameworkInventory) -> dict[str, Any]:
    """Build a workspace info summary dict for the active context."""
    profile = inventory.get_project_profile()
    initialized: bool = bool(profile.metadata.get("initialized", False)) if profile else False
    manifest = ManifestManager(context.github_root)
    return {
        "workspace_root": str(context.workspace_root),
        "github_root": str(context.github_root),
        "initialized": initialized,
        "engine_version": ENGINE_VERSION,
        "installed_packages": manifest.get_installed_versions(),
        "agent_count": len(inventory.list_agents()),
        "skill_count": len(inventory.list_skills()),
        "instruction_count": len(inventory.list_instructions()),
        "prompt_count": len(inventory.list_prompts()),
    }
