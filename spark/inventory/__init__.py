"""Public re-exports for the ``spark.inventory`` package.

Extracted to ``spark.inventory`` during Phase 0 modular refactoring.
"""
from __future__ import annotations

from spark.inventory.framework import FrameworkInventory, build_workspace_info
from spark.inventory.engine import EngineInventory

__all__ = [
    "FrameworkInventory",
    "EngineInventory",
    "build_workspace_info",
]
