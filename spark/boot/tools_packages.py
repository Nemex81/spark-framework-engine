"""Facade di retrocompatibilità — spark.boot.tools_packages (Sprint 3 D1).

All 15 package lifecycle MCP tools have been moved to thematic submodules:
  - tools_packages_query       -> scf_list_available_packages, scf_get_package_info,
                                  scf_list_installed_packages, scf_plan_install
  - tools_packages_install     -> scf_install_package
  - tools_packages_update      -> scf_check_updates, scf_update_package,
                                  scf_update_packages, scf_apply_updates
  - tools_packages_remove      -> scf_remove_package, scf_get_package_changelog
  - tools_packages_diagnostics -> scf_resolve_conflict_ai, scf_approve_conflict,
                                  scf_reject_conflict, scf_finalize_update

This module re-exports register_package_tools with the identical signature
expected by spark.boot.engine. Zero logic lives here.
"""
from __future__ import annotations

from typing import Any

from spark.boot.tools_packages_query import register_query_package_tools
from spark.boot.tools_packages_install import register_install_package_tools
from spark.boot.tools_packages_update import register_update_package_tools
from spark.boot.tools_packages_remove import register_remove_package_tools
from spark.boot.tools_packages_diagnostics import register_diagnostics_package_tools

__all__ = ["register_package_tools"]


def register_package_tools(engine: Any, mcp: Any, tool_names: list[str]) -> None:
    """Register all 15 package lifecycle tools -- delegates to thematic sub-factories.

    Sets engine._install_package_tool_fn so that register_bootstrap_tools
    (called immediately after by SparkFrameworkEngine.register_tools) can
    invoke scf_install_package during workspace bootstrap.

    Args:
        engine: SparkFrameworkEngine instance.
        mcp: FastMCP instance.
        tool_names: Shared list to which tool names are appended on registration.
    """
    scf_plan_install = register_query_package_tools(engine, mcp, tool_names)
    scf_install_package = register_install_package_tools(engine, mcp, tool_names)
    # D.3: inject scf_install_package as callback for scf_bootstrap_workspace.
    engine._install_package_tool_fn = scf_install_package
    register_update_package_tools(
        engine,
        mcp,
        tool_names,
        scf_install_package=scf_install_package,
        scf_plan_install=scf_plan_install,
    )
    register_remove_package_tools(engine, mcp, tool_names)
    register_diagnostics_package_tools(engine, mcp, tool_names)
