"""Test AP.1 — scf_get_agent source_warning per agenti workspace-only vs store.

Verifica che scf_get_agent() aggiunga il campo 'source_warning' quando
l'agente è trovato nel workspace fisico (.github/agents/) ma non è registrato
nel McpResourceRegistry (che è la sorgente usata da scf_get_agent_resource).

La divergenza silenziosa AP.1: un agente solo nel workspace fisico è trovato
da scf_get_agent (via inventory.list_agents() con resolver) ma non da
scf_get_agent_resource (via reg.resolve(uri) che usa solo il registry).
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from typing import Any

from spark.boot.tools_resources import register_resource_tools
from spark.core.models import FrameworkFile, WorkspaceContext
from spark.inventory.framework import FrameworkInventory
from spark.registry.mcp import McpResourceRegistry
from spark.registry.store import PackageResourceStore


def _make_context(github_root: Path, engine_root: Path) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_root=github_root.parent,
        github_root=github_root,
        engine_root=engine_root,
    )


class _MockMcp:
    """Mock minimo di FastMCP per catturare le closure dei tool."""

    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}

    def tool(self) -> Any:
        def decorator(fn: Any) -> Any:
            self._tools[fn.__name__] = fn
            return fn
        return decorator


def _register_store_agent(
    inv: FrameworkInventory,
    engine_dir: Path,
    pkg_id: str,
    name: str,
    content: str,
) -> None:
    """Installa un agente nello store e popola registry + resource_store dell'inventario."""
    pkg_agents_dir = engine_dir / "packages" / pkg_id / ".github" / "agents"
    pkg_agents_dir.mkdir(parents=True, exist_ok=True)
    (pkg_agents_dir / f"{name}.agent.md").write_text(content, encoding="utf-8")

    registry = McpResourceRegistry() if inv.mcp_registry is None else inv.mcp_registry
    store = PackageResourceStore(engine_dir) if inv.resource_store is None else inv.resource_store
    path = store.resolve(pkg_id, "agents", name)
    assert path is not None, f"store.resolve({pkg_id!r}, 'agents', {name!r}) returned None"
    uri = McpResourceRegistry.make_uri("agents", name)
    registry.register(uri, path, pkg_id, "agents")

    inv.mcp_registry = registry
    inv.resource_store = store


class TestScfGetAgentSourceWarning(unittest.TestCase):
    """AP.1 — scf_get_agent source_warning per agenti workspace-only."""

    def _build_tools(
        self, inv: FrameworkInventory, engine_root: Path
    ) -> dict[str, Any]:
        """Registra i tool risorse e restituisce il dizionario closure per nome."""
        mock_mcp = _MockMcp()
        tool_names: list[str] = []
        register_resource_tools(inv, engine_root, mock_mcp, tool_names)
        return mock_mcp._tools

    def test_source_warning_present_for_workspace_only_agent(self) -> None:
        """scf_get_agent aggiunge source_warning quando l'agente è solo nel workspace fisico."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws_github = root / ".github"
            ws_agents = ws_github / "agents"
            ws_agents.mkdir(parents=True)

            # Agente presente solo nel workspace fisico (non nello store/registry).
            (ws_agents / "Agent-WS.agent.md").write_text("# Agent WS\n", encoding="utf-8")

            engine_root = root / "engine"
            engine_root.mkdir()
            inv = FrameworkInventory(_make_context(ws_github, engine_root))

            # Popola registry con un agente di store DIVERSO (non Agent-WS)
            # così il registry esiste ma non contiene Agent-WS.
            _register_store_agent(inv, engine_root, "pkg-base", "Agent-Store", "store content")

            tools = self._build_tools(inv, engine_root)
            scf_get_agent = tools["scf_get_agent"]

            result = asyncio.run(scf_get_agent("Agent-WS"))

            self.assertIn("content", result, "scf_get_agent deve restituire content per Agent-WS")
            self.assertIn(
                "source_warning",
                result,
                "AP.1: scf_get_agent deve aggiungere source_warning per agente workspace-only",
            )
            self.assertIn(
                "not in store",
                result["source_warning"],
                "source_warning deve menzionare 'not in store'",
            )

    def test_no_source_warning_for_store_agent(self) -> None:
        """scf_get_agent NON aggiunge source_warning quando l'agente è nel store/registry."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws_github = root / ".github"
            (ws_github / "agents").mkdir(parents=True)

            engine_root = root / "engine"
            engine_root.mkdir()
            inv = FrameworkInventory(_make_context(ws_github, engine_root))

            # Agente presente solo nello store.
            _register_store_agent(inv, engine_root, "pkg-base", "Agent-Git", "# Agent Git\n")

            tools = self._build_tools(inv, engine_root)
            scf_get_agent = tools["scf_get_agent"]

            result = asyncio.run(scf_get_agent("Agent-Git"))

            self.assertIn("content", result, "scf_get_agent deve restituire content per Agent-Git")
            self.assertNotIn(
                "source_warning",
                result,
                "AP.1: scf_get_agent NON deve aggiungere source_warning per agente nel store",
            )

    def test_not_found_returns_error(self) -> None:
        """scf_get_agent restituisce errore strutturato per agente inesistente."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws_github = root / ".github"
            (ws_github / "agents").mkdir(parents=True)

            engine_root = root / "engine"
            engine_root.mkdir()
            inv = FrameworkInventory(_make_context(ws_github, engine_root))
            # Registry vuoto (nessuno store agent, nessun ws agent).
            inv.mcp_registry = McpResourceRegistry()
            inv.resource_store = PackageResourceStore(engine_root)

            tools = self._build_tools(inv, engine_root)
            scf_get_agent = tools["scf_get_agent"]

            result = asyncio.run(scf_get_agent("NonExistent"))

            self.assertIn("error", result)
            self.assertIn("not found", result["error"].lower())


if __name__ == "__main__":
    unittest.main()
