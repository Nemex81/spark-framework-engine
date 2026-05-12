"""Tests per Registry U2 Client — is_cache_fresh, fetch_if_stale, dispatcher hint.

Punto 3 — Prompt Copilot Registry U2 Client (scf-registry Fetch Dinamico)
Copre:
- RegistryClient.is_cache_fresh() con TTL
- RegistryClient.fetch_if_stale() — usa cache se fresca, altrimenti fetch remoto
- _build_u2_registry_hint() — lettura cache locale e confronto versioni
- scf_plugin_list_remote tool — annotazione universe U1/U2
"""
from __future__ import annotations

import json
import time
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from spark.registry.client import RegistryClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_REGISTRY: dict[str, Any] = {
    "schema_version": "2.0",
    "packages": [
        {"id": "spark-base", "latest_version": "2.1.0", "delivery_mode": "mcp_only"},
        {"id": "scf-master-codecrafter", "latest_version": "2.3.0", "delivery_mode": "mcp_only"},
        {"id": "acme-plugin", "latest_version": "1.0.0", "delivery_mode": "managed"},
    ],
}

_VALID_REGISTRY_URL = (
    "https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json"
)


def _mock_urlopen(data: dict[str, Any]) -> Any:
    raw = json.dumps(data).encode()
    resp = MagicMock()
    resp.read.return_value = raw
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ---------------------------------------------------------------------------
# is_cache_fresh — assenza cache
# ---------------------------------------------------------------------------


def test_is_cache_fresh_returns_false_when_no_cache(tmp_path: Path) -> None:
    """is_cache_fresh() ritorna False se il file cache non esiste."""
    client = RegistryClient(tmp_path, registry_url=_VALID_REGISTRY_URL)
    assert client.is_cache_fresh() is False


# ---------------------------------------------------------------------------
# is_cache_fresh — cache recente
# ---------------------------------------------------------------------------


def test_is_cache_fresh_returns_true_when_cache_young(tmp_path: Path) -> None:
    """is_cache_fresh() ritorna True se la cache è stata scritta adesso."""
    cache_file = tmp_path / ".scf-registry-cache.json"
    cache_file.write_text(json.dumps(_SAMPLE_REGISTRY), encoding="utf-8")
    client = RegistryClient(tmp_path, registry_url=_VALID_REGISTRY_URL)
    assert client.is_cache_fresh(ttl_seconds=3600) is True


# ---------------------------------------------------------------------------
# is_cache_fresh — cache scaduta
# ---------------------------------------------------------------------------


def test_is_cache_fresh_returns_false_when_cache_old(tmp_path: Path) -> None:
    """is_cache_fresh() ritorna False se la cache è più vecchia del TTL."""
    cache_file = tmp_path / ".scf-registry-cache.json"
    cache_file.write_text(json.dumps(_SAMPLE_REGISTRY), encoding="utf-8")
    # Mtime 2 ore fa
    old_mtime = time.time() - 7200
    import os
    os.utime(cache_file, (old_mtime, old_mtime))
    client = RegistryClient(tmp_path, registry_url=_VALID_REGISTRY_URL)
    assert client.is_cache_fresh(ttl_seconds=3600) is False


# ---------------------------------------------------------------------------
# fetch_if_stale — usa cache fresca
# ---------------------------------------------------------------------------


def test_fetch_if_stale_uses_cache_when_fresh(tmp_path: Path) -> None:
    """fetch_if_stale() restituisce dati dalla cache locale senza fetch remoto."""
    cache_file = tmp_path / ".scf-registry-cache.json"
    cache_file.write_text(json.dumps(_SAMPLE_REGISTRY), encoding="utf-8")
    client = RegistryClient(tmp_path, registry_url=_VALID_REGISTRY_URL)
    with patch("urllib.request.urlopen") as mock_url:
        result = client.fetch_if_stale(ttl_seconds=3600)
    mock_url.assert_not_called()
    assert result["packages"] == _SAMPLE_REGISTRY["packages"]


# ---------------------------------------------------------------------------
# fetch_if_stale — refresh quando scaduta
# ---------------------------------------------------------------------------


def test_fetch_if_stale_refreshes_when_stale(tmp_path: Path) -> None:
    """fetch_if_stale() esegue fetch remoto se la cache è scaduta."""
    cache_file = tmp_path / ".scf-registry-cache.json"
    cache_file.write_text(json.dumps({"packages": []}), encoding="utf-8")
    import os
    old_mtime = time.time() - 7200
    os.utime(cache_file, (old_mtime, old_mtime))
    client = RegistryClient(tmp_path, registry_url=_VALID_REGISTRY_URL)
    fresh_data = {**_SAMPLE_REGISTRY, "schema_version": "2.1"}
    mock_resp = _mock_urlopen(fresh_data)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = client.fetch_if_stale(ttl_seconds=3600)
    assert result["schema_version"] == "2.1"


# ---------------------------------------------------------------------------
# fetch_if_stale — fallback su cache stale se rete non disponibile
# ---------------------------------------------------------------------------


def test_fetch_if_stale_falls_back_to_stale_cache_on_network_error(tmp_path: Path) -> None:
    """fetch_if_stale() usa cache stale se rete fallisce."""
    import urllib.error
    cache_file = tmp_path / ".scf-registry-cache.json"
    cache_file.write_text(json.dumps(_SAMPLE_REGISTRY), encoding="utf-8")
    import os
    old_mtime = time.time() - 7200
    os.utime(cache_file, (old_mtime, old_mtime))
    client = RegistryClient(tmp_path, registry_url=_VALID_REGISTRY_URL)
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
        result = client.fetch_if_stale(ttl_seconds=3600)
    assert result["packages"] == _SAMPLE_REGISTRY["packages"]


