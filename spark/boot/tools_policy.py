"""Factory module for policy tool group (D.4).

Registers the following 9 MCP tools:
  scf_get_project_profile, scf_get_global_instructions, scf_get_model_policy,
  scf_get_framework_version, scf_get_workspace_info,
  scf_get_runtime_state, scf_update_runtime_state,
  scf_get_update_policy, scf_set_update_policy.

The factory ``register_policy_tools(engine, mcp, tool_names)`` is called
from ``SparkFrameworkEngine.register_tools()`` after ``_init_runtime_objects()``
has been called so that ``engine._manifest`` is already initialized.
"""
from __future__ import annotations

import logging
from typing import Any

from spark.core.constants import ENGINE_VERSION
from spark.core.utils import _format_utc_timestamp, _utc_now
from spark.inventory.framework import build_workspace_info
from spark.workspace import (
    _read_update_policy_payload,
    _update_policy_path,
    _validate_update_mode,
    _write_update_policy_payload,
)
from spark.boot.tools_resources import _ff_to_dict

_log = logging.getLogger("spark-framework-engine")


def register_policy_tools(engine: Any, mcp: Any, tool_names: list[str]) -> None:
    """Register 9 policy and workspace-info tools into mcp.

    Args:
        engine: SparkFrameworkEngine instance (must have _ctx, _manifest, _inventory
                already initialized via _init_runtime_objects()).
        mcp: FastMCP instance.
        tool_names: Shared list to which tool names are appended on registration.
    """
    ctx = engine._ctx
    manifest = engine._manifest
    inventory = engine._inventory

    def _register_tool(name: str) -> Any:
        tool_names.append(name)
        return mcp.tool()

    @_register_tool("scf_get_project_profile")
    async def scf_get_project_profile() -> dict[str, Any]:
        """Return project-profile.md content, metadata and initialized state."""
        ff = inventory.get_project_profile()
        if ff is None:
            return {"success": False, "error": "project-profile.md not found in .github/."}
        result = _ff_to_dict(ff)
        result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
        result["initialized"] = bool(ff.metadata.get("initialized", False))
        if not result["initialized"]:
            result["warning"] = (
                "Project not initialized. Run #project-setup to configure this workspace."
            )
        return result

    @_register_tool("scf_get_global_instructions")
    async def scf_get_global_instructions() -> dict[str, Any]:
        """Return copilot-instructions.md content and metadata."""
        ff = inventory.get_global_instructions()
        if ff is None:
            return {"success": False, "error": "copilot-instructions.md not found in .github/."}
        result = _ff_to_dict(ff)
        result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
        return result

    @_register_tool("scf_get_model_policy")
    async def scf_get_model_policy() -> dict[str, Any]:
        """Return model-policy.instructions.md content and metadata."""
        ff = inventory.get_model_policy()
        if ff is None:
            return {
                "success": False,
                "error": "model-policy.instructions.md not found in .github/instructions/.",
            }
        result = _ff_to_dict(ff)
        result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
        return result

    @_register_tool("scf_get_framework_version")
    async def scf_get_framework_version() -> dict[str, Any]:
        """Return the engine version and installed SCF package versions."""
        return {
            "engine_version": ENGINE_VERSION,
            "packages": manifest.get_installed_versions(),
        }

    @_register_tool("scf_get_workspace_info")
    async def scf_get_workspace_info() -> dict[str, Any]:
        """Return workspace paths, initialization state and SCF asset counts."""
        return build_workspace_info(ctx, inventory)

    @_register_tool("scf_get_runtime_state")
    async def scf_get_runtime_state() -> dict[str, Any]:
        """Leggi lo stato runtime dell'orchestratore dal workspace corrente."""
        return inventory.get_orchestrator_state()

    @_register_tool("scf_update_runtime_state")
    async def scf_update_runtime_state(patch: dict[str, Any]) -> dict[str, Any]:
        """Aggiorna selettivamente lo stato runtime dell'orchestratore nel workspace."""
        return inventory.set_orchestrator_state(patch)

    @_register_tool("scf_get_update_policy")
    async def scf_get_update_policy() -> dict[str, Any]:
        """Return the workspace update policy used for SCF file updates."""
        payload, source = _read_update_policy_payload(ctx.github_root)
        return {
            "success": True,
            "policy": payload["update_policy"],
            "path": str(_update_policy_path(ctx.github_root)),
            "source": source,
        }

    @_register_tool("scf_set_update_policy")
    async def scf_set_update_policy(
        auto_update: bool,
        default_mode: str | None = None,
        mode_per_package: dict[str, str] | None = None,
        mode_per_file_role: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Create or update the workspace update policy for SCF file operations."""
        payload, source = _read_update_policy_payload(ctx.github_root)
        policy = dict(payload["update_policy"])

        if default_mode is not None:
            validated_default_mode = _validate_update_mode(
                default_mode,
                allow_selective=False,
            )
            if validated_default_mode is None:
                return {
                    "success": False,
                    "error": (
                        "Invalid default_mode. Supported values: ask, integrative, "
                        "replace, conservative."
                    ),
                    "path": str(_update_policy_path(ctx.github_root)),
                }
            policy["default_mode"] = validated_default_mode

        if mode_per_package is not None:
            normalized_package_modes: dict[str, str] = {}
            invalid_package_modes: list[str] = []
            for package_key, mode_value in mode_per_package.items():
                normalized_key = str(package_key).strip()
                validated_mode = _validate_update_mode(str(mode_value), allow_selective=True)
                if not normalized_key or validated_mode is None:
                    invalid_package_modes.append(f"{package_key}={mode_value}")
                    continue
                normalized_package_modes[normalized_key] = validated_mode
            if invalid_package_modes:
                return {
                    "success": False,
                    "error": "Invalid mode_per_package entries.",
                    "invalid_entries": invalid_package_modes,
                    "path": str(_update_policy_path(ctx.github_root)),
                }
            policy["mode_per_package"] = normalized_package_modes

        if mode_per_file_role is not None:
            normalized_role_modes: dict[str, str] = {}
            invalid_role_modes: list[str] = []
            for role_key, mode_value in mode_per_file_role.items():
                normalized_key = str(role_key).strip()
                validated_mode = _validate_update_mode(str(mode_value), allow_selective=True)
                if not normalized_key or validated_mode is None:
                    invalid_role_modes.append(f"{role_key}={mode_value}")
                    continue
                normalized_role_modes[normalized_key] = validated_mode
            if invalid_role_modes:
                return {
                    "success": False,
                    "error": "Invalid mode_per_file_role entries.",
                    "invalid_entries": invalid_role_modes,
                    "path": str(_update_policy_path(ctx.github_root)),
                }
            policy["mode_per_file_role"] = normalized_role_modes

        policy["auto_update"] = bool(auto_update)
        policy["last_changed"] = _format_utc_timestamp(_utc_now())
        policy["changed_by_user"] = True

        saved_path = _write_update_policy_payload(
            ctx.github_root,
            {"update_policy": policy},
        )
        return {
            "success": True,
            "policy": policy,
            "path": str(saved_path),
            "source": source,
        }
