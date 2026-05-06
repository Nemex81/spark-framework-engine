"""Unit tests for C.1 — source_divergence field in scf_verify_workspace."""
from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Coroutine, cast
from unittest.mock import MagicMock, patch

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

FrameworkInventory = _module.FrameworkInventory
ManifestManager = _module.ManifestManager
SparkFrameworkEngine = _module.SparkFrameworkEngine
WorkspaceContext = _module.WorkspaceContext


class FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Coroutine[Any, Any, dict[str, Any]]]] = {}

    def tool(
        self,
    ) -> Callable[
        [Callable[..., Coroutine[Any, Any, dict[str, Any]]]],
        Callable[..., Coroutine[Any, Any, dict[str, Any]]],
    ]:
        def decorator(
            func: Callable[..., Coroutine[Any, Any, dict[str, Any]]],
        ) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
            self.tools[func.__name__] = func
            return func

        return decorator


def _make_context(workspace_root: Path) -> Any:
    return WorkspaceContext(
        workspace_root=workspace_root,
        github_root=workspace_root / ".github",
        engine_root=Path(__file__).parent.parent,
    )


def _setup_engine(workspace_root: Path) -> tuple[Any, Any]:
    """Build and register a bare SparkFrameworkEngine for the given workspace."""
    (workspace_root / ".github").mkdir(parents=True, exist_ok=True)
    context = _make_context(workspace_root)
    inventory = FrameworkInventory(context)
    fake_mcp = FakeMCP()
    engine = SparkFrameworkEngine(fake_mcp, context, inventory)
    engine.register_tools()
    return engine, fake_mcp


async def _call_verify(fake_mcp: Any) -> dict[str, Any]:
    verify_fn = cast(
        Callable[[], Coroutine[Any, Any, dict[str, Any]]],
        fake_mcp.tools["scf_verify_workspace"],
    )
    return await verify_fn()


class TestVerifyWorkspaceDivergenceField(unittest.TestCase):
    """C.1: scf_verify_workspace always includes source_divergence field."""

    def test_source_divergence_field_always_present(self) -> None:
        """source_divergence key must be present in the return dict."""
        with tempfile.TemporaryDirectory() as tmp:
            _, fake_mcp = _setup_engine(Path(tmp))
            result = asyncio.run(_call_verify(fake_mcp))
        self.assertIn("source_divergence", result)

    def test_source_divergence_structure(self) -> None:
        """source_divergence must have the three expected sub-keys."""
        with tempfile.TemporaryDirectory() as tmp:
            _, fake_mcp = _setup_engine(Path(tmp))
            result = asyncio.run(_call_verify(fake_mcp))
        sd = result["source_divergence"]
        self.assertIn("only_in_store", sd)
        self.assertIn("only_in_workspace", sd)
        self.assertIn("divergent_content", sd)

    def test_source_divergence_empty_when_no_resolver(self) -> None:
        """When no registry/store is available, lists are empty and no error key."""
        with tempfile.TemporaryDirectory() as tmp:
            _, fake_mcp = _setup_engine(Path(tmp))
            result = asyncio.run(_call_verify(fake_mcp))
        sd = result["source_divergence"]
        self.assertEqual(sd["only_in_store"], [])
        self.assertEqual(sd["only_in_workspace"], [])
        self.assertEqual(sd["divergent_content"], [])
        self.assertNotIn("error", sd)

    def test_source_divergence_error_key_on_resolver_exception(self) -> None:
        """When _build_resolver raises, error key is set and lists are empty."""
        with tempfile.TemporaryDirectory() as tmp:
            _, fake_mcp = _setup_engine(Path(tmp))
            # Patch inventory._build_resolver to raise
            tools_module = sys.modules.get("spark_framework_engine")
            inventory_ref = None
            # Locate the inventory inside the engine (captured in register_tools closure).
            # We patch FrameworkInventory._build_resolver globally for this call.
            original_build = FrameworkInventory._build_resolver
            try:
                FrameworkInventory._build_resolver = lambda self: (_ for _ in ()).throw(  # type: ignore[assignment]
                    RuntimeError("forced resolver error")
                )
                result = asyncio.run(_call_verify(fake_mcp))
            finally:
                FrameworkInventory._build_resolver = original_build

        sd = result["source_divergence"]
        self.assertIn("error", sd)
        self.assertIn("forced resolver error", sd["error"])

    def test_original_summary_fields_still_present(self) -> None:
        """Existing summary fields must remain unaffected after C.1 change."""
        with tempfile.TemporaryDirectory() as tmp:
            _, fake_mcp = _setup_engine(Path(tmp))
            result = asyncio.run(_call_verify(fake_mcp))
        self.assertIn("summary", result)
        self.assertIn("is_clean", result["summary"])
        self.assertIn("issue_count", result["summary"])

    def test_source_divergence_workspace_resource_classified_as_only_in_workspace(
        self,
    ) -> None:
        """A resource present in workspace but not in store → only_in_workspace."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            gh = ws / ".github"
            agents_dir = gh / "agents"
            agents_dir.mkdir(parents=True)
            (agents_dir / "my-agent.agent.md").write_text(
                "---\nspark: true\n---\n# My Agent\n", encoding="utf-8"
            )
            _, fake_mcp = _setup_engine(ws)

            # Provide a resolver stub that returns ("my-agent", path, "workspace") for agents
            fake_path = agents_dir / "my-agent.agent.md"
            original_build = FrameworkInventory._build_resolver

            class _FakeResolver:
                def enumerate_merged(self, resource_type: str) -> list[tuple[str, Any, str]]:
                    if resource_type == "agents":
                        return [("my-agent", fake_path, "workspace")]
                    return []

            try:
                FrameworkInventory._build_resolver = lambda self: _FakeResolver()  # type: ignore[assignment]
                result = asyncio.run(_call_verify(fake_mcp))
            finally:
                FrameworkInventory._build_resolver = original_build

        sd = result["source_divergence"]
        self.assertEqual(len(sd["only_in_workspace"]), 1)
        self.assertEqual(sd["only_in_workspace"][0]["name"], "my-agent")
        self.assertEqual(sd["only_in_workspace"][0]["resource_type"], "agents")
        self.assertEqual(sd["only_in_store"], [])

    def test_source_divergence_store_resource_classified_as_only_in_store(
        self,
    ) -> None:
        """A resource present only in store → only_in_store."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / ".github").mkdir(parents=True)
            _, fake_mcp = _setup_engine(ws)

            class _FakeResolver:
                def enumerate_merged(self, resource_type: str) -> list[tuple[str, Any, str]]:
                    if resource_type == "agents":
                        return [("store-agent", Path("/fake/store-agent.agent.md"), "store")]
                    return []

            original_build = FrameworkInventory._build_resolver
            try:
                FrameworkInventory._build_resolver = lambda self: _FakeResolver()  # type: ignore[assignment]
                result = asyncio.run(_call_verify(fake_mcp))
            finally:
                FrameworkInventory._build_resolver = original_build

        sd = result["source_divergence"]
        self.assertEqual(len(sd["only_in_store"]), 1)
        self.assertEqual(sd["only_in_store"][0]["name"], "store-agent")
        self.assertEqual(sd["only_in_workspace"], [])


if __name__ == "__main__":
    unittest.main()
