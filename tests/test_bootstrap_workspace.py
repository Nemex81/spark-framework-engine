from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

FrameworkInventory = _module.FrameworkInventory
SparkFrameworkEngine = _module.SparkFrameworkEngine
WorkspaceContext = _module.WorkspaceContext


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self):
        def _decorator(func):
            self.tools[func.__name__] = func
            return func

        return _decorator

    def resource(self, *_args, **_kwargs):
        def _decorator(func):
            return func

        return _decorator


class TestBootstrapWorkspace(unittest.TestCase):
    def _build_engine(self, workspace_root: Path) -> tuple[object, object]:
        ctx = WorkspaceContext(
            workspace_root=workspace_root,
            github_root=workspace_root / ".github",
            engine_root=workspace_root / "spark-framework-engine",
        )
        inventory = FrameworkInventory(ctx)
        mcp = _FakeMCP()
        engine = SparkFrameworkEngine(mcp, ctx, inventory)
        engine.register_tools()
        return engine, mcp

    def test_bootstrap_copies_prompts_agent_and_guide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            _, mcp = self._build_engine(workspace_root)
            expected_copied_files = len(list((_ENGINE_PATH.parent / ".github" / "prompts").glob("scf-*.prompt.md"))) + 3

            result = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())

            self.assertTrue(result["success"])
            self.assertFalse(result["already_bootstrapped"])
            self.assertTrue((workspace_root / ".github" / "agents" / "spark-assistant.agent.md").is_file())
            self.assertTrue((workspace_root / ".github" / "agents" / "spark-guide.agent.md").is_file())
            self.assertTrue((workspace_root / ".github" / "instructions" / "spark-assistant-guide.instructions.md").is_file())
            self.assertEqual(len(result["files_copied"]), expected_copied_files)

    def test_bootstrap_repairs_missing_guide_when_agent_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            agent_path = workspace_root / ".github" / "agents" / "spark-assistant.agent.md"
            agent_path.parent.mkdir(parents=True, exist_ok=True)
            agent_path.write_text("existing agent", encoding="utf-8")

            _, mcp = self._build_engine(workspace_root)

            result = asyncio.run(mcp.tools["scf_bootstrap_workspace"]())

            self.assertTrue(result["success"])
            self.assertTrue(result["already_bootstrapped"])
            self.assertTrue((workspace_root / ".github" / "instructions" / "spark-assistant-guide.instructions.md").is_file())
            self.assertIn(".github/agents/spark-assistant.agent.md", result["files_skipped"])


if __name__ == "__main__":
    unittest.main()