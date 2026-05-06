"""D.1 — Factory per i 13 tool risorse SCF.

Espone ``register_resource_tools`` che registra su *mcp* i tool:
scf_read_resource, scf_get_skill_resource, scf_get_instruction_resource,
scf_get_agent_resource, scf_get_prompt_resource, scf_list_agents, scf_get_agent,
scf_list_skills, scf_get_skill, scf_list_instructions, scf_get_instruction,
scf_list_prompts, scf_get_prompt.

Gli helper ``_ff_to_dict``, ``_parse_resource_uri`` e ``_ensure_registry`` sono
definiti a livello di modulo per essere importabili da altri sub-moduli (D.2).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from spark.core.models import FrameworkFile
from spark.inventory import EngineInventory, FrameworkInventory
from spark.registry import McpResourceRegistry

if TYPE_CHECKING:
    pass

_log = logging.getLogger("spark-framework-engine")

# Tipi di risorse supportate — spec invariante condivisa con engine.py.
_RESOURCE_TYPES: frozenset[str] = frozenset({"agents", "skills", "instructions", "prompts"})


# ---------------------------------------------------------------------------
# Helper riusabili (esportati per D.2 override tools)
# ---------------------------------------------------------------------------

def _ff_to_dict(ff: FrameworkFile) -> dict[str, Any]:
    """Converti un FrameworkFile in dict serializzabile MCP."""
    return {
        "name": ff.name,
        "path": str(ff.path),
        "category": ff.category,
        "summary": ff.summary,
        "metadata": ff.metadata,
    }


def _parse_resource_uri(uri: str) -> tuple[str, str] | None:
    """Analizza un URI ``{type}://{name}`` e restituisce ``(type, name)`` o None."""
    if not isinstance(uri, str) or "://" not in uri:
        return None
    scheme, _, name = uri.partition("://")
    if scheme not in _RESOURCE_TYPES:
        return None
    if not name:
        return None
    return scheme, name


