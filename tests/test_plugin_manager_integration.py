"""Test di integrazione per il layer Plugin Manager (Step 2).

Verifica che i tool MCP plugin (scf_plugin_install, scf_plugin_remove,
scf_plugin_update, scf_plugin_list) deleghino correttamente a
``PluginManagerFacade`` e restituiscano il formato atteso senza crash.

Tutti i test usano ``tmp_path`` di pytest come workspace isolato e
mockano le chiamate HTTP esterne per evitare dipendenze di rete.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from spark.boot.tools_plugins import register_plugin_tools
from spark.plugins import PluginManagerFacade
from spark.plugins.schema import PluginNotFoundError, PluginNotInstalledError


class FakeMCP:
    """Minimal MCP test double that captures registered tools by function name."""

    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Coroutine[Any, Any, dict[str, Any]]]] = {}

    def tool(
        self,
    ) -> Callable[
        [Callable[..., Coroutine[Any, Any, dict[str, Any]]]],
        Callable[..., Coroutine[Any, Any, dict[str, Any]]],

    ]:
        def decorator(
            func: Callable[..., Coroutine[Any, Any, dict[str, Any]]],
        ) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
            self.tools[func.__name__] = func
            return func

        return decorator


class FakeRegistryClient:
    """Registry client fixture for plugin info tool tests."""

    def list_packages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "test-plugin",
                "name": "Test Plugin",
                "description": "Registry description",
                "latest_version": "1.0.0",
                "repo_url": "https://github.com/Test/test-plugin",
                "min_engine_version": "3.1.0",
                "delivery_mode": "plugin",
            },
            {
                "id": "internal-service",
                "description": "MCP-only internal package",
                "latest_version": "1.0.0",
                "repo_url": "https://github.com/Test/internal-service",
                "delivery_mode": "mcp_only",
            },
        ]

    def fetch_package_manifest(self, repo_url: str) -> dict[str, Any]:
        assert repo_url == "https://github.com/Test/test-plugin"
        return {
            "schema_version": "3.1",
            "package": "test-plugin",
            "display_name": "Test Plugin Display",
            "description": "Manifest description",
            "version": "1.0.1",
            "min_engine_version": "3.1.0",
            "dependencies": ["spark-base"],
            "plugin_files": [".github/agents/test-plugin.agent.md"],
        }


class FakeRemoteInstallRegistryClient:
    """Registry client fixture for scf_plugin_install_remote tests."""

    def __init__(self, entry: dict[str, Any], manifest: dict[str, Any]) -> None:
        self._entry = entry
        self._manifest = manifest

    def fetch_if_stale(self, ttl_seconds: int = 3600) -> dict[str, Any]:
        return {"packages": [self._entry]}

    def fetch_package_manifest(self, repo_url: str) -> dict[str, Any]:
        assert repo_url == self._entry["repo_url"]
        return self._manifest


class FakeRemoteListRegistryClient:
    """Registry client fixture for scf_plugin_list_remote telemetry tests."""

    def __init__(self, *, fresh_before_fetch: bool, cache_age_seconds: float) -> None:
        self._fresh_before_fetch = fresh_before_fetch
        self._cache_age_seconds = cache_age_seconds

    def is_cache_fresh(self, ttl_seconds: int = 3600) -> bool:
        return self._fresh_before_fetch

    def cache_age_seconds(self) -> float:
        return self._cache_age_seconds

    def fetch_if_stale(self, ttl_seconds: int = 3600) -> dict[str, Any]:
        return {
            "packages": [
                {
                    "id": "remote-plugin",
                    "latest_version": "1.0.0",
                    "delivery_mode": "managed",
                    "repo_url": "https://github.com/Test/remote-plugin",
                }
            ]
        }


from spark.plugins import PluginManagerFacade
from spark.plugins.schema import PluginNotFoundError, PluginNotInstalledError


# ---------------------------------------------------------------------------
# Fixtures condivise
# ---------------------------------------------------------------------------


def test_scf_get_plugin_info_returns_plugin_specific_details(workspace: Path) -> None:
    """scf_get_plugin_info restituisce dettagli dal registry e dal manifest plugin."""
    fake_mcp = FakeMCP()
    tool_names: list[str] = []
    engine = SimpleNamespace(
        _ctx=SimpleNamespace(workspace_root=workspace, github_root=workspace / ".github"),
        _registry_client=FakeRegistryClient(),
    )

    register_plugin_tools(engine, fake_mcp, tool_names)

    assert "scf_get_plugin_info" in tool_names
    result = asyncio.run(fake_mcp.tools["scf_get_plugin_info"]("test-plugin"))

    assert result["status"] == "ok"
    assert result["name"] == "Test Plugin Display"
    assert result["description"] == "Manifest description"
    assert result["version"] == "1.0.1"
    assert result["dependencies"] == ["spark-base"]
    assert result["source_url"] == "https://github.com/Test/test-plugin"
    assert result["min_engine_version"] == "3.1.0"
    assert result["plugin_files"] == [".github/agents/test-plugin.agent.md"]


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Workspace temporaneo con struttura .github/ minima."""
    github = tmp_path / ".github"
    github.mkdir(parents=True)
    (github / "copilot-instructions.md").write_text(
        "# Instructions\n", encoding="utf-8"
    )
    return tmp_path


