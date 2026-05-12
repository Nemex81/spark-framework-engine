"""Registry client helpers for tools — TTL-cached access to scf-registry.

Thin helpers for tools that need to interact with the remote SCF registry.
All functions delegate to ``RegistryClient.fetch_if_stale()`` to honour the
1-hour TTL cache and avoid unnecessary GitHub HTTPS requests.

Key differences from calling ``RegistryClient`` directly:
- TTL is always applied (``ttl_seconds=3600`` default).
- ``force_refresh=True`` bypasses the TTL (passes ``ttl_seconds=0``).
- ``get_remote_packages()`` returns packages already annotated with a
  ``universe`` field (``"U1"`` for ``mcp_only``, ``"U2"`` for all others).
- ``find_remote_package()`` performs a case-insensitive id-match.

These helpers contain zero MCP tool logic — they exist only to avoid
duplicating TTL/annotation logic across multiple tool modules.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from spark.core.constants import _REGISTRY_URL
from spark.registry.client import RegistryClient

_log: logging.Logger = logging.getLogger("spark-framework-engine")

__all__ = [
    "fetch_registry_data",
    "get_remote_packages",
    "find_remote_package",
]

# Default TTL usato in tutti gli helper di questo modulo.
_DEFAULT_TTL_SECONDS: int = 3600


def _make_client(
    github_root: Path,
    registry_url: str = _REGISTRY_URL,
    *,
    engine: Any = None,
) -> RegistryClient:
    """Return the engine registry client if available, otherwise create one.

    Args:
        github_root: Path to the workspace .github/ directory.
        registry_url: URL of the remote registry (default: SCF public registry).
        engine: Optional SparkFrameworkEngine instance. If provided and has
            a ``_registry_client`` attribute, that client is reused.

    Returns:
        RegistryClient ready to use.
    """
    if engine is not None:
        rc = getattr(engine, "_registry_client", None)
        if rc is not None:
            return rc  # type: ignore[return-value]
    return RegistryClient(github_root, registry_url=registry_url)


def fetch_registry_data(
    github_root: Path,
    registry_url: str = _REGISTRY_URL,
    *,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    force_refresh: bool = False,
    engine: Any = None,
) -> dict[str, Any]:
    """Return raw registry data, using TTL cache unless force_refresh is True.

    Args:
        github_root: Path to workspace .github/ directory (cache lives here).
        registry_url: URL of the remote registry JSON.
        ttl_seconds: Cache TTL in seconds. Default 3600 (1 hour).
        force_refresh: If True, bypass TTL and fetch fresh data.
        engine: Optional engine instance for client reuse.

    Returns:
        Registry dict with a ``packages`` list.

    Raises:
        RuntimeError: If both network and cache are unavailable.
        ValueError: If the registry URL is not a public raw.githubusercontent.com URL.
    """
    client = _make_client(github_root, registry_url, engine=engine)
    effective_ttl = 0 if force_refresh else ttl_seconds
    return client.fetch_if_stale(ttl_seconds=effective_ttl)


def get_remote_packages(
    github_root: Path,
    registry_url: str = _REGISTRY_URL,
    *,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    force_refresh: bool = False,
    engine: Any = None,
) -> list[dict[str, Any]]:
    """Return all registry packages annotated with a ``universe`` field.

    Each returned dict includes the original registry fields plus:
    - ``universe``: ``"U1"`` if ``delivery_mode == "mcp_only"``, else ``"U2"``.

    Returns an empty list if the registry is unreachable and no cache exists.

    Args:
        github_root: Path to workspace .github/ directory.
        registry_url: URL of the remote registry JSON.
        ttl_seconds: Cache TTL in seconds.
        force_refresh: If True, bypass TTL and fetch fresh data.
        engine: Optional engine instance for client reuse.

    Returns:
        Annotated list of package dicts.
    """
    try:
        data = fetch_registry_data(
            github_root,
            registry_url,
            ttl_seconds=ttl_seconds,
            force_refresh=force_refresh,
            engine=engine,
        )
    except RuntimeError as exc:
        _log.warning(
            "[SPARK-REGISTRY][WARNING] get_remote_packages: registry non raggiungibile: %s",
            exc,
        )
        return []

    raw: list[dict[str, Any]] = data.get("packages", [])
    annotated: list[dict[str, Any]] = []
    for pkg in raw:
        delivery = str(pkg.get("delivery_mode", "managed")).strip()
        universe = "U1" if delivery == "mcp_only" else "U2"
        annotated.append({**pkg, "universe": universe, "delivery_mode": delivery})
    return annotated


def find_remote_package(
    github_root: Path,
    pkg_id: str,
    registry_url: str = _REGISTRY_URL,
    *,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    force_refresh: bool = False,
    engine: Any = None,
) -> dict[str, Any] | None:
    """Find a single package in the remote registry by ID.

    Performs a case-insensitive match on the ``id`` field of each package.

    Args:
        github_root: Path to workspace .github/ directory.
        pkg_id: Package identifier to look up (e.g. ``"spark-base"``).
        registry_url: URL of the remote registry JSON.
        ttl_seconds: Cache TTL in seconds.
        force_refresh: If True, bypass TTL.
        engine: Optional engine instance for client reuse.

    Returns:
        Annotated package dict (including ``universe`` field), or None if not found.
    """
    packages = get_remote_packages(
        github_root,
        registry_url,
        ttl_seconds=ttl_seconds,
        force_refresh=force_refresh,
        engine=engine,
    )
    target = pkg_id.strip().lower()
    return next(
        (p for p in packages if str(p.get("id", "")).strip().lower() == target),
        None,
    )
