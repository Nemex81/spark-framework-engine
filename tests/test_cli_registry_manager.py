"""tests.test_cli_registry_manager — Test unitari per spark.cli.registry_manager.

Coprono: sfoglio plugin, installazione, verifica aggiornamenti,
graceful degradation su registro non raggiungibile.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from spark.cli.registry_manager import RegistryManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_REGISTRY = {
    "schema_version": "2.0",
    "packages": [
        {
            "id": "my-plugin",
            "latest_version": "1.0.0",
            "description": "Plugin di test",
            "repo_url": "https://github.com/Nemex81/my-plugin",
            "manifest_path": "package-manifest.json",
        },
        {
            "id": "other-plugin",
            "latest_version": "2.3.0",
            "description": "Altro plugin",
            "repo_url": "https://github.com/Nemex81/other-plugin",
            "manifest_path": "package-manifest.json",
        },
    ],
}

_SAMPLE_PLUGIN_MANIFEST = {
    "package": "my-plugin",
    "version": "1.0.0",
    "workspace_files": [".github/agents/my-agent.md"],
}


def _make_mgr(tmp_path: Path) -> RegistryManager:
    """Crea un RegistryManager con directories fittizie."""
    github_root = tmp_path / ".github"
    github_root.mkdir()
    engine_root = tmp_path / "engine"
    engine_root.mkdir()
    return RegistryManager(github_root, engine_root)


# ---------------------------------------------------------------------------
# Test _load_registry
# ---------------------------------------------------------------------------


class TestLoadRegistry:
    """Test per RegistryManager._load_registry."""

    def test_returns_registry_on_success(self, tmp_path: Path) -> None:
        """Ritorna il registro parsato quando il download ha successo."""
        mgr = _make_mgr(tmp_path)
        raw_bytes = json.dumps(_SAMPLE_REGISTRY).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = raw_bytes

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = mgr._load_registry()

        assert result is not None
        assert len(result["packages"]) == 2

    def test_returns_none_on_url_error(self, tmp_path: Path) -> None:
        """Ritorna None e non lancia eccezione su URLError."""
        mgr = _make_mgr(tmp_path)
        with patch("urllib.request.urlopen", side_effect=URLError("offline")):
            result = mgr._load_registry()

        assert result is None

    def test_returns_none_on_invalid_json(self, tmp_path: Path) -> None:
        """Ritorna None se il JSON non è valido."""
        mgr = _make_mgr(tmp_path)
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = b"not-valid-json!!!"

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = mgr._load_registry()

        assert result is None

    def test_caches_registry_after_first_load(self, tmp_path: Path) -> None:
        """La seconda chiamata usa la cache senza chiamare urlopen di nuovo."""
        mgr = _make_mgr(tmp_path)
        raw_bytes = json.dumps(_SAMPLE_REGISTRY).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = raw_bytes

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            mgr._load_registry()
            mgr._load_registry()
            assert mock_open.call_count == 1  # chiamato una sola volta


# ---------------------------------------------------------------------------
# Test _browse_plugins
# ---------------------------------------------------------------------------


class TestBrowsePlugins:
    """Test per RegistryManager._browse_plugins."""

    def test_prints_plugin_list(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Stampa la lista dei plugin quando il registro è disponibile."""
        mgr = _make_mgr(tmp_path)
        mgr._registry_cache = _SAMPLE_REGISTRY

        mgr._browse_plugins()

        out, _ = capsys.readouterr()
        assert "my-plugin" in out
        assert "other-plugin" in out

    def test_graceful_degradation_when_registry_unavailable(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Stampa messaggio di errore senza crash quando registro non disponibile."""
        mgr = _make_mgr(tmp_path)
        with patch("urllib.request.urlopen", side_effect=URLError("offline")):
            mgr._browse_plugins()

        out, _ = capsys.readouterr()
        assert "non raggiungibile" in out.lower() or "errore" in out.lower() or "connessione" in out.lower()


# ---------------------------------------------------------------------------
# Test _download_and_install_plugin
# ---------------------------------------------------------------------------


class TestDownloadAndInstallPlugin:
    """Test per RegistryManager._download_and_install_plugin."""

    def test_installs_plugin_files(self, tmp_path: Path) -> None:
        """Scarica e scrive i file del plugin nel github_root."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        mgr = RegistryManager(github_root, engine_root)

        plugin_entry = _SAMPLE_REGISTRY["packages"][0]
        manifest_bytes = json.dumps(_SAMPLE_PLUGIN_MANIFEST).encode("utf-8")
        file_bytes = b"AGENT-FILE-CONTENT"

        def fake_urlopen(url: str, timeout: int = 10):
            mock_resp = MagicMock()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            if "package-manifest.json" in url:
                mock_resp.read.return_value = manifest_bytes
            else:
                mock_resp.read.return_value = file_bytes
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = mgr._download_and_install_plugin(plugin_entry)

        assert result["success"] is True
        assert result["files_copied"] == 1
        dest = github_root / "agents" / "my-agent.md"
        assert dest.is_file()
        assert dest.read_bytes() == file_bytes

    def test_skips_existing_files_without_force(self, tmp_path: Path) -> None:
        """Con force=False salta i file già presenti."""
        github_root = tmp_path / ".github"
        existing_dir = github_root / "agents"
        existing_dir.mkdir(parents=True)
        existing_file = existing_dir / "my-agent.md"
        existing_file.write_text("EXISTING", encoding="utf-8")

        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        mgr = RegistryManager(github_root, engine_root)

        plugin_entry = _SAMPLE_REGISTRY["packages"][0]
        manifest_bytes = json.dumps(_SAMPLE_PLUGIN_MANIFEST).encode("utf-8")

        def fake_urlopen(url: str, timeout: int = 10):
            mock_resp = MagicMock()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = manifest_bytes
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = mgr._download_and_install_plugin(plugin_entry, force=False)

        assert result["success"] is True
        assert result["files_copied"] == 0
        assert existing_file.read_text(encoding="utf-8") == "EXISTING"

    def test_overwrites_with_force(self, tmp_path: Path) -> None:
        """Con force=True sovrascrive i file già presenti."""
        github_root = tmp_path / ".github"
        existing_dir = github_root / "agents"
        existing_dir.mkdir(parents=True)
        existing_file = existing_dir / "my-agent.md"
        existing_file.write_text("OLD", encoding="utf-8")

        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        mgr = RegistryManager(github_root, engine_root)

        plugin_entry = _SAMPLE_REGISTRY["packages"][0]
        manifest_bytes = json.dumps(_SAMPLE_PLUGIN_MANIFEST).encode("utf-8")
        new_content = b"NEW-CONTENT"

        def fake_urlopen(url: str, timeout: int = 10):
            mock_resp = MagicMock()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            if "package-manifest.json" in url:
                mock_resp.read.return_value = manifest_bytes
            else:
                mock_resp.read.return_value = new_content
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = mgr._download_and_install_plugin(plugin_entry, force=True)

        assert result["success"] is True
        assert result["files_copied"] == 1
        assert existing_file.read_bytes() == new_content

    def test_returns_error_when_manifest_unreachable(self, tmp_path: Path) -> None:
        """Ritorna success=False se il manifest del plugin non è scaricabile."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        mgr = RegistryManager(github_root, engine_root)

        plugin_entry = _SAMPLE_REGISTRY["packages"][0]

        with patch("urllib.request.urlopen", side_effect=URLError("offline")):
            result = mgr._download_and_install_plugin(plugin_entry)

        assert result["success"] is False
        assert "Impossibile scaricare manifest" in result.get("error", "")

    def test_incomplete_plugin_entry_returns_error(self, tmp_path: Path) -> None:
        """Ritorna success=False per entry registro con 'repo_url' mancante."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        mgr = RegistryManager(github_root, engine_root)

        bad_entry: dict = {"id": "bad-plugin"}  # senza 'repo_url'

        result = mgr._download_and_install_plugin(bad_entry)

        assert result["success"] is False


# ---------------------------------------------------------------------------
# Test _check_updates
# ---------------------------------------------------------------------------


class TestCheckUpdates:
    """Test per RegistryManager._check_updates."""

    def test_detects_available_update(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Mostra aggiornamento disponibile quando versione locale < remota."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        mgr = RegistryManager(github_root, engine_root)
        mgr._registry_cache = _SAMPLE_REGISTRY

        local_versions = {"my-plugin": "0.9.0"}
        with patch.object(mgr, "_read_local_plugin_versions", return_value=local_versions):
            mgr._check_updates()

        out, _ = capsys.readouterr()
        assert "my-plugin" in out
        assert "1.0.0" in out

    def test_reports_no_updates_when_all_current(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Mostra 'aggiornati' quando tutte le versioni coincidono."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        mgr = RegistryManager(github_root, engine_root)
        mgr._registry_cache = _SAMPLE_REGISTRY

        local_versions = {"my-plugin": "1.0.0", "other-plugin": "2.3.0"}
        with patch.object(mgr, "_read_local_plugin_versions", return_value=local_versions):
            mgr._check_updates()

        out, _ = capsys.readouterr()
        assert "aggiornati" in out.lower()


# ---------------------------------------------------------------------------
# Test _browse_plugins — latest_version in output
# ---------------------------------------------------------------------------


class TestBrowsePluginsLatestVersion:
    """Test aggiuntivi per _browse_plugins con struttura registro v2.0."""

    def test_browse_plugins_shows_latest_version(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Mostra il valore di latest_version per ogni pacchetto nella lista.

        Verifica che il campo ``latest_version`` venga letto e stampato
        correttamente dopo la correzione del mismatch chiavi JSON.
        """
        mgr = _make_mgr(tmp_path)
        mgr._registry_cache = _SAMPLE_REGISTRY

        mgr._browse_plugins()

        out, _ = capsys.readouterr()
        assert "1.0.0" in out   # latest_version di my-plugin
        assert "2.3.0" in out   # latest_version di other-plugin


# ---------------------------------------------------------------------------
# Test _install_plugin — repo_url passato a _download_and_install_plugin
# ---------------------------------------------------------------------------


class TestInstallPlugin:
    """Test per RegistryManager._install_plugin."""

    def test_install_plugin_uses_repo_url(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """_install_plugin passa l'entry con repo_url a _download_and_install_plugin.

        Verifica che, dopo la selezione dell'ID via input(), il metodo chiami
        ``_download_and_install_plugin`` con l'entry contenente ``repo_url``
        (chiave corretta del registro v2.0).
        """
        mgr = _make_mgr(tmp_path)
        mgr._registry_cache = _SAMPLE_REGISTRY  # packages[0].repo_url valorizzato

        with (
            patch("builtins.input", return_value="my-plugin"),
            patch.object(
                mgr,
                "_download_and_install_plugin",
                return_value={"success": True, "files_copied": 1, "error": ""},
            ) as mock_install,
        ):
            mgr._install_plugin()

        mock_install.assert_called_once()
        call_package = mock_install.call_args[0][0]
        assert call_package.get("repo_url") == "https://github.com/Nemex81/my-plugin"

    def test_install_plugin_not_found_prints_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Stampa messaggio di errore se il plugin_id non è nel registro.

        Verifica la graceful degradation quando l'utente inserisce un ID
        non presente nella lista ``packages`` del registro.
        """
        mgr = _make_mgr(tmp_path)
        mgr._registry_cache = _SAMPLE_REGISTRY

        with patch("builtins.input", return_value="nonexistent-plugin"):
            mgr._install_plugin()

        out, _ = capsys.readouterr()
        assert "non trovato" in out.lower()


# ---------------------------------------------------------------------------
# Fixture registri per test filtro engine_managed
# ---------------------------------------------------------------------------

_SAMPLE_ENGINE_MANAGED_REGISTRY = {
    "schema_version": "2.0",
    "packages": [
        {
            "id": "engine-pkg",
            "latest_version": "1.0.0",
            "description": "Gestito dall'engine",
            "repo_url": "https://github.com/Nemex81/engine-pkg",
            "manifest_path": "package-manifest.json",
            "engine_managed_resources": True,
        },
    ],
}

_SAMPLE_MIXED_REGISTRY = {
    "schema_version": "2.0",
    "packages": [
        {
            "id": "user-plugin",
            "latest_version": "1.5.0",
            "description": "Plugin utente",
            "repo_url": "https://github.com/Nemex81/user-plugin",
            "manifest_path": "package-manifest.json",
        },
        {
            "id": "engine-pkg",
            "latest_version": "2.0.0",
            "description": "Gestito dall'engine",
            "repo_url": "https://github.com/Nemex81/engine-pkg",
            "manifest_path": "package-manifest.json",
            "engine_managed_resources": True,
        },
    ],
}


# ---------------------------------------------------------------------------
# Test _user_installable_packages
# ---------------------------------------------------------------------------


class TestUserInstallablePackages:
    """Test per RegistryManager._user_installable_packages."""

    def test_filtra_pacchetti_engine_managed(self, tmp_path: Path) -> None:
        """Esclude i pacchetti con engine_managed_resources=True."""
        mgr = _make_mgr(tmp_path)
        result = mgr._user_installable_packages(_SAMPLE_MIXED_REGISTRY)
        ids = [p["id"] for p in result]
        assert "user-plugin" in ids
        assert "engine-pkg" not in ids

    def test_include_pacchetti_senza_campo(self, tmp_path: Path) -> None:
        """Include i pacchetti che non dichiarano engine_managed_resources."""
        mgr = _make_mgr(tmp_path)
        result = mgr._user_installable_packages(_SAMPLE_REGISTRY)
        ids = [p["id"] for p in result]
        assert "my-plugin" in ids
        assert "other-plugin" in ids

    def test_lista_vuota_se_tutti_engine_managed(self, tmp_path: Path) -> None:
        """Ritorna lista vuota se tutti i pacchetti sono engine_managed."""
        mgr = _make_mgr(tmp_path)
        result = mgr._user_installable_packages(_SAMPLE_ENGINE_MANAGED_REGISTRY)
        assert result == []


# ---------------------------------------------------------------------------
# Test filtro engine_managed nelle operazioni di menu
# ---------------------------------------------------------------------------


class TestFiltroEngineManaged:
    """Verifica che i pacchetti engine_managed siano esclusi dalle operazioni CLI."""

    def test_browse_plugins_esclude_engine_managed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """_browse_plugins mostra solo pacchetti non engine_managed."""
        mgr = _make_mgr(tmp_path)
        mgr._registry_cache = _SAMPLE_MIXED_REGISTRY

        mgr._browse_plugins()

        out, _ = capsys.readouterr()
        assert "user-plugin" in out
        assert "engine-pkg" not in out

    def test_install_plugin_rifiuta_package_engine_managed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """_install_plugin non trova un pacchetto engine_managed anche se esiste nel registro."""
        mgr = _make_mgr(tmp_path)
        mgr._registry_cache = _SAMPLE_ENGINE_MANAGED_REGISTRY

        with patch("builtins.input", return_value="engine-pkg"):
            mgr._install_plugin()

        out, _ = capsys.readouterr()
        assert "non trovato" in out.lower()

    def test_check_updates_ignora_pacchetti_engine_managed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """_check_updates non segnala aggiornamenti per pacchetti engine_managed."""
        mgr = _make_mgr(tmp_path)
        mgr._registry_cache = _SAMPLE_ENGINE_MANAGED_REGISTRY
        # Simula la presenza locale di engine-pkg con versione obsoleta.
        local_versions = {"engine-pkg": "0.9.0"}
        with patch.object(mgr, "_read_local_plugin_versions", return_value=local_versions):
            mgr._check_updates()

        out, _ = capsys.readouterr()
        # engine-pkg non deve apparire come aggiornamento disponibile.
        assert "engine-pkg" not in out


# ---------------------------------------------------------------------------
# Test comportamento UX run() — FIX-2
# ---------------------------------------------------------------------------


class TestRunUX:
    """Verifica clear screen e pausa interattiva in RegistryManager.run()."""

    def test_run_chiama_pausa_dopo_operazione(self, tmp_path: Path) -> None:
        """run() chiama input() per la pausa dopo ogni operazione (elif 1-4)."""
        mgr = _make_mgr(tmp_path)
        # Sequenza: "1" (scelta browse), "" (pausa), "0" (esci)
        mock_input = MagicMock(side_effect=["1", "", "0"])
        with (
            patch("builtins.input", mock_input),
            patch.object(mgr, "_browse_plugins"),
            patch("os.system"),
        ):
            mgr.run()
        # input() deve essere chiamato 3 volte: menu, pausa, menu-exit
        assert mock_input.call_count == 3

    def test_run_no_pausa_per_scelta_invalida(self, tmp_path: Path) -> None:
        """run() non inserisce pausa per scelta non valida."""
        mgr = _make_mgr(tmp_path)
        # Sequenza: "9" (invalida), "0" (esci)
        mock_input = MagicMock(side_effect=["9", "0"])
        with (
            patch("builtins.input", mock_input),
            patch("os.system"),
        ):
            mgr.run()
        # Nessuna pausa: solo 2 input() calls (menu + exit)
        assert mock_input.call_count == 2

    def test_run_esegue_clear_prima_del_menu(self, tmp_path: Path) -> None:
        """run() chiama os.system per pulire lo schermo prima di ogni iterazione."""
        mgr = _make_mgr(tmp_path)
        with (
            patch("builtins.input", side_effect=["0"]),
            patch("os.system") as mock_sys,
        ):
            mgr.run()
        mock_sys.assert_called_once()