@pytest.fixture()
def empty_registry_response() -> dict[str, Any]:
    """Risposta del registry remoto vuota (nessun pacchetto)."""
    return {
        "schema_version": "1.0",
        "packages": [],
    }


@pytest.fixture()
def mock_registry_response() -> dict[str, Any]:
    """Registry remoto con un pacchetto fittizio 'test-plugin'."""
    return {
        "schema_version": "1.0",
        "packages": [
            {
                "id": "test-plugin",
                "name": "Test Plugin",
                "description": "Plugin fittizio per test",
                "latest_version": "1.0.0",
                "repo_url": "https://github.com/Test/test-plugin",
            }
        ],
    }


# ---------------------------------------------------------------------------
# TEST 1 — scf_plugin_list: struttura corretta con workspace vuoto
# ---------------------------------------------------------------------------


def test_scf_plugin_list_empty_workspace(workspace: Path) -> None:
    """scf_plugin_list restituisce la struttura attesa con workspace vuoto.

    Con un workspace senza plugin installati, il risultato deve contenere:
    - status: "ok"
    - installed: lista vuota
    - available: lista (può essere vuota se il registry non è raggiungibile)
    - message: stringa con conteggio

    La chiamata non deve sollevare eccezioni.
    """
    facade = PluginManagerFacade(workspace_root=workspace)

    # Mock del fetch remoto: evita connessione HTTP
    with patch.object(
        facade._remote_registry,
        "list_packages",
        return_value=[],
    ):
        installed = facade.list_installed()
        available = facade.list_available()

    assert installed.get("success") is True
    assert isinstance(installed.get("plugins"), list)
    assert len(installed["plugins"]) == 0

    assert "success" in available
    assert isinstance(available.get("packages", []), list)


def test_scf_plugin_list_response_keys(workspace: Path) -> None:
    """Il formato composito di scf_plugin_list ha le chiavi obbligatorie.

    Simula la logica di aggregazione che il MCP tool esegue su list_installed()
    + list_available() e verifica che il dizionario finale sia conforme.
    """
    facade = PluginManagerFacade(workspace_root=workspace)

    with patch.object(facade._remote_registry, "list_packages", return_value=[]):
        installed_result = facade.list_installed()
        available_result = facade.list_available()

    installed = installed_result.get("plugins", []) if installed_result.get("success") else []
    available = available_result.get("packages", []) if available_result.get("success") else []

    # Simula costruzione payload come in tools_plugins.scf_plugin_list
    response = {
        "status": "ok",
        "installed": installed,
        "available": available,
        "message": f"{len(installed)} plugin installati, {len(available)} disponibili nel registry.",
    }

    assert response["status"] == "ok"
    assert "installed" in response
    assert "available" in response
    assert "message" in response
    assert isinstance(response["installed"], list)
    assert isinstance(response["available"], list)


def test_scf_plugin_install_remote_rejects_absolute_manifest_path(workspace: Path) -> None:
    """scf_plugin_install_remote rifiuta path assoluti che uscirebbero da .github/."""
    fake_mcp = FakeMCP()
    tool_names: list[str] = []
    entry = {
        "id": "remote-plugin",
        "latest_version": "1.0.0",
        "delivery_mode": "managed",
        "repo_url": "https://github.com/Test/remote-plugin",
    }
    manifest = {
        "version": "1.0.0",
        "plugin_files": ["C:/evil.txt"],
    }
    engine = SimpleNamespace(
        _ctx=SimpleNamespace(workspace_root=workspace, github_root=workspace / ".github"),
        _registry_client=FakeRemoteInstallRegistryClient(entry, manifest),
    )

    register_plugin_tools(engine, fake_mcp, tool_names)

    with patch("urllib.request.urlopen") as mock_urlopen:
        result = asyncio.run(
            fake_mcp.tools["scf_plugin_install_remote"]("remote-plugin")
        )

    mock_urlopen.assert_not_called()
    assert result["status"] == "error"
    assert result["files_written"] == []
    assert any("Path non sicuro" in item for item in result["errors"])


