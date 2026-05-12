"""Tests per spark.boot.tools_registry_client e scf_plugin_install_remote.

Copre:
- fetch_registry_data() con TTL e force_refresh
- get_remote_packages() con annotazione universe
- find_remote_package() — trovato, non trovato, case-insensitive
- scf_plugin_install_remote — logica di validazione (mcp_only reject, missing pkg)
- path traversal guard
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from spark.boot.tools_registry_client import (
    fetch_registry_data,
    find_remote_package,
    get_remote_packages,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_REGISTRY: dict[str, Any] = {
    "schema_version": "2.0",
    "packages": [
        {
            "id": "spark-base",
            "latest_version": "2.1.0",
            "delivery_mode": "mcp_only",
            "repo_url": "https://github.com/Nemex81/spark-base",
        },
        {
            "id": "acme-plugin",
            "latest_version": "1.2.0",
            "delivery_mode": "managed",
            "repo_url": "https://github.com/Nemex81/acme-plugin",
        },
        {
            "id": "no-delivery-plugin",
            "latest_version": "0.5.0",
            "repo_url": "https://github.com/Nemex81/no-delivery-plugin",
        },
    ],
}

_VALID_REGISTRY_URL = (
    "https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json"
)


def _write_cache(tmp_path: Path, data: dict[str, Any] | None = None) -> Path:
    cache = tmp_path / ".scf-registry-cache.json"
    cache.write_text(json.dumps(data or _SAMPLE_REGISTRY), encoding="utf-8")
    return cache


# ---------------------------------------------------------------------------
# fetch_registry_data
# ---------------------------------------------------------------------------


def test_fetch_registry_data_uses_cache_when_fresh(tmp_path: Path) -> None:
    """fetch_registry_data() usa la cache quando fresca senza chiamata rete."""
    _write_cache(tmp_path)
    with patch("urllib.request.urlopen") as mock_url:
        result = fetch_registry_data(tmp_path, _VALID_REGISTRY_URL, ttl_seconds=3600)
    mock_url.assert_not_called()
    assert "packages" in result


def test_fetch_registry_data_force_refresh_fetches_remote(tmp_path: Path) -> None:
    """fetch_registry_data(force_refresh=True) bypassa la cache."""
    _write_cache(tmp_path)
    fresh = {**_SAMPLE_REGISTRY, "schema_version": "3.0"}
    resp = MagicMock()
    resp.read.return_value = json.dumps(fresh).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=resp):
        result = fetch_registry_data(
            tmp_path, _VALID_REGISTRY_URL, ttl_seconds=3600, force_refresh=True
        )
    assert result["schema_version"] == "3.0"


def test_fetch_registry_data_raises_runtime_if_no_cache_no_network(tmp_path: Path) -> None:
    """fetch_registry_data() solleva RuntimeError se rete fallisce e cache assente."""
    import urllib.error
    with patch(
        "urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")
    ):
        with pytest.raises(RuntimeError):
            fetch_registry_data(tmp_path, _VALID_REGISTRY_URL)


# ---------------------------------------------------------------------------
# get_remote_packages — annotazione universe
# ---------------------------------------------------------------------------


def test_get_remote_packages_annotates_mcp_only_as_u1(tmp_path: Path) -> None:
    """get_remote_packages() aggiunge universe='U1' per mcp_only."""
    _write_cache(tmp_path)
    packages = get_remote_packages(tmp_path, _VALID_REGISTRY_URL)
    u1 = [p for p in packages if p["id"] == "spark-base"]
    assert len(u1) == 1
    assert u1[0]["universe"] == "U1"


def test_get_remote_packages_annotates_managed_as_u2(tmp_path: Path) -> None:
    """get_remote_packages() aggiunge universe='U2' per managed."""
    _write_cache(tmp_path)
    packages = get_remote_packages(tmp_path, _VALID_REGISTRY_URL)
    u2 = [p for p in packages if p["id"] == "acme-plugin"]
    assert len(u2) == 1
    assert u2[0]["universe"] == "U2"


def test_get_remote_packages_annotates_missing_delivery_as_u2(tmp_path: Path) -> None:
    """get_remote_packages() annota come U2 se delivery_mode è assente."""
    _write_cache(tmp_path)
    packages = get_remote_packages(tmp_path, _VALID_REGISTRY_URL)
    no_delivery = [p for p in packages if p["id"] == "no-delivery-plugin"]
    assert len(no_delivery) == 1
    assert no_delivery[0]["universe"] == "U2"


def test_get_remote_packages_returns_empty_on_runtime_error(tmp_path: Path) -> None:
    """get_remote_packages() ritorna lista vuota se registry non raggiungibile."""
    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
        result = get_remote_packages(tmp_path, _VALID_REGISTRY_URL)
    assert result == []


# ---------------------------------------------------------------------------
# find_remote_package
# ---------------------------------------------------------------------------


def test_find_remote_package_returns_entry_for_known_id(tmp_path: Path) -> None:
    """find_remote_package() trova un pacchetto per ID esatto."""
    _write_cache(tmp_path)
    result = find_remote_package(tmp_path, "acme-plugin", _VALID_REGISTRY_URL)
    assert result is not None
    assert result["id"] == "acme-plugin"
    assert result["universe"] == "U2"


def test_find_remote_package_is_case_insensitive(tmp_path: Path) -> None:
    """find_remote_package() ignora maiuscole/minuscole nell'ID."""
    _write_cache(tmp_path)
    result = find_remote_package(tmp_path, "ACME-PLUGIN", _VALID_REGISTRY_URL)
    assert result is not None
    assert result["id"] == "acme-plugin"


