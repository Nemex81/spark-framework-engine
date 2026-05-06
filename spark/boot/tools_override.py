"""D.2 — Factory per i 3 tool override SCF.

Espone ``register_override_tools`` che registra su *mcp* i tool:
scf_list_overrides, scf_override_resource, scf_drop_override.

Dipende da ``tools_resources`` per i helper condivisi
``_parse_resource_uri`` e ``_ensure_registry``.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from spark.boot.install_helpers import _sha256_text
from spark.boot.tools_resources import _ensure_registry, _parse_resource_uri
from spark.core.models import WorkspaceContext
from spark.inventory import FrameworkInventory
from spark.manifest import ManifestManager

_log = logging.getLogger("spark-framework-engine")

# Tipi di risorse supportate — spec invariante condivisa.
from spark.core.constants import _RESOURCE_TYPES  # type: ignore[attr-defined]


def register_override_tools(
    inventory: FrameworkInventory,
    ctx: WorkspaceContext,
    mcp: Any,
    tool_names: list[str],
) -> None:
    """Registra i 3 tool override SCF su *mcp*.

    Args:
        inventory: istanza FrameworkInventory condivisa con l'engine.
        ctx: WorkspaceContext con github_root e engine_root.
        mcp: istanza FastMCP su cui registrare i tool.
        tool_names: lista condivisa in cui appendere i nomi dei tool registrati.
    """

    def _register_tool(name: str) -> Any:
        tool_names.append(name)
        return mcp.tool()

    def _ensure_reg() -> Any:
        return _ensure_registry(inventory, ctx.engine_root)

    @_register_tool("scf_list_overrides")
    async def scf_list_overrides(
        resource_type: str | None = None,
    ) -> dict[str, Any]:
        """Lista override workspace registrati nel McpResourceRegistry.

        Args:
            resource_type: filtro opzionale (agents|prompts|skills|instructions).
        """
        registry = _ensure_reg()
        if resource_type is not None and resource_type not in _RESOURCE_TYPES:
            return {
                "success": False,
                "error": f"resource_type non valido: {resource_type}",
                "supported": list(_RESOURCE_TYPES),
            }
        items: list[dict[str, Any]] = []
        for uri in registry.list_all():
            if not registry.has_override(uri):
                continue
            meta = registry.get_metadata(uri) or {}
            rtype = str(meta.get("resource_type", ""))
            if resource_type is not None and rtype != resource_type:
                continue
            override_path = meta.get("override")
            sha = ""
            if override_path:
                try:
                    sha = _sha256_text(
                        Path(override_path).read_text(encoding="utf-8")
                    )
                except OSError:
                    sha = ""
            _, _, name = uri.partition("://")
            items.append({
                "uri": uri,
                "type": rtype,
                "name": name,
                "path": str(override_path) if override_path else None,
                "sha256": sha,
            })
        return {"count": len(items), "items": items}

    @_register_tool("scf_override_resource")
    async def scf_override_resource(
        uri: str, content: str
    ) -> dict[str, Any]:
        """Crea/aggiorna un override workspace per la risorsa indicata.

        Args:
            uri: URI nel formato ``{type}://{name}``.
            content: nuovo contenuto del file di override.
        """
        parsed = _parse_resource_uri(uri)
        if parsed is None:
            return {
                "success": False,
                "error": f"URI non valido: {uri}",
            }
        resource_type, name = parsed
        registry = _ensure_reg()
        if registry.resolve_engine(uri) is None and not registry.has_override(uri):
            return {
                "success": False,
                "error": (
                    f"Risorsa {uri} non registrata: l'override richiede una "
                    "risorsa engine o un override preesistente."
                ),
            }
        orchestrator_state = inventory.get_orchestrator_state()
        if not bool(orchestrator_state.get("github_write_authorized", False)):
            return {
                "success": False,
                "error": "github_write_authorized=False: scrittura su .github/ non autorizzata.",
                "authorization_required": True,
            }
        manifest_mgr = ManifestManager(ctx.github_root)
        try:
            target = manifest_mgr.write_override(resource_type, name, content)
        except (ValueError, OSError) as exc:
            return {"success": False, "error": str(exc)}
        registry.register_override(uri, target)
        return {
            "success": True,
            "uri": uri,
            "path": str(target),
            "sha256": _sha256_text(content),
        }

    @_register_tool("scf_drop_override")
    async def scf_drop_override(uri: str) -> dict[str, Any]:
        """Rimuove un override workspace e deregistra dal registry.

        Args:
            uri: URI nel formato ``{type}://{name}``.
        """
        parsed = _parse_resource_uri(uri)
        if parsed is None:
            return {
                "success": False,
                "error": f"URI non valido: {uri}",
            }
        resource_type, name = parsed
        registry = _ensure_reg()
        if not registry.has_override(uri):
            return {
                "success": False,
                "error": f"Nessun override registrato per {uri}",
            }
        orchestrator_state = inventory.get_orchestrator_state()
        if not bool(orchestrator_state.get("github_write_authorized", False)):
            return {
                "success": False,
                "error": "github_write_authorized=False: rimozione non autorizzata.",
                "authorization_required": True,
            }
        manifest_mgr = ManifestManager(ctx.github_root)
        try:
            removed = manifest_mgr.drop_override(resource_type, name)
        except OSError as exc:
            return {"success": False, "error": str(exc)}
        registry.drop_override(uri)
        return {"success": True, "uri": uri, "file_removed": removed}
