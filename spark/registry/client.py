# Modulo registry/client — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""RegistryClient — fetch/cache del registry SCF."""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from spark.core.constants import (
    ENGINE_VERSION,
    _REGISTRY_CACHE_FILENAME,
    _REGISTRY_TIMEOUT_SECONDS,
    _REGISTRY_URL,
)

_log: logging.Logger = logging.getLogger("spark-framework-engine")


class RegistryClient:
    """Fetch and cache the SCF registry index from GitHub.

    V1 supports public packages only (public raw.githubusercontent.com URLs).
    Any non-standard or private URL produces an explicit ValueError —
    no silent attempt is ever made on private raw URLs.
    """

    def __init__(
        self,
        github_root: Path,
        registry_url: str = _REGISTRY_URL,
        cache_path: Path | None = None,
    ) -> None:
        self._github_root = github_root
        self._registry_url = registry_url
        # v3.0: prefer engine-central cache when caller supplies one.
        # Legacy default kept for back-compat with v2.x callers and tests.
        self._cache_path = (
            cache_path
            if cache_path is not None
            else github_root / _REGISTRY_CACHE_FILENAME
        )

    def fetch(self) -> dict[str, Any]:
        """Return registry data, falling back to cache on network failure.

        Raises ValueError for non-public URLs.
        Raises RuntimeError if both network and cache are unavailable.
        """
        if not self._registry_url.startswith("https://raw.githubusercontent.com/"):
            raise ValueError(
                "Private or non-standard registry URLs are not supported in v1. "
                "Only public raw.githubusercontent.com URLs are accepted."
            )
        try:
            data = self._fetch_remote()
            self._save_cache(data)
            return data
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            _log.warning("Registry fetch failed (%s), falling back to cache", exc)
            return self._load_cache()

    def list_packages(self) -> list[dict[str, Any]]:
        """Return the packages array. Returns [] when registry is unavailable."""
        try:
            return list(self.fetch().get("packages", []))
        except RuntimeError:
            return []

    def is_cache_fresh(self, ttl_seconds: int = 3600) -> bool:
        """Return True if the local cache file exists and is younger than ttl_seconds.

        Args:
            ttl_seconds: Max age in seconds for the cache to be considered fresh.
                Default is 3600 (1 hour).

        Returns:
            True if cache file exists and mtime is within ttl_seconds.
        """
        if not self._cache_path.is_file():
            return False
        age = time.time() - self._cache_path.stat().st_mtime
        return age < ttl_seconds

    def cache_age_seconds(self) -> float | None:
        """Return cache age in seconds, or None when no cache file exists."""
        if not self._cache_path.is_file():
            return None
        return max(0.0, time.time() - self._cache_path.stat().st_mtime)

    def fetch_if_stale(self, ttl_seconds: int = 3600) -> dict[str, Any]:
        """Return registry data from cache if fresh, otherwise fetch remote.

        Falls back to cache (stale) on network failure. Raises RuntimeError
        only when both remote and cache are unavailable.

        Args:
            ttl_seconds: TTL in seconds. Default 3600 (1 hour).

        Returns:
            Registry dict with 'packages' list.
        """
        if self.is_cache_fresh(ttl_seconds):
            _log.debug("Registry cache fresh (< %ds), skipping remote fetch.", ttl_seconds)
            return self._load_cache()
        return self.fetch()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_remote(self) -> dict[str, Any]:
        req = urllib.request.Request(
            self._registry_url,
            headers={"User-Agent": f"spark-framework-engine/{ENGINE_VERSION}"},
        )
        with urllib.request.urlopen(req, timeout=_REGISTRY_TIMEOUT_SECONDS) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
        return json.loads(raw)  # type: ignore[no-any-return]

    def _save_cache(self, data: dict[str, Any]) -> None:
        try:
            self._cache_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            _log.warning("Cannot write registry cache: %s", exc)

    def _load_cache(self) -> dict[str, Any]:
        if not self._cache_path.is_file():
            raise RuntimeError(
                "Registry unavailable and no local cache found at "
                f"{self._cache_path}. Connect to the internet and retry."
            )
        try:
            return json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Registry cache corrupted: {exc}") from exc

    def fetch_package_manifest(self, repo_url: str) -> dict[str, Any]:
        """Fetch the package-manifest.json from a package repo.

        Constructs the raw URL from repo_url. No caching — always fetched fresh
        to guarantee consistency with the published package version.
        Raises ValueError for non-github.com repo URLs.
        Raises RuntimeError on network or parse failure.
        """
        if not repo_url.startswith("https://github.com/"):
            raise ValueError(
                f"Unsupported repo URL: {repo_url!r}. "
                "Only https://github.com/ URLs are supported."
            )
        raw_url = (
            repo_url.replace("https://github.com/", "https://raw.githubusercontent.com/")
            + "/main/package-manifest.json"
        )
        try:
            raw = self.fetch_raw_file(raw_url)
            return json.loads(raw)  # type: ignore[no-any-return]
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Cannot fetch package manifest from {raw_url}: {exc}"
            ) from exc

    def fetch_raw_file(self, raw_url: str) -> str:
        """Fetch a single raw text file from a URL. No caching."""
        req = urllib.request.Request(
            raw_url,
            headers={"User-Agent": f"spark-framework-engine/{ENGINE_VERSION}"},
        )
        with urllib.request.urlopen(req, timeout=_REGISTRY_TIMEOUT_SECONDS) as resp:  # noqa: S310
            return resp.read().decode("utf-8")