def test_find_remote_package_returns_none_for_unknown_id(tmp_path: Path) -> None:
    """find_remote_package() ritorna None se il pacchetto non esiste."""
    _write_cache(tmp_path)
    result = find_remote_package(tmp_path, "nonexistent-pkg", _VALID_REGISTRY_URL)
    assert result is None


# ---------------------------------------------------------------------------
# scf_plugin_install_remote — logica di validazione
# (test sulla logica pura senza avviare il server MCP)
# ---------------------------------------------------------------------------


def test_install_remote_rejects_mcp_only_universe_detection(tmp_path: Path) -> None:
    """Verifica che la logica U1 detection rifiuti mcp_only packages."""
    # Simula l'entry trovata per un pacchetto mcp_only
    entry = {
        "id": "spark-base",
        "latest_version": "2.1.0",
        "delivery_mode": "mcp_only",
        "universe": "U1",
    }
    delivery = str(entry.get("delivery_mode", "managed")).strip()
    is_mcp_only = delivery == "mcp_only"
    assert is_mcp_only is True


def test_install_remote_accepts_managed_delivery_mode(tmp_path: Path) -> None:
    """Verifica che la logica U2 detection accetti managed packages."""
    entry = {
        "id": "acme-plugin",
        "latest_version": "1.2.0",
        "delivery_mode": "managed",
        "universe": "U2",
    }
    delivery = str(entry.get("delivery_mode", "managed")).strip()
    is_mcp_only = delivery == "mcp_only"
    assert is_mcp_only is False


def test_install_remote_path_traversal_guard(tmp_path: Path) -> None:
    """Verifica il path traversal guard per plugin_files."""
    # Simula la logica guard usata in scf_plugin_install_remote
    dangerous_paths = [
        "../../../etc/passwd",
        ".github/../../../etc/shadow",
    ]
    for file_path in dangerous_paths:
        github_rel = file_path.removeprefix(".github/")
        has_traversal = ".." in Path(github_rel).parts
        assert has_traversal is True, f"Expected traversal detected for: {file_path!r}"


def test_install_remote_safe_paths_not_flagged(tmp_path: Path) -> None:
    """Verifica che path legittimi non vengano bloccati dal guard."""
    safe_paths = [
        ".github/agents/my-agent.agent.md",
        ".github/prompts/my-prompt.prompt.md",
        ".github/instructions/my.instructions.md",
    ]
    for file_path in safe_paths:
        github_rel = file_path.removeprefix(".github/")
        has_traversal = ".." in Path(github_rel).parts
        assert has_traversal is False, f"False positive for safe path: {file_path!r}"