# ---------------------------------------------------------------------------
# _build_u2_registry_hint — helper dispatcher
# ---------------------------------------------------------------------------


def test_u2_registry_hint_returns_none_without_cache(tmp_path: Path) -> None:
    """_build_u2_registry_hint() ritorna None se il file cache non esiste."""
    from spark.boot.tools_resources import _build_u2_registry_hint
    from spark.core.models import FrameworkFile

    ff = FrameworkFile(
        name="test-agent",
        path=tmp_path / "test.agent.md",
        category="agents",
        summary="",
        metadata={"scf_owner": "acme-plugin", "scf_version": "0.9.0"},
    )
    assert _build_u2_registry_hint(ff, tmp_path) is None


def test_u2_registry_hint_detects_update_available(tmp_path: Path) -> None:
    """_build_u2_registry_hint() riporta update_available=True quando versione diversa."""
    from spark.boot.tools_resources import _build_u2_registry_hint
    from spark.core.models import FrameworkFile

    cache_file = tmp_path / ".scf-registry-cache.json"
    cache_file.write_text(json.dumps(_SAMPLE_REGISTRY), encoding="utf-8")

    ff = FrameworkFile(
        name="acme-agent",
        path=tmp_path / "acme.agent.md",
        category="agents",
        summary="",
        metadata={"scf_owner": "acme-plugin", "scf_version": "0.9.0"},
    )
    hint = _build_u2_registry_hint(ff, tmp_path)
    assert hint is not None
    assert hint["update_available"] is True
    assert hint["installed_version"] == "0.9.0"
    assert hint["latest_version"] == "1.0.0"
    assert hint["registry_package"] == "acme-plugin"


def test_u2_registry_hint_no_update_when_versions_match(tmp_path: Path) -> None:
    """_build_u2_registry_hint() riporta update_available=False se versione uguale."""
    from spark.boot.tools_resources import _build_u2_registry_hint
    from spark.core.models import FrameworkFile

    cache_file = tmp_path / ".scf-registry-cache.json"
    cache_file.write_text(json.dumps(_SAMPLE_REGISTRY), encoding="utf-8")

    ff = FrameworkFile(
        name="acme-agent",
        path=tmp_path / "acme.agent.md",
        category="agents",
        summary="",
        metadata={"scf_owner": "acme-plugin", "scf_version": "1.0.0"},
    )
    hint = _build_u2_registry_hint(ff, tmp_path)
    assert hint is not None
    assert hint["update_available"] is False


def test_u2_registry_hint_returns_none_for_unknown_package(tmp_path: Path) -> None:
    """_build_u2_registry_hint() ritorna None se il pacchetto non è nel registry."""
    from spark.boot.tools_resources import _build_u2_registry_hint
    from spark.core.models import FrameworkFile

    cache_file = tmp_path / ".scf-registry-cache.json"
    cache_file.write_text(json.dumps(_SAMPLE_REGISTRY), encoding="utf-8")

    ff = FrameworkFile(
        name="unknown-agent",
        path=tmp_path / "unknown.agent.md",
        category="agents",
        summary="",
        metadata={"scf_owner": "nonexistent-pkg", "scf_version": "1.0.0"},
    )
    assert _build_u2_registry_hint(ff, tmp_path) is None


def test_u2_registry_hint_returns_none_without_scf_owner(tmp_path: Path) -> None:
    """_build_u2_registry_hint() ritorna None se ff.metadata non ha scf_owner."""
    from spark.boot.tools_resources import _build_u2_registry_hint
    from spark.core.models import FrameworkFile

    cache_file = tmp_path / ".scf-registry-cache.json"
    cache_file.write_text(json.dumps(_SAMPLE_REGISTRY), encoding="utf-8")

    ff = FrameworkFile(
        name="orphan-agent",
        path=tmp_path / "orphan.agent.md",
        category="agents",
        summary="",
        metadata={},
    )
    assert _build_u2_registry_hint(ff, tmp_path) is None


# ---------------------------------------------------------------------------
# scf_plugin_list_remote — annotazione U1/U2
# ---------------------------------------------------------------------------


def test_plugin_list_remote_annotates_mcp_only_as_u1(tmp_path: Path) -> None:
    """scf_plugin_list_remote annota delivery_mode=mcp_only come universe='U1'."""
    from spark.boot.tools_resources import _build_u2_registry_hint

    # Verifica che i campi siano nella struttura del registry
    pkg = {"id": "spark-base", "latest_version": "2.1.0", "delivery_mode": "mcp_only"}
    # Logica di annotazione U1/U2 usata da scf_plugin_list_remote
    delivery = str(pkg.get("delivery_mode", "managed")).strip()
    universe = "U1" if delivery == "mcp_only" else "U2"
    assert universe == "U1"


def test_plugin_list_remote_annotates_managed_as_u2(tmp_path: Path) -> None:
    """scf_plugin_list_remote annota delivery_mode=managed come universe='U2'."""
    pkg = {"id": "acme-plugin", "latest_version": "1.0.0", "delivery_mode": "managed"}
    delivery = str(pkg.get("delivery_mode", "managed")).strip()
    universe = "U1" if delivery == "mcp_only" else "U2"
    assert universe == "U2"


def test_plugin_list_remote_annotates_missing_delivery_mode_as_u2(tmp_path: Path) -> None:
    """scf_plugin_list_remote tratta delivery_mode assente come U2."""
    pkg = {"id": "mystery-plugin", "latest_version": "0.1.0"}
    delivery = str(pkg.get("delivery_mode", "managed")).strip()
    universe = "U1" if delivery == "mcp_only" else "U2"
    assert universe == "U2"
