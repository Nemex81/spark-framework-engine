# Modulo packages — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""Public re-exports for the ``spark.packages`` package."""
from __future__ import annotations

from spark.packages.lifecycle import (
    _install_package_v3_into_store,
    _list_orphan_overrides_for_package,
    _remove_package_v3_from_store,
    _v3_overrides_blocking_update,
)
from spark.packages.registry_summary import (
    _build_registry_package_summary,
    _get_registry_min_engine_version,
    _resolve_package_version,
)

__all__ = [
    "_build_registry_package_summary",
    "_get_registry_min_engine_version",
    "_install_package_v3_into_store",
    "_list_orphan_overrides_for_package",
    "_remove_package_v3_from_store",
    "_resolve_package_version",
    "_v3_overrides_blocking_update",
]
