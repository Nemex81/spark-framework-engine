"""Unit tests for McpResourceRegistry (Phase 2)."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

McpResourceRegistry = _module.McpResourceRegistry


class TestMcpResourceRegistry(unittest.TestCase):
    def test_make_uri(self) -> None:
        self.assertEqual(McpResourceRegistry.make_uri("agents", "X"), "agents://X")

    def test_register_and_resolve(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.md"
            p.write_text("x", encoding="utf-8")
            r = McpResourceRegistry()
            r.register("agents://X", p, "pkg", "agents")
            self.assertEqual(r.resolve("agents://X"), p.resolve())
            self.assertEqual(r.resolve_engine("agents://X"), p.resolve())
            self.assertFalse(r.has_override("agents://X"))

    def test_resolve_unknown(self) -> None:
        r = McpResourceRegistry()
        self.assertIsNone(r.resolve("agents://Missing"))
        self.assertIsNone(r.resolve_engine("agents://Missing"))

    def test_override_priority(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = Path(tmp) / "e.md"
            override = Path(tmp) / "o.md"
            engine.write_text("e", encoding="utf-8")
            override.write_text("o", encoding="utf-8")
            r = McpResourceRegistry()
            r.register("agents://X", engine, "pkg", "agents")
            r.register_override("agents://X", override)
            self.assertEqual(r.resolve("agents://X"), override.resolve())
            self.assertEqual(r.resolve_engine("agents://X"), engine.resolve())
            self.assertTrue(r.has_override("agents://X"))

    def test_register_override_orphan(self) -> None:
        """Override senza engine path (es. dopo rimozione pacchetto)."""
        with TemporaryDirectory() as tmp:
            override = Path(tmp) / "o.md"
            override.write_text("o", encoding="utf-8")
            r = McpResourceRegistry()
            r.register_override("agents://X", override)
            self.assertEqual(r.resolve("agents://X"), override.resolve())
            self.assertIsNone(r.resolve_engine("agents://X"))
            self.assertTrue(r.has_override("agents://X"))

    def test_drop_override(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = Path(tmp) / "e.md"
            override = Path(tmp) / "o.md"
            engine.write_text("e", encoding="utf-8")
            override.write_text("o", encoding="utf-8")
            r = McpResourceRegistry()
            r.register("agents://X", engine, "pkg", "agents")
            r.register_override("agents://X", override)
            self.assertTrue(r.drop_override("agents://X"))
            self.assertFalse(r.has_override("agents://X"))
            self.assertEqual(r.resolve("agents://X"), engine.resolve())
            # Drop su URI senza override -> False
            self.assertFalse(r.drop_override("agents://X"))
            self.assertFalse(r.drop_override("agents://Missing"))

    def test_list_by_type(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.md"
            p.write_text("x", encoding="utf-8")
            r = McpResourceRegistry()
            r.register("agents://A", p, "pkg", "agents")
            r.register("agents://B", p, "pkg", "agents")
            r.register("skills://S", p, "pkg", "skills")
            self.assertEqual(r.list_by_type("agents"), ["agents://A", "agents://B"])
            self.assertEqual(r.list_by_type("skills"), ["skills://S"])
            self.assertEqual(r.list_by_type("prompts"), [])

    def test_get_metadata(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.md"
            p.write_text("x", encoding="utf-8")
            r = McpResourceRegistry()
            r.register("agents://A", p, "pkg-x", "agents")
            md = r.get_metadata("agents://A")
            self.assertEqual(md["uri"], "agents://A")
            self.assertEqual(md["package"], "pkg-x")
            self.assertEqual(md["resource_type"], "agents")
            self.assertIsNone(md["override"])
            self.assertIsNone(r.get_metadata("agents://Missing"))


class TestFrameworkInventoryRegistryPopulation(unittest.TestCase):
    """Verifica integrazione boot: populate_mcp_registry con engine_manifest reale."""

    def test_populate_with_real_engine_manifest(self) -> None:
        FrameworkInventory = _module.FrameworkInventory
        EngineInventory = _module.EngineInventory
        WorkspaceContext = _module.WorkspaceContext

        engine_inv = EngineInventory()
        # Use engine root as workspace per il test (ha .github/agents)
        engine_root = Path(_module.__file__).parent
        ctx = WorkspaceContext(
            workspace_root=engine_root,
            github_root=engine_root / ".github",
            engine_root=engine_root,
        )
        inv = FrameworkInventory(ctx)
        registry = inv.populate_mcp_registry(
            engine_manifest=engine_inv.engine_manifest
        )

        all_uris = registry.list_all()
        self.assertTrue(any("spark-welcome" in u for u in all_uris))
        agent_uris = registry.list_by_type("agents")
        self.assertIn("agents://spark-welcome", agent_uris)
        # Engine path resolvibile
        path = registry.resolve("agents://spark-welcome")
        self.assertIsNotNone(path)
        self.assertTrue(path.is_file())

    def test_populate_with_empty_manifest(self) -> None:
        FrameworkInventory = _module.FrameworkInventory
        WorkspaceContext = _module.WorkspaceContext
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / ".github").mkdir()
            ctx = WorkspaceContext(
                workspace_root=tmp_path,
                github_root=tmp_path / ".github",
                engine_root=tmp_path,
            )
            inv = FrameworkInventory(ctx)
            registry = inv.populate_mcp_registry(engine_manifest={})
            self.assertEqual(registry.list_all(), [])

    def test_populate_with_workspace_overrides(self) -> None:
        FrameworkInventory = _module.FrameworkInventory
        WorkspaceContext = _module.WorkspaceContext
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            gh = tmp_path / ".github"
            (gh / "overrides" / "agents").mkdir(parents=True)
            override_file = gh / "overrides" / "agents" / "Agent-Custom.agent.md"
            override_file.write_text("custom", encoding="utf-8")
            ctx = WorkspaceContext(
                workspace_root=tmp_path,
                github_root=gh,
                engine_root=tmp_path,
            )
            inv = FrameworkInventory(ctx)
            registry = inv.populate_mcp_registry(engine_manifest={})
            self.assertTrue(registry.has_override("agents://Agent-Custom"))
            self.assertEqual(
                registry.resolve("agents://Agent-Custom"),
                override_file.resolve(),
            )


if __name__ == "__main__":
    unittest.main()