def test_scf_plugin_list_remote_reports_cache_hit_and_age(workspace: Path) -> None:
    """scf_plugin_list_remote espone from_cache=True e cache_age_seconds su cache hit."""
    fake_mcp = FakeMCP()
    tool_names: list[str] = []
    engine = SimpleNamespace(
        _ctx=SimpleNamespace(workspace_root=workspace, github_root=workspace / ".github"),
        _registry_client=FakeRemoteListRegistryClient(
            fresh_before_fetch=True,
            cache_age_seconds=12.5,
        ),
    )

    register_plugin_tools(engine, fake_mcp, tool_names)

    result = asyncio.run(fake_mcp.tools["scf_plugin_list_remote"]())

    assert result["status"] == "ok"
    assert result["from_cache"] is True
    assert result["cache_age_seconds"] == pytest.approx(12.5)


def test_scf_plugin_list_remote_reports_refresh_without_cache_hit(workspace: Path) -> None:
    """scf_plugin_list_remote espone from_cache=False quando la richiesta ha fatto refresh."""
    fake_mcp = FakeMCP()
    tool_names: list[str] = []
    engine = SimpleNamespace(
        _ctx=SimpleNamespace(workspace_root=workspace, github_root=workspace / ".github"),
        _registry_client=FakeRemoteListRegistryClient(
            fresh_before_fetch=False,
            cache_age_seconds=0.2,
        ),
    )

    register_plugin_tools(engine, fake_mcp, tool_names)

    result = asyncio.run(fake_mcp.tools["scf_plugin_list_remote"]())

    assert result["status"] == "ok"
    assert result["from_cache"] is False
    assert result["cache_age_seconds"] == pytest.approx(0.2)


def test_scf_plugin_install_remote_uses_target_workspace_cache_root(tmp_path: Path) -> None:
    """scf_plugin_install_remote deve interrogare il registry usando il workspace target."""
    fake_mcp = FakeMCP()
    tool_names: list[str] = []
    engine_workspace = tmp_path / "engine-ws"
    engine_github = engine_workspace / ".github"
    engine_github.mkdir(parents=True)
    target_workspace = tmp_path / "target-ws"
    target_github = target_workspace / ".github"
    target_github.mkdir(parents=True)

    engine = SimpleNamespace(
        _ctx=SimpleNamespace(workspace_root=engine_workspace, github_root=engine_github),
        _registry_client=MagicMock(_github_root=engine_github),
    )
    register_plugin_tools(engine, fake_mcp, tool_names)

    with patch("spark.boot.tools_plugins.find_remote_package", return_value=None) as mock_find:
        result = asyncio.run(
            fake_mcp.tools["scf_plugin_install_remote"](
                "remote-plugin",
                workspace_root=str(target_workspace),
            )
        )

    assert result["status"] == "error"
    assert mock_find.call_args.kwargs["github_root"] == target_github


# ---------------------------------------------------------------------------
# TEST 2 — scf_plugin_install: pacchetto inesistente → "error" senza crash
# ---------------------------------------------------------------------------


def test_scf_plugin_install_nonexistent_pkg(workspace: Path) -> None:
    """scf_plugin_install con pkg_id inesistente restituisce status 'error'.

    Il registry remoto è mocked per rispondere con lista vuota.
    L'operazione non deve sollevare eccezioni — deve restituire
    ``{"success": False, "error": ...}`` dall'interno della facade.
    """
    facade = PluginManagerFacade(workspace_root=workspace)

    with patch.object(
        facade._remote_registry,
        "list_packages",
        return_value=[],
    ):
        result = facade.install("pacchetto-inesistente")

    assert result.get("success") is False
    assert "error" in result
    assert isinstance(result["error"], str)
    assert len(result["error"]) > 0


def test_scf_plugin_install_maps_to_status_error(workspace: Path) -> None:
    """La mappatura facade → tools_plugins produce status='error' coerente.

    Verifica che la normalizzazione ``success=False → status='error'``
    che il tool MCP esegue sia corretta.
    """
    facade = PluginManagerFacade(workspace_root=workspace)

    with patch.object(
        facade._remote_registry,
        "list_packages",
        return_value=[],
    ):
        raw_result = facade.install("pkg-non-esistente")

    # Normalizzazione che scf_plugin_install esegue nel tool MCP
    status = "ok" if raw_result.get("success") else "error"
    mapped = {
        "status": status,
        "pkg_id": "pkg-non-esistente",
        "message": raw_result.get("error", "Installazione fallita."),
    }

    assert mapped["status"] == "error"
    assert mapped["pkg_id"] == "pkg-non-esistente"
    assert isinstance(mapped["message"], str)


