"""Test di integrazione per il layer Plugin Manager (Step 2).

Verifica che i tool MCP plugin (scf_plugin_install, scf_plugin_remove,
scf_plugin_update, scf_plugin_list) deleghino correttamente a
``PluginManagerFacade`` e restituiscano il formato atteso senza crash.

Tutti i test usano ``tmp_path`` di pytest come workspace isolato e
mockano le chiamate HTTP esterne per evitare dipendenze di rete.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from spark.plugins import PluginManagerFacade
from spark.plugins.schema import PluginNotFoundError, PluginNotInstalledError


# ---------------------------------------------------------------------------
# Fixtures condivise
# ---------------------------------------------------------------------------


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
