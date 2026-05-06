"""Unit tests for ResourceResolver — cascata priorità override > workspace > store."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

McpResourceRegistry: Any = _module.McpResourceRegistry
PackageResourceStore: Any = _module.PackageResourceStore
ResourceResolver: Any = _module.ResourceResolver


def _make_registry_with_store(
    tmp: Path,
    pkg_id: str = "pkg-test",
    agent_name: str = "Agent-Test",
    agent_content: str = "store agent content",
) -> tuple[Any, Any, Path]:
    """Crea un registry con uno store popolato. Ritorna (registry, store, engine_dir)."""
    engine_dir = tmp / "engine"
    pkg_github = engine_dir / "packages" / pkg_id / ".github" / "agents"
    pkg_github.mkdir(parents=True)
    agent_file = pkg_github / f"{agent_name}.agent.md"
    agent_file.write_text(agent_content, encoding="utf-8")

    registry = McpResourceRegistry()
    store = PackageResourceStore(engine_dir)
    path = store.resolve(pkg_id, "agents", agent_name)
    assert path is not None
    uri = McpResourceRegistry.make_uri("agents", agent_name)
    registry.register(uri, path, pkg_id, "agents")
    return registry, store, engine_dir


class TestResourceResolverResolve(unittest.TestCase):
    """Test metodo resolve() con la cascata priorità."""

    def test_resolve_returns_store_path_when_only_store_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, store, engine_dir = _make_registry_with_store(root)
            ws_github = root / "workspace" / ".github"
            ws_github.mkdir(parents=True)

            resolver = ResourceResolver(registry, store, ws_github)
            result = resolver.resolve("agents", "Agent-Test")

            self.assertIsNotNone(result)
            self.assertTrue(result.is_file())
            self.assertIn("Agent-Test", result.name)

    def test_workspace_physical_wins_over_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, store, engine_dir = _make_registry_with_store(root)
            ws_github = root / "workspace" / ".github"
            ws_agents = ws_github / "agents"
            ws_agents.mkdir(parents=True)
            ws_agent = ws_agents / "Agent-Test.agent.md"
            ws_agent.write_text("workspace agent content", encoding="utf-8")

            resolver = ResourceResolver(registry, store, ws_github)
            result = resolver.resolve("agents", "Agent-Test")

            self.assertIsNotNone(result)
            self.assertEqual(result, ws_agent.resolve())

    def test_override_wins_over_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, store, engine_dir = _make_registry_with_store(root)

            # Workspace fisico
            ws_github = root / "workspace" / ".github"
            ws_agents = ws_github / "agents"
            ws_agents.mkdir(parents=True)
            ws_agent = ws_agents / "Agent-Test.agent.md"
            ws_agent.write_text("workspace content", encoding="utf-8")

            # Override
            override_dir = ws_github / "overrides" / "agents"
            override_dir.mkdir(parents=True)
            override_file = override_dir / "Agent-Test.agent.md"
            override_file.write_text("override content", encoding="utf-8")
            uri = McpResourceRegistry.make_uri("agents", "Agent-Test")
            registry.register_override(uri, override_file)

            resolver = ResourceResolver(registry, store, ws_github)
            result = resolver.resolve("agents", "Agent-Test")

            self.assertIsNotNone(result)
            self.assertEqual(result, override_file.resolve())

    def test_resolve_returns_none_when_nothing_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws_github = root / "workspace" / ".github"
            ws_github.mkdir(parents=True)
            registry = McpResourceRegistry()
            store = PackageResourceStore(root / "engine")

            resolver = ResourceResolver(registry, store, ws_github)
            result = resolver.resolve("agents", "NonExistent")

            self.assertIsNone(result)

    def test_resolve_skill_subdirectory_format(self) -> None:
        """Skills in formato subdirectory vengono trovate nel workspace fisico."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws_github = root / ".github"
            skill_dir = ws_github / "skills" / "my-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("skill content", encoding="utf-8")

            registry = McpResourceRegistry()
            store = PackageResourceStore(root / "engine")

            resolver = ResourceResolver(registry, store, ws_github)
            result = resolver.resolve("skills", "my-skill")

            self.assertIsNotNone(result)
            self.assertTrue(result.is_file())


