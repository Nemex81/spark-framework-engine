# Modulo registry — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""Public re-exports for the ``spark.registry`` package."""
from __future__ import annotations

from spark.registry.client import RegistryClient
from spark.registry.mcp import McpResourceRegistry
from spark.registry.resolver import ResourceResolver
from spark.registry.store import PackageResourceStore, _resource_filename_candidates
from spark.registry.v3_store import (
    _V3_STORE_INSTALLATION_MODE,
    _build_package_raw_url_base,
    _v3_store_sentinel_file,
)

__all__ = [
    "McpResourceRegistry",
    "PackageResourceStore",
    "RegistryClient",
    "ResourceResolver",
    "_V3_STORE_INSTALLATION_MODE",
    "_build_package_raw_url_base",
    "_resource_filename_candidates",
    "_v3_store_sentinel_file",
]
