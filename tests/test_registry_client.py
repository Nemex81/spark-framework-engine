"""Tests per spark.registry.client.RegistryClient.

Copre fetch, list_packages, _load_cache, _save_cache,
fetch_package_manifest e fetch_raw_file tramite mock
(nessuna chiamata di rete reale).
"""
from __future__ import annotations

import json
import urllib.error
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from spark.registry.client import RegistryClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_REGISTRY: dict[str, Any] = {
    "schema_version": "2.0",
    "packages": [
        {"id": "spark-base", "latest_version": "1.6.1"},
        {"id": "scf-master-codecrafter", "latest_version": "2.5.1"},
    ],
}
_SAMPLE_MANIFEST: dict[str, Any] = {
    "id": "spark-base",
    "version": "1.6.1",
    "min_engine_version": "3.4.0",
}

_VALID_REGISTRY_URL = "https://raw.githubusercontent.com/Nemex81/spark-framework-engine/main/registry.json"
_PRIVATE_URL = "https://registry.internal/packages.json"
_VALID_GITHUB_REPO = "https://github.com/Nemex81/spark-base"


# ---------------------------------------------------------------------------
# __init__ / cache_path
# ---------------------------------------------------------------------------


def test_registry_client_uses_supplied_cache_path(tmp_path: Path) -> None:
    """Se cache_path è passato esplicitamente, viene usato al posto del default."""
    custom_cache = tmp_path / "custom.json"
    client = RegistryClient(tmp_path, cache_path=custom_cache)
    assert client._cache_path == custom_cache


def test_registry_client_defaults_cache_to_github_root(tmp_path: Path) -> None:
    """Senza cache_path, il default è github_root/.scf-registry-cache.json."""
    client = RegistryClient(tmp_path)
    assert client._cache_path == tmp_path / ".scf-registry-cache.json"


# ---------------------------------------------------------------------------
# fetch — URL validation
# ---------------------------------------------------------------------------


def test_fetch_raises_value_error_on_private_url(tmp_path: Path) -> None:
    """fetch() solleva ValueError per URL non-raw.githubusercontent.com."""
    client = RegistryClient(tmp_path, registry_url=_PRIVATE_URL)
    with pytest.raises(ValueError, match="not supported"):
        client.fetch()


# ---------------------------------------------------------------------------
# fetch — network success path
# ---------------------------------------------------------------------------


def test_fetch_returns_remote_data_and_writes_cache(tmp_path: Path) -> None:
    """fetch() restituisce dati remoti e scrive la cache su disco."""
    cache_file = tmp_path / "cache.json"
    client = RegistryClient(tmp_path, registry_url=_VALID_REGISTRY_URL, cache_path=cache_file)

    with patch.object(client, "_fetch_remote", return_value=_SAMPLE_REGISTRY):
        result = client.fetch()

    assert result == _SAMPLE_REGISTRY
    assert cache_file.is_file()
    saved = json.loads(cache_file.read_text(encoding="utf-8"))
    assert saved["schema_version"] == "2.0"


# ---------------------------------------------------------------------------
# fetch — network failure → cache fallback
# ---------------------------------------------------------------------------


def test_fetch_falls_back_to_cache_on_url_error(tmp_path: Path) -> None:
    """fetch() cade sul cache se la rete fallisce con URLError."""
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(json.dumps(_SAMPLE_REGISTRY), encoding="utf-8")
    client = RegistryClient(tmp_path, registry_url=_VALID_REGISTRY_URL, cache_path=cache_file)

    with patch.object(client, "_fetch_remote", side_effect=urllib.error.URLError("timeout")):
        result = client.fetch()

    assert result["schema_version"] == "2.0"
    assert len(result["packages"]) == 2


# ---------------------------------------------------------------------------
# list_packages
# ---------------------------------------------------------------------------


def test_list_packages_returns_packages_array(tmp_path: Path) -> None:
    """list_packages() restituisce la lista dei pacchetti dal registry."""
    client = RegistryClient(tmp_path, registry_url=_VALID_REGISTRY_URL)

    with patch.object(client, "fetch", return_value=_SAMPLE_REGISTRY):
        packages = client.list_packages()

    assert len(packages) == 2
    assert packages[0]["id"] == "spark-base"


def test_list_packages_returns_empty_list_on_runtime_error(tmp_path: Path) -> None:
    """list_packages() restituisce [] se fetch() solleva RuntimeError (cache mancante)."""
    client = RegistryClient(tmp_path, registry_url=_VALID_REGISTRY_URL)

    with patch.object(client, "fetch", side_effect=RuntimeError("no cache")):
        packages = client.list_packages()

    assert packages == []


# ---------------------------------------------------------------------------
# _load_cache
# ---------------------------------------------------------------------------


def test_load_cache_raises_runtime_if_no_cache_file(tmp_path: Path) -> None:
    """_load_cache() solleva RuntimeError se il file cache non esiste."""
    cache_file = tmp_path / "missing.json"
    client = RegistryClient(tmp_path, cache_path=cache_file)

    with pytest.raises(RuntimeError, match="no local cache found"):
        client._load_cache()


def test_load_cache_raises_runtime_on_corrupted_json(tmp_path: Path) -> None:
    """_load_cache() solleva RuntimeError su JSON malformato."""
    cache_file = tmp_path / "corrupted.json"
    cache_file.write_text("{ not valid json ", encoding="utf-8")
    client = RegistryClient(tmp_path, cache_path=cache_file)

    with pytest.raises(RuntimeError, match="corrupted"):
        client._load_cache()