class TestResourceResolverEnumerateMerged(unittest.TestCase):
    """Test metodo enumerate_merged() con deduplicazione."""

    def test_deduplication_workspace_wins_over_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, store, engine_dir = _make_registry_with_store(root)

            # Stessa risorsa nel workspace fisico
            ws_github = root / "workspace" / ".github"
            ws_agents = ws_github / "agents"
            ws_agents.mkdir(parents=True)
            (ws_agents / "Agent-Test.agent.md").write_text("ws", encoding="utf-8")

            resolver = ResourceResolver(registry, store, ws_github)
            merged = resolver.enumerate_merged("agents")

            # Una sola voce con source=workspace
            names = [name for name, _, _ in merged]
            self.assertIn("Agent-Test", names)
            sources = {name: src for name, _, src in merged}
            self.assertEqual(sources["Agent-Test"], "workspace")

    def test_resource_only_in_store_appears_as_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, store, engine_dir = _make_registry_with_store(root)
            ws_github = root / "workspace" / ".github"
            ws_github.mkdir(parents=True)

            resolver = ResourceResolver(registry, store, ws_github)
            merged = resolver.enumerate_merged("agents")

            sources = {name: src for name, _, src in merged}
            self.assertIn("Agent-Test", sources)
            self.assertEqual(sources["Agent-Test"], "store")

    def test_resource_only_in_workspace_appears_as_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws_github = root / ".github"
            ws_agents = ws_github / "agents"
            ws_agents.mkdir(parents=True)
            (ws_agents / "Agent-WsOnly.agent.md").write_text("x", encoding="utf-8")

            registry = McpResourceRegistry()
            store = PackageResourceStore(root / "engine")

            resolver = ResourceResolver(registry, store, ws_github)
            merged = resolver.enumerate_merged("agents")

            sources = {name: src for name, _, src in merged}
            self.assertIn("Agent-WsOnly", sources)
            self.assertEqual(sources["Agent-WsOnly"], "workspace")

    def test_override_source_wins_in_merged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, store, engine_dir = _make_registry_with_store(root)

            ws_github = root / "workspace" / ".github"
            override_dir = ws_github / "overrides" / "agents"
            override_dir.mkdir(parents=True)
            override_file = override_dir / "Agent-Test.agent.md"
            override_file.write_text("override", encoding="utf-8")
            uri = McpResourceRegistry.make_uri("agents", "Agent-Test")
            registry.register_override(uri, override_file)

            resolver = ResourceResolver(registry, store, ws_github)
            merged = resolver.enumerate_merged("agents")

            sources = {name: src for name, _, src in merged}
            self.assertEqual(sources["Agent-Test"], "override")

    def test_enumerate_merged_returns_sorted_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws_github = root / ".github"
            ws_agents = ws_github / "agents"
            ws_agents.mkdir(parents=True)
            (ws_agents / "ZAgent.agent.md").write_text("z", encoding="utf-8")
            (ws_agents / "AAgent.agent.md").write_text("a", encoding="utf-8")
            (ws_agents / "MAgent.agent.md").write_text("m", encoding="utf-8")

            registry = McpResourceRegistry()
            store = PackageResourceStore(root / "engine")

            resolver = ResourceResolver(registry, store, ws_github)
            merged = resolver.enumerate_merged("agents")
            names = [name for name, _, _ in merged]

            self.assertEqual(names, sorted(names))

    def test_enumerate_merged_empty_when_nothing_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws_github = root / ".github"
            ws_github.mkdir(parents=True)
            registry = McpResourceRegistry()
            store = PackageResourceStore(root / "engine")

            resolver = ResourceResolver(registry, store, ws_github)
            merged = resolver.enumerate_merged("agents")

            self.assertEqual(merged, [])


if __name__ == "__main__":
    unittest.main()