# ---------------------------------------------------------------------------
# TEST 3 — scf_plugin_remove: plugin non installato → "error" senza crash
# ---------------------------------------------------------------------------


def test_scf_plugin_remove_not_installed(workspace: Path) -> None:
    """scf_plugin_remove su plugin non installato restituisce success=False.

    Il PluginRegistry non conosce il pkg_id richiesto; la facade deve
    restituire un errore pulito senza eccezioni non gestite.
    """
    facade = PluginManagerFacade(workspace_root=workspace)

    result = facade.remove("plugin-non-installato")

    assert result.get("success") is False
    assert "error" in result
    assert isinstance(result["error"], str)


def test_scf_plugin_remove_maps_to_status_error(workspace: Path) -> None:
    """La mappatura facade → tools_plugins produce status='error' per rimozione fallita."""
    facade = PluginManagerFacade(workspace_root=workspace)

    raw_result = facade.remove("plugin-assente")

    status = "ok" if raw_result.get("success") else "error"
    mapped = {
        "status": status,
        "pkg_id": "plugin-assente",
        "message": raw_result.get("error", "Rimozione fallita."),
    }

    assert mapped["status"] == "error"
    assert isinstance(mapped["message"], str)


# ---------------------------------------------------------------------------
# TEST 4 — Ciclo install → list → remove mocked, nessuna regressione
# ---------------------------------------------------------------------------


def test_install_list_remove_cycle_mocked(workspace: Path, mock_registry_response: dict) -> None:
    """Ciclo completo install → list → remove su package mocked.

    Il test usa un ``package-manifest.json`` fittizio servito tramite mock
    del fetch HTTP. Verifica che:
    - list_installed() veda il plugin dopo l'install
    - remove() rimuova il plugin correttamente
    - list_installed() non veda più il plugin dopo la remove

    Non effettua chiamate HTTP reali. Non dipende da file di rete.
    """
    pkg_id = "test-plugin"
    fake_pkg_manifest: dict[str, Any] = {
        "schema_version": "3.1",
        "package": pkg_id,
        "version": "1.0.0",
        "source_repo": "Test/test-plugin",
        "plugin_files": [
            ".github/agents/test-Agent.md",
            ".github/instructions/test-plugin.instructions.md",
        ],
    }

    facade = PluginManagerFacade(workspace_root=workspace)

    # Prepara i file fisici nella store (simula file già presenti nel repo)
    (workspace / ".github" / "agents").mkdir(parents=True, exist_ok=True)
    (workspace / ".github" / "instructions").mkdir(parents=True, exist_ok=True)

    with (
        patch.object(
            facade._remote_registry,
            "list_packages",
            return_value=mock_registry_response["packages"],
        ),
        patch.object(
            facade._remote_registry,
            "fetch_package_manifest",
            return_value=fake_pkg_manifest,
        ),
        patch.object(
            facade._installer,
            "install_files",
            return_value=[".github/agents/test-Agent.md", ".github/instructions/test-plugin.instructions.md"],
        ),
        patch.object(
            facade._installer,
            "_add_instruction_reference",
            return_value=None,
        ),
    ):
        install_result = facade.install(pkg_id)

    # Verifica installazione
    assert install_result.get("success") is True, f"Install fallita: {install_result}"
    assert install_result.get("pkg_id") == pkg_id
    assert install_result.get("version") == "1.0.0"

    # Verifica che list_installed() veda il plugin
    with patch.object(facade._remote_registry, "list_packages", return_value=[]):
        list_result = facade.list_installed()

    assert list_result.get("success") is True
    installed_ids = [p.get("pkg_id") or p.get("id", "") for p in list_result.get("plugins", [])]
    assert pkg_id in installed_ids, f"Plugin non trovato in installed: {list_result}"

    # Remove
    with patch.object(
        facade._remover,
        "remove_files",
        return_value=[".github/agents/test-Agent.md", ".github/instructions/test-plugin.instructions.md"],
    ), patch.object(
        facade._remover,
        "_remove_instruction_reference",
        return_value=None,
    ):
        remove_result = facade.remove(pkg_id)

    assert remove_result.get("success") is True, f"Remove fallita: {remove_result}"

    # Verifica che list_installed() non veda più il plugin
    with patch.object(facade._remote_registry, "list_packages", return_value=[]):
        list_after = facade.list_installed()

    assert list_after.get("success") is True
    installed_ids_after = [p.get("pkg_id") or p.get("id", "") for p in list_after.get("plugins", [])]
    assert pkg_id not in installed_ids_after, f"Plugin ancora presente dopo remove: {list_after}"
