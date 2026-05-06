"""Unit tests per FrameworkInventory.list_* con ResourceResolver integrato — Task A.4."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

_spec = importlib.util.spec_from_file_location("spark_framework_engine_a4", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine_a4"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

FrameworkInventory: Any = _module.FrameworkInventory
WorkspaceContext: Any = _module.WorkspaceContext
McpResourceRegistry: Any = _module.McpResourceRegistry
PackageResourceStore: Any = _module.PackageResourceStore


def _make_context(github_root: Path) -> Any:
    """Crea WorkspaceContext minimo per i test."""
    return WorkspaceContext(
        workspace_root=github_root.parent,
        github_root=github_root,
        engine_root=github_root.parent,
    )


def _populate_inventory(
    inv: Any, engine_dir: Path, pkg_id: str, resource_type: str, name: str, content: str
) -> None:
    """Popola mcp_registry e resource_store dell'inventario con una risorsa store."""
    subdir_map = {
        "agents": "agents",
        "skills": "skills",
        "instructions": "instructions",
        "prompts": "prompts",
    }
    suffix_map = {
        "agents": ".agent.md",
        "skills": ".skill.md",
        "instructions": ".instructions.md",
        "prompts": ".prompt.md",
    }
    subdir = subdir_map[resource_type]
    suffix = suffix_map[resource_type]
    pkg_dir = engine_dir / "packages" / pkg_id / ".github" / subdir
    pkg_dir.mkdir(parents=True)
    (pkg_dir / f"{name}{suffix}").write_text(content, encoding="utf-8")

    registry = McpResourceRegistry()
    store = PackageResourceStore(engine_dir)
    path = store.resolve(pkg_id, resource_type, name)
    assert path is not None, f"store.resolve({pkg_id!r}, {resource_type!r}, {name!r}) returned None"
    uri = McpResourceRegistry.make_uri(resource_type, name)
    registry.register(uri, path, pkg_id, resource_type)

    inv.mcp_registry = registry
    inv.resource_store = store


class TestFrameworkInventoryWithResolver(unittest.TestCase):
    """list_* con ResourceResolver popolato include risorse dallo store."""

    def test_list_agents_includes_store_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws_github = root / ".github"
            ws_github.mkdir()
            (ws_github / "agents").mkdir()
            inv = FrameworkInventory(_make_context(ws_github))
            _populate_inventory(inv, root / "engine", "pkg-x", "agents", "Agent-Store", "content")

            agents = inv.list_agents()
            names = [a.name for a in agents]
            self.assertIn("Agent-Store", names)

    def test_list_agents_fallback_when_no_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws_github = root / ".github"
            ws_agents = ws_github / "agents"
            ws_agents.mkdir(parents=True)
            # Usa .md (senza .agent intermedio) per compatibilità con path.stem nel fallback.
            (ws_agents / "Agent-Local.md").write_text("local", encoding="utf-8")
            inv = FrameworkInventory(_make_context(ws_github))
            # mcp_registry NON popolato → fallback filesystem

            agents = inv.list_agents()
            names = [a.name for a in agents]
            self.assertIn("Agent-Local", names)

    def test_list_agents_resolver_includes_workspace_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws_github = root / ".github"
            ws_agents = ws_github / "agents"
            ws_agents.mkdir(parents=True)
            (ws_agents / "Agent-WS.agent.md").write_text("ws agent", encoding="utf-8")
            inv = FrameworkInventory(_make_context(ws_github))
            _populate_inventory(inv, root / "engine", "pkg-y", "agents", "Agent-Store", "store agent")

            agents = inv.list_agents()
            names = [a.name for a in agents]
            self.assertIn("Agent-WS", names)
            self.assertIn("Agent-Store", names)

    def test_list_skills_includes_store_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws_github = root / ".github"
            ws_github.mkdir()
            inv = FrameworkInventory(_make_context(ws_github))
            _populate_inventory(inv, root / "engine", "pkg-z", "skills", "my-skill", "skill content")

            skills = inv.list_skills()
            names = [s.name for s in skills]
            self.assertIn("my-skill", names)

    def test_list_skills_fallback_when_no_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws_github = root / ".github"
            skills_dir = ws_github / "skills"
            skill_subdir = skills_dir / "local-skill"
            skill_subdir.mkdir(parents=True)
            (skill_subdir / "SKILL.md").write_text("skill", encoding="utf-8")
            inv = FrameworkInventory(_make_context(ws_github))
            # mcp_registry NON popolato → fallback filesystem

            skills = inv.list_skills()
            names = [s.name for s in skills]
            self.assertIn("local-skill", names)

    def test_list_instructions_includes_store_instruction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws_github = root / ".github"
            ws_github.mkdir()
            inv = FrameworkInventory(_make_context(ws_github))
            _populate_inventory(
                inv, root / "engine", "pkg-i", "instructions", "python", "python instructions"
            )

            instructions = inv.list_instructions()
            names = [i.name for i in instructions]
            self.assertIn("python", names)

    def test_list_prompts_includes_store_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws_github = root / ".github"
            ws_github.mkdir()
            inv = FrameworkInventory(_make_context(ws_github))
            _populate_inventory(
                inv, root / "engine", "pkg-p", "prompts", "git-commit", "commit prompt"
            )

            prompts = inv.list_prompts()
            names = [p.name for p in prompts]
            self.assertIn("git-commit", names)

    def test_list_agents_sorted(self) -> None:
        """list_agents restituisce risultati ordinati per nome."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws_github = root / ".github"
            ws_agents = ws_github / "agents"
            ws_agents.mkdir(parents=True)
            for name in ["ZAgent", "AAgent", "MAgent"]:
                (ws_agents / f"{name}.agent.md").write_text("x", encoding="utf-8")
            inv = FrameworkInventory(_make_context(ws_github))
            _populate_inventory(inv, root / "engine", "pkg-s", "agents", "BAgent", "b")

            agents = inv.list_agents()
            names = [a.name for a in agents]
            self.assertEqual(names, sorted(names))


if __name__ == "__main__":
    unittest.main()
