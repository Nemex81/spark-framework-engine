"""Tests for v3.0 override tools (Phase 3)."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"
_ENGINE_DIR = _ENGINE_PATH.parent

# The fastmcp stub is initialized by conftest.py stub_mcp_modules at session start.
_fake_fastmcp = sys.modules["mcp.server.fastmcp"]


_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]


class _StubMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self):  # noqa: ANN201
        def deco(fn):  # noqa: ANN001
            self.tools[fn.__name__] = fn
            return fn

        return deco

    def resource(self, uri):  # noqa: ANN001, ANN201
        def deco(fn):  # noqa: ANN001
            return fn

        return deco


def _build_workspace(tmp: Path, *, authorized: bool = True) -> tuple[Any, _StubMCP]:
    workspace = tmp / "ws"
    gh = workspace / ".github"
    (gh / "agents").mkdir(parents=True)
    # Seed a minimal "engine" agent so the registry has at least one URI.
    (gh / "agents" / "Demo.agent.md").write_text("engine-content", encoding="utf-8")
    runtime = gh / "runtime"
    runtime.mkdir()
    (runtime / "orchestrator-state.json").write_text(
        json.dumps({"github_write_authorized": authorized}),
        encoding="utf-8",
    )
    WorkspaceContext = _module.WorkspaceContext
    FrameworkInventory = _module.FrameworkInventory
    SparkFrameworkEngine = _module.SparkFrameworkEngine
    McpResourceRegistry = _module.McpResourceRegistry

    ctx = WorkspaceContext(
        workspace_root=workspace,
        github_root=gh,
        engine_root=_ENGINE_DIR,
    )
    inv = FrameworkInventory(ctx)
    # Manually register a resource so override tools can act on it.
    registry = McpResourceRegistry()
    registry.register(
        "agents://Demo",
        gh / "agents" / "Demo.agent.md",
        "test-pkg",
        "agents",
    )
    inv.mcp_registry = registry
    inv.resource_store = _module.PackageResourceStore(_ENGINE_DIR)

    mcp = _StubMCP()
    engine = SparkFrameworkEngine(mcp, ctx, inv)
    engine.register_tools()
    return engine, mcp


def _run(coro):  # noqa: ANN001
    return asyncio.run(coro)


class TestOverrideTools(unittest.TestCase):
    def test_list_overrides_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            _, mcp = _build_workspace(Path(tmp))
            res = _run(mcp.tools["scf_list_overrides"]())
            self.assertEqual(res["count"], 0)
            self.assertEqual(res["items"], [])

    def test_list_overrides_invalid_type(self) -> None:
        with TemporaryDirectory() as tmp:
            _, mcp = _build_workspace(Path(tmp))
            res = _run(mcp.tools["scf_list_overrides"]("bogus"))
            self.assertFalse(res["success"])

    def test_read_resource_engine(self) -> None:
        with TemporaryDirectory() as tmp:
            _, mcp = _build_workspace(Path(tmp))
            res = _run(mcp.tools["scf_read_resource"]("agents://Demo"))
            self.assertTrue(res["success"])
            self.assertEqual(res["source"], "engine")
            self.assertIn("engine-content", res["content"])

    def test_read_resource_invalid_uri(self) -> None:
        with TemporaryDirectory() as tmp:
            _, mcp = _build_workspace(Path(tmp))
            res = _run(mcp.tools["scf_read_resource"]("bogus://X"))
            self.assertFalse(res["success"])

    def test_read_resource_override_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            _, mcp = _build_workspace(Path(tmp))
            res = _run(
                mcp.tools["scf_read_resource"]("agents://Demo", source="override")
            )
            self.assertFalse(res["success"])

    def test_override_cycle(self) -> None:
        with TemporaryDirectory() as tmp:
            _, mcp = _build_workspace(Path(tmp))
            # Create override
            res = _run(
                mcp.tools["scf_override_resource"](
                    "agents://Demo", "OVERRIDE-CONTENT"
                )
            )
            self.assertTrue(res["success"], res)
            override_path = Path(res["path"])
            self.assertTrue(override_path.is_file())
            self.assertEqual(
                override_path.read_text(encoding="utf-8"), "OVERRIDE-CONTENT"
            )
            # auto -> override
            res = _run(mcp.tools["scf_read_resource"]("agents://Demo"))
            self.assertEqual(res["source"], "override")
            self.assertEqual(res["content"], "OVERRIDE-CONTENT")
            # engine still readable
            res = _run(
                mcp.tools["scf_read_resource"]("agents://Demo", source="engine")
            )
            self.assertEqual(res["content"], "engine-content")
            # list
            res = _run(mcp.tools["scf_list_overrides"]())
            self.assertEqual(res["count"], 1)
            # filter
            res = _run(mcp.tools["scf_list_overrides"]("agents"))
            self.assertEqual(res["count"], 1)
            res = _run(mcp.tools["scf_list_overrides"]("prompts"))
            self.assertEqual(res["count"], 0)
            # drop
            res = _run(mcp.tools["scf_drop_override"]("agents://Demo"))
            self.assertTrue(res["success"])
            self.assertTrue(res["file_removed"])
            self.assertFalse(override_path.is_file())
            # auto back to engine
            res = _run(mcp.tools["scf_read_resource"]("agents://Demo"))
            self.assertEqual(res["source"], "engine")

    def test_override_unauthorized(self) -> None:
        with TemporaryDirectory() as tmp:
            _, mcp = _build_workspace(Path(tmp), authorized=False)
            res = _run(
                mcp.tools["scf_override_resource"]("agents://Demo", "X")
            )
            self.assertFalse(res["success"])
            self.assertTrue(res.get("authorization_required"))

    def test_override_unknown_uri(self) -> None:
        with TemporaryDirectory() as tmp:
            _, mcp = _build_workspace(Path(tmp))
            res = _run(
                mcp.tools["scf_override_resource"]("agents://Missing", "X")
            )
            self.assertFalse(res["success"])

    def test_drop_override_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            _, mcp = _build_workspace(Path(tmp))
            res = _run(mcp.tools["scf_drop_override"]("agents://Demo"))
            self.assertFalse(res["success"])


if __name__ == "__main__":
    unittest.main()