def _ensure_registry(inventory: FrameworkInventory, engine_root: Path) -> McpResourceRegistry:
    """Garantisce che il McpResourceRegistry sia popolato e lo restituisce.

    Args:
        inventory: l'istanza FrameworkInventory dell'engine.
        engine_root: path root del motore per fallback EngineInventory.

    Returns:
        McpResourceRegistry popolato.
    """
    if inventory.mcp_registry is None:
        try:
            engine_manifest = EngineInventory(engine_root=engine_root).engine_manifest
        except Exception as exc:  # noqa: BLE001
            _log.error(
                "[SPARK-ENGINE][ERROR] _ensure_registry: EngineInventory init failed: %s. "
                "Registry sarà vuoto — le risorse URI-based non saranno disponibili.",
                exc,
            )
            engine_manifest = {}
        inventory.populate_mcp_registry(engine_manifest=engine_manifest)
    assert inventory.mcp_registry is not None  # noqa: S101
    return inventory.mcp_registry


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def register_resource_tools(
    inventory: FrameworkInventory,
    engine_root: Path,
    mcp: Any,
    tool_names: list[str],
) -> None:
    """Registra i 13 tool risorse SCF su *mcp*.

    Args:
        inventory: istanza FrameworkInventory condivisa con l'engine.
        engine_root: path root del motore per fallback EngineInventory.
        mcp: istanza FastMCP su cui registrare i tool.
        tool_names: lista condivisa in cui appendere i nomi dei tool registrati.
    """

    def _register_tool(name: str) -> Any:
        tool_names.append(name)
        return mcp.tool()

    def _ensure_reg() -> McpResourceRegistry:
        return _ensure_registry(inventory, engine_root)

    @_register_tool("scf_read_resource")
    async def scf_read_resource(
        uri: str, source: str = "auto"
    ) -> dict[str, Any]:
        """Legge il contenuto di una risorsa MCP (engine o override).

        Args:
            uri: URI nel formato ``{type}://{name}``.
            source: ``auto`` (override > engine), ``engine``, ``override``.
        """
        parsed = _parse_resource_uri(uri)
        if parsed is None:
            return {
                "success": False,
                "error": f"URI non valido: {uri}",
            }
        if source not in ("auto", "engine", "override"):
            return {
                "success": False,
                "error": f"source non valido: {source}",
            }
        reg = _ensure_reg()
        target: Path | None
        actual_source: str
        if source == "engine":
            target = reg.resolve_engine(uri)
            actual_source = "engine"
        elif source == "override":
            if not reg.has_override(uri):
                return {
                    "success": False,
                    "error": f"Override non presente per {uri}",
                }
            meta = reg.get_metadata(uri) or {}
            ov = meta.get("override")
            target = Path(ov) if ov else None
            actual_source = "override"
        else:  # auto
            target = reg.resolve(uri)
            actual_source = "override" if reg.has_override(uri) else "engine"
        if target is None or not target.is_file():
            return {
                "success": False,
                "error": f"Risorsa non trovata: {uri} (source={source})",
            }
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return {
                "success": False,
                "error": f"Errore lettura {target}: {exc}",
            }
        return {
            "success": True,
            "uri": uri,
            "source": actual_source,
            "path": str(target),
            "content": content,
        }

    @_register_tool("scf_get_skill_resource")
    async def scf_get_skill_resource(name: str) -> dict[str, Any]:
        """Return full content and metadata for a single SCF skill by name via skills:// URI."""
        uri = McpResourceRegistry.make_uri("skills", name)
        reg = _ensure_reg()
        ff = reg.resolve(uri)
        if ff is None:
            return {
                "success": False,
                "error": f"Skill resource URI not found: {uri}",
                "available": [f.name for f in inventory.list_skills()],
            }
        result = _ff_to_dict(ff)
        result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
        result["mcp_uri"] = uri
        result["mime_type"] = "text/markdown"
        return result

    @_register_tool("scf_get_instruction_resource")
    async def scf_get_instruction_resource(name: str) -> dict[str, Any]:
        """Return full content and metadata for a single SCF instruction by name via instructions:// URI."""
        uri = McpResourceRegistry.make_uri("instructions", name)
        reg = _ensure_reg()
        ff = reg.resolve(uri)
        if ff is None:
            return {
                "success": False,
                "error": f"Instruction resource URI not found: {uri}",
                "available": [f.name for f in inventory.list_instructions()],
            }
        result = _ff_to_dict(ff)
        result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
        result["mcp_uri"] = uri
        result["mime_type"] = "text/markdown"
        return result

    @_register_tool("scf_get_agent_resource")
    async def scf_get_agent_resource(name: str) -> dict[str, Any]:
        """Return full content and metadata for a single SCF agent by name via agents:// URI."""
        uri = McpResourceRegistry.make_uri("agents", name)
        reg = _ensure_reg()
        ff = reg.resolve(uri)
        if ff is None:
            return {
                "success": False,
                "error": f"Agent resource URI not found: {uri}",
                "available": [f.name for f in inventory.list_agents()],
            }
        result = _ff_to_dict(ff)
        result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
        result["mcp_uri"] = uri
        result["mime_type"] = "text/markdown"
        return result

    @_register_tool("scf_get_prompt_resource")
    async def scf_get_prompt_resource(name: str) -> dict[str, Any]:
        """Return full content and metadata for a single SCF prompt by name via prompts:// URI."""
        uri = McpResourceRegistry.make_uri("prompts", name)
        reg = _ensure_reg()
        ff = reg.resolve(uri)
        if ff is None:
            return {
                "success": False,
                "error": f"Prompt resource URI not found: {uri}",
                "available": [f.name for f in inventory.list_prompts()],
            }
        result = _ff_to_dict(ff)
        result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
        result["mcp_uri"] = uri
        result["mime_type"] = "text/markdown"
        return result

    @_register_tool("scf_list_agents")
    async def scf_list_agents() -> dict[str, Any]:
        """Return all discovered SCF agents with name, path and summary."""
        items = inventory.list_agents()
        return {"count": len(items), "agents": [_ff_to_dict(ff) for ff in items]}

    @_register_tool("scf_get_agent")
    async def scf_get_agent(name: str) -> dict[str, Any]:
        """Return full content and metadata for a single SCF agent by name."""
        for ff in inventory.list_agents():
            if ff.name.lower() == name.lower():
                result = _ff_to_dict(ff)
                result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
                return result
        return {
            "success": False,
            "error": f"Agent '{name}' not found.",
            "available": [ff.name for ff in inventory.list_agents()],
        }

    @_register_tool("scf_list_skills")
    async def scf_list_skills() -> dict[str, Any]:
        """Return all discovered SCF skills with name, path and summary."""
        items = inventory.list_skills()
        return {"count": len(items), "skills": [_ff_to_dict(ff) for ff in items]}

    @_register_tool("scf_get_skill")
    async def scf_get_skill(name: str) -> dict[str, Any]:
        """Return full content and metadata for a single SCF skill by name."""
        query = name.lower().removesuffix(".skill")
        for ff in inventory.list_skills():
            if ff.name.lower().removesuffix(".skill") == query:
                result = _ff_to_dict(ff)
                result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
                return result
        return {
            "success": False,
            "error": f"Skill '{name}' not found.",
            "available": [ff.name for ff in inventory.list_skills()],
        }

    @_register_tool("scf_list_instructions")
    async def scf_list_instructions() -> dict[str, Any]:
        """Return all discovered SCF instruction files with name, path and summary."""
        items = inventory.list_instructions()
        return {"count": len(items), "instructions": [_ff_to_dict(ff) for ff in items]}

    @_register_tool("scf_get_instruction")
    async def scf_get_instruction(name: str) -> dict[str, Any]:
        """Return full content and metadata for a single SCF instruction by name."""
        query = name.lower().removesuffix(".instructions")
        for ff in inventory.list_instructions():
            if ff.name.lower().removesuffix(".instructions") == query:
                result = _ff_to_dict(ff)
                result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
                return result
        return {
            "success": False,
            "error": f"Instruction '{name}' not found.",
            "available": [ff.name for ff in inventory.list_instructions()],
        }

    @_register_tool("scf_list_prompts")
    async def scf_list_prompts() -> dict[str, Any]:
        """Return all SCF prompt files. Read-only — slash commands are handled natively by VS Code."""
        items = inventory.list_prompts()
        return {"count": len(items), "prompts": [_ff_to_dict(ff) for ff in items]}

    @_register_tool("scf_get_prompt")
    async def scf_get_prompt(name: str) -> dict[str, Any]:
        """Return full content of a SCF prompt file by stem name."""
        query = name.lower().removesuffix(".prompt")
        for ff in inventory.list_prompts():
            if ff.name.lower().removesuffix(".prompt") == query:
                result = _ff_to_dict(ff)
                result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
                return result
        return {
            "success": False,
            "error": f"Prompt '{name}' not found.",
            "available": [ff.name for ff in inventory.list_prompts()],
        }
