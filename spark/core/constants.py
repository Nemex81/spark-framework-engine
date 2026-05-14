"""Constants module — estratto da spark-framework-engine.py durante Fase 0.

Contiene esclusivamente costanti immutabili e nomi di filesystem usati
trasversalmente dal motore SCF. Nessuna logica, nessuna dipendenza interna.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Engine version
# ---------------------------------------------------------------------------

ENGINE_VERSION: str = "3.6.0"


# ---------------------------------------------------------------------------
# Changelogs directory
# ---------------------------------------------------------------------------
_CHANGELOGS_SUBDIR: str = "changelogs"
_SNAPSHOTS_SUBDIR: str = "snapshots"
_MERGE_SESSIONS_SUBDIR: str = "merge-sessions"
_BACKUPS_SUBDIR: str = "backups"
_USER_PREFS_FILENAME: str = "user-prefs.json"

# ---------------------------------------------------------------------------
# Runtime directory configuration
# ---------------------------------------------------------------------------
_SPARK_RUNTIME_DIR_ENV: str = "SPARK_RUNTIME_DIR"
_ALLOWED_UPDATE_MODES: frozenset[str] = frozenset(
    {"ask", "integrative", "replace", "conservative", "selective"}
)


# ---------------------------------------------------------------------------
# Manifest / bootstrap identifiers
# ---------------------------------------------------------------------------
_MANIFEST_FILENAME: str = ".scf-manifest.json"
_BOOTSTRAP_PACKAGE_ID: str = "scf-engine-bootstrap"


# ---------------------------------------------------------------------------
# Resource categories
# ---------------------------------------------------------------------------
_RESOURCE_TYPES: tuple[str, ...] = ("agents", "prompts", "skills", "instructions")


# ---------------------------------------------------------------------------
# Registry endpoints
# ---------------------------------------------------------------------------
_REGISTRY_URL: str = (
    "https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json"
)
_REGISTRY_CACHE_FILENAME: str = ".scf-registry-cache.json"
_REGISTRY_TIMEOUT_SECONDS: int = 5


# ---------------------------------------------------------------------------
# Manifest schema versions
# ---------------------------------------------------------------------------
_MANIFEST_SCHEMA_VERSION: str = "3.0"
_SUPPORTED_MANIFEST_SCHEMA_VERSIONS: frozenset[str] = frozenset(
    {"1.0", "2.0", "2.1", "3.0"}
)
_LEGACY_MANIFEST_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0", "2.0", "2.1"})