def test_load_cache_returns_data_on_valid_cache(tmp_path: Path) -> None:
    """_load_cache() restituisce i dati quando il file JSON è valido."""
    cache_file = tmp_path / "valid.json"
    cache_file.write_text(json.dumps(_SAMPLE_REGISTRY), encoding="utf-8")
    client = RegistryClient(tmp_path, cache_path=cache_file)

    result = client._load_cache()

    assert result["schema_version"] == "2.0"


# ---------------------------------------------------------------------------
# _save_cache
# ---------------------------------------------------------------------------


def test_save_cache_writes_json_to_disk(tmp_path: Path) -> None:
    """_save_cache() scrive il JSON correttamente su disco."""
    cache_file = tmp_path / "output.json"
    client = RegistryClient(tmp_path, cache_path=cache_file)

    client._save_cache(_SAMPLE_REGISTRY)

    saved = json.loads(cache_file.read_text(encoding="utf-8"))
    assert saved["schema_version"] == "2.0"


def test_save_cache_logs_warning_on_os_error(tmp_path: Path) -> None:
    """_save_cache() non solleva eccezioni su OSError — logga solo un warning."""
    cache_file = tmp_path / "readonly.json"
    client = RegistryClient(tmp_path, cache_path=cache_file)

    with patch.object(type(cache_file), "write_text", side_effect=OSError("read only")):
        # Deve completare senza eccezioni
        client._save_cache(_SAMPLE_REGISTRY)


# ---------------------------------------------------------------------------
# fetch_package_manifest
# ---------------------------------------------------------------------------


def test_fetch_package_manifest_raises_value_error_on_non_github_url(tmp_path: Path) -> None:
    """fetch_package_manifest() solleva ValueError per URL non github.com."""
    client = RegistryClient(tmp_path)

    with pytest.raises(ValueError, match="Unsupported repo URL"):
        client.fetch_package_manifest("https://gitlab.com/org/repo")


def test_fetch_package_manifest_returns_dict_from_raw_github(tmp_path: Path) -> None:
    """fetch_package_manifest() restituisce il manifest come dict."""
    client = RegistryClient(tmp_path)
    manifest_json = json.dumps(_SAMPLE_MANIFEST)

    with patch.object(client, "fetch_raw_file", return_value=manifest_json):
        result = client.fetch_package_manifest(_VALID_GITHUB_REPO)

    assert result["id"] == "spark-base"
    assert result["min_engine_version"] == "3.4.0"


def test_fetch_package_manifest_constructs_correct_raw_url(tmp_path: Path) -> None:
    """fetch_package_manifest() chiama fetch_raw_file con l'URL raw corretto."""
    client = RegistryClient(tmp_path)
    expected_raw_url = (
        "https://raw.githubusercontent.com/Nemex81/spark-base"
        "/main/package-manifest.json"
    )

    with patch.object(client, "fetch_raw_file", return_value=json.dumps(_SAMPLE_MANIFEST)) as mock_fetch:
        client.fetch_package_manifest(_VALID_GITHUB_REPO)

    mock_fetch.assert_called_once_with(expected_raw_url)


def test_fetch_package_manifest_raises_runtime_on_network_error(tmp_path: Path) -> None:
    """fetch_package_manifest() solleva RuntimeError se fetch_raw_file fallisce."""
    client = RegistryClient(tmp_path)

    with patch.object(client, "fetch_raw_file", side_effect=urllib.error.URLError("timeout")):
        with pytest.raises(RuntimeError, match="Cannot fetch package manifest"):
            client.fetch_package_manifest(_VALID_GITHUB_REPO)


def test_fetch_package_manifest_raises_runtime_on_bad_json(tmp_path: Path) -> None:
    """fetch_package_manifest() solleva RuntimeError su risposta JSON non valida."""
    client = RegistryClient(tmp_path)

    with patch.object(client, "fetch_raw_file", return_value="NOT JSON {{{{"):
        with pytest.raises(RuntimeError, match="Cannot fetch package manifest"):
            client.fetch_package_manifest(_VALID_GITHUB_REPO)


# ---------------------------------------------------------------------------
# fetch_raw_file
# ---------------------------------------------------------------------------


def test_fetch_raw_file_returns_content_from_url(tmp_path: Path) -> None:
    """fetch_raw_file() restituisce il testo grezzo dalla URL."""
    client = RegistryClient(tmp_path)
    raw_url = "https://raw.githubusercontent.com/org/repo/main/file.md"
    expected_content = "# Hello\n"

    mock_resp = MagicMock()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = expected_content.encode("utf-8")

    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = client.fetch_raw_file(raw_url)

    assert result == expected_content


# ---------------------------------------------------------------------------
# _fetch_remote — direct urlopen coverage
# ---------------------------------------------------------------------------


def test_fetch_remote_calls_urlopen_and_returns_parsed_json(tmp_path: Path) -> None:
    """_fetch_remote() chiama urlopen e restituisce il JSON parsato."""
    client = RegistryClient(
        tmp_path,
        registry_url=_VALID_REGISTRY_URL,
    )
    mock_resp = MagicMock()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = json.dumps(_SAMPLE_REGISTRY).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = client._fetch_remote()

    assert result["schema_version"] == "2.0"
    assert len(result["packages"]) == 2


def test_fetch_remote_sends_user_agent_header(tmp_path: Path) -> None:
    """_fetch_remote() invia un header User-Agent contenente 'spark-framework-engine'."""
    client = RegistryClient(
        tmp_path,
        registry_url=_VALID_REGISTRY_URL,
    )
    mock_resp = MagicMock()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = json.dumps(_SAMPLE_REGISTRY).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        client._fetch_remote()

    called_req = mock_urlopen.call_args[0][0]
    assert "spark-framework-engine" in called_req.get_header("User-agent")
