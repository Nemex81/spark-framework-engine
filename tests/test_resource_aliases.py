"""Tests for v3.0 resource handler refactor + alias retrocompatibili."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"
_ENGINE_DIR = _ENGINE_PATH.parent

for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]


class _StubMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}
        self.resources: dict[str, Any] = {}

    def tool(self):  # noqa: ANN201
        def deco(fn):  # noqa: ANN001
            self.tools[fn.__name__] = fn
            return fn

        return deco

    def resource(self, uri):  # noqa: ANN001, ANN201
        def deco(fn):  # noqa: ANN001
            self.resources[uri] = fn
            return fn

        return deco


def _build(tmp: Path):  # noqa: ANN202
    workspace = tmp / "ws"
    gh = workspace / ".github"
    (gh / "agents").mkdir(parents=True)
    (gh / "skills").mkdir(parents=True)
    (gh / "instructions").mkdir(parents=True)
    (gh / "prompts").mkdir(parents=True)
    (gh / "runtime").mkdir()
    (gh / "agents" / "Demo.agent.md").write_text("AGENT-Demo", encoding="utf-8")
    (gh / "skills" / "demo-skill.skill.md").write_text("SKILL-X", encoding="utf-8")
    (gh / "instructions" / "demo.instructions.md").write_text(
        "INSTR-X", encoding="utf-8"
    )
    (gh / "prompts" / "demo.prompt.md").write_text("PROMPT-X", encoding="utf-8")
    (gh / "runtime" / "orchestrator-state.json").write_text(
        json.dumps({"github_write_authorized": True}), encoding="utf-8"
    )

    WorkspaceContext = _module.WorkspaceContext
    FrameworkInventory = _module.FrameworkInventory
    SparkFrameworkEngine = _module.SparkFrameworkEngine
    McpResourceRegistry = _module.McpResourceRegistry

    ctx = WorkspaceContext(
        workspace_root=workspace, github_root=gh, engine_root=_ENGINE_DIR
    )
    inv = FrameworkInventory(ctx)
    registry = McpResourceRegistry()
    registry.register("agents://Demo", gh / "agents" / "Demo.agent.md", "p", "agents")
    registry.register(
        "skills://demo-skill", gh / "skills" / "demo-skill.skill.md", "p", "skills"
    )
    registry.register(
        "instructions://demo",
        gh / "instructions" / "demo.instructions.md",
        "p",
        "instructions",
    )
    registry.register(
        "prompts://demo", gh / "prompts" / "demo.prompt.md", "p", "prompts"
    )
    inv.mcp_registry = registry

    mcp = _StubMCP()
    eng = SparkFrameworkEngine(mcp, ctx, inv)
    eng.register_resources()
    eng.register_tools()
    return eng, mcp, gh


def _run(coro):  # noqa: ANN001
    return asyncio.get_event_loop().run_until_complete(coro)


class TestResourceHandlersRegistry(unittest.TestCase):
    def setUp(self) -> None:
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())

    def test_agent_handler_via_registry(self) -> None:
        with TemporaryDirectory() as tmp:
            _, mcp, _ = _build(Path(tmp))
            content = _run(mcp.resources["agents://{name}"]("Demo"))
            self.assertEqual(content, "AGENT-Demo")

    def test_skill_handler_via_registry(self) -> None:
        with TemporaryDirectory() as tmp:
            _, mcp, _ = _build(Path(tmp))
            content = _run(mcp.resources["skills://{name}"]("demo-skill"))
            self.assertEqual(content, "SKILL-X")

    def test_instruction_handler_via_registry(self) -> None:
        with TemporaryDirectory() as tmp:
            _, mcp, _ = _build(Path(tmp))
            content = _run(mcp.resources["instructions://{name}"]("demo"))
            self.assertEqual(content, "INSTR-X")

    def test_override_priority_via_handler(self) -> None:
        with TemporaryDirectory() as tmp:
            eng, mcp, gh = _build(Path(tmp))
            # Use override tool to install workspace override.
            res = _run(
                mcp.tools["scf_override_resource"](
                    "agents://Demo", "OVERRIDE-WINS"
                )
            )
            self.assertTrue(res["success"])
            content = _run(mcp.resources["agents://{name}"]("Demo"))
            self.assertEqual(content, "OVERRIDE-WINS")

    def test_alias_engine_skills(self) -> None:
        with TemporaryDirectory() as tmp:
            _, mcp, _ = _build(Path(tmp))
            content = _run(
                mcp.resources["engine-skills://{name}"]("demo-skill")
            )
            self.assertEqual(content, "SKILL-X")

    def test_alias_engine_instructions(self) -> None:
        with TemporaryDirectory() as tmp:
            _, mcp, _ = _build(Path(tmp))
            content = _run(
                mcp.resources["engine-instructions://{name}"]("demo")
            )
            self.assertEqual(content, "INSTR-X")

    def test_alias_warning_logged_once(self) -> None:
        with TemporaryDirectory() as tmp:
            eng, mcp, _ = _build(Path(tmp))
            with self.assertLogs(_module._log, level="WARNING") as cap:
                _run(mcp.resources["engine-skills://{name}"]("demo-skill"))
                _run(mcp.resources["engine-skills://{name}"]("demo-skill"))
            warns = [m for m in cap.output if "engine-skills://demo-skill" in m]
            self.assertEqual(len(warns), 1)
            # different name -> separate warning
            with self.assertLogs(_module._log, level="WARNING") as cap2:
                _run(mcp.resources["engine-skills://{name}"]("other"))
            warns2 = [m for m in cap2.output if "engine-skills://other" in m]
            self.assertEqual(len(warns2), 1)


if __name__ == "__main__":
    unittest.main()
