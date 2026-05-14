"""tests.test_cli_registry_manager — Test unitari per spark.cli.registry_manager.

Coprono: sfoglio plugin, installazione, verifica aggiornamenti,
graceful degradation su registro non raggiungibile.
"""
from __future__ import annotations

import hashlib
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
        assert any(
            "Impossibile scaricare manifest" in e for e in result.get("errors", [])
        )

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
                return_value={"success": True, "files_copied": 1, "preserved": 0, "errors": []},
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


# ---------------------------------------------------------------------------
# Test filtro con nomi reali del registro (spark-base / spark-ops)
# ---------------------------------------------------------------------------

_SAMPLE_REAL_REGISTRY: dict[str, object] = {
    "packages": [
        {
            "id": "spark-base",
            "display_name": "SPARK Base Layer",
            "latest_version": "2.1.0",
            "repo_url": "https://github.com/Nemex81/spark-base",
            "engine_managed_resources": False,
        },
        {
            "id": "spark-ops",
            "display_name": "SPARK Ops Layer",
            "latest_version": "1.1.0",
            "repo_url": "https://github.com/Nemex81/spark-ops",
            "engine_managed_resources": True,
        },
    ]
}


class TestFiltroEngineMangedNomiReali:
    """Verifica il filtro con ID reali spark-base e spark-ops."""

    def test_spark_base_incluso_spark_ops_escluso(self, tmp_path: Path) -> None:
        """spark-base (engine_managed=false) è incluso; spark-ops (true) è escluso."""
        mgr = _make_mgr(tmp_path)
        result = mgr._user_installable_packages(_SAMPLE_REAL_REGISTRY)  # type: ignore[arg-type]
        ids = [p["id"] for p in result]
        assert "spark-base" in ids
        assert "spark-ops" not in ids


# ---------------------------------------------------------------------------
# Costanti per test PR-1
# ---------------------------------------------------------------------------

_PR1_FILE_CONTENT = b"AGENT-FILE-CONTENT-PR1"
_PR1_SHA_KNOWN = hashlib.sha256(_PR1_FILE_CONTENT).hexdigest()

_PR1_PLUGIN_ENTRY: dict = {
    "id": "my-plugin",
    "latest_version": "1.0.0",
    "repo_url": "https://github.com/Nemex81/my-plugin",
    "manifest_path": "package-manifest.json",
}

_PR1_MANIFEST_WITH_META: dict = {
    "package": "my-plugin",
    "version": "1.0.0",
    "workspace_files": [".github/agents/my-agent.md"],
    "files_metadata": [
        {"path": ".github/agents/my-agent.md", "sha256": _PR1_SHA_KNOWN},
    ],
}


def _make_urlopen_ctx(content: bytes) -> MagicMock:
    """Crea un mock di urlopen compatibile con context manager.

    Args:
        content: Bytes da restituire come corpo della risposta HTTP.

    Returns:
        MagicMock configurato per essere usato con ``with urlopen(...) as resp``.
    """
    mock_resp = MagicMock()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = content
    return mock_resp


# ---------------------------------------------------------------------------
# Test _download_and_install_plugin — PR-1 fixes
# ---------------------------------------------------------------------------


class TestDownloadAndInstallPluginPR1:
    """Test per i fix PR-1 di _download_and_install_plugin.

    Copre Fix A (delivery_mode mcp_only), Fix B (SHA-based idempotency),
    Fix C (plugin_files loop), Fix D (upsert_many manifest update).
    """

    def test_scenario1_fresh_install(self, tmp_path: Path) -> None:
        """Scenario 1 — Installazione da zero.

        Prerequisiti: nessun file su disco, manifest con files_metadata e sha256.
        Verifica che il file venga scritto e upsert_many chiamata con gli argomenti
        corretti (plugin_id, version, lista file).

        Asserzioni:
            - success == True
            - files_copied == 1
            - preserved == 0
            - errors == []
            - upsert_many chiamata esattamente 1 volta
        """
        github_root = tmp_path / ".github"
        github_root.mkdir()
        mgr = RegistryManager(github_root, tmp_path / "engine")

        with (
            patch.object(mgr, "_fetch_remote_manifest", return_value=_PR1_MANIFEST_WITH_META),
            patch("urllib.request.urlopen", return_value=_make_urlopen_ctx(_PR1_FILE_CONTENT)),
            patch("spark.manifest.manifest.ManifestManager") as mock_mm,
        ):
            result = mgr._download_and_install_plugin(_PR1_PLUGIN_ENTRY)

        assert result["success"] is True
        assert result["files_copied"] == 1
        assert result["preserved"] == 0
        assert result["errors"] == []
        mock_mm.return_value.upsert_many.assert_called_once()
        call_args = mock_mm.return_value.upsert_many.call_args[0]
        assert call_args[0] == "my-plugin"
        assert call_args[1] == "1.0.0"
        assert len(call_args[2]) == 1

    def test_scenario2_idempotent_reinstall_sha_invariato(self, tmp_path: Path) -> None:
        """Scenario 2 — Reinstallazione con SHA invariato (idempotenza).

        Prerequisiti: file già presenti su disco, SHA identico al manifest remoto.
        _sha256_file viene patchato per restituire il valore noto senza lettura disco.

        Asserzioni:
            - success == True
            - files_copied == 0
            - preserved == 1
            - errors == []
            - upsert_many NON chiamata (files_copied == 0)
        """
        github_root = tmp_path / ".github"
        (github_root / "agents").mkdir(parents=True)
        (github_root / "agents" / "my-agent.md").write_bytes(_PR1_FILE_CONTENT)
        mgr = RegistryManager(github_root, tmp_path / "engine")

        with (
            patch.object(mgr, "_fetch_remote_manifest", return_value=_PR1_MANIFEST_WITH_META),
            patch("spark.cli.registry_manager._sha256_file", return_value=_PR1_SHA_KNOWN),
            patch("spark.manifest.manifest.ManifestManager") as mock_mm,
        ):
            result = mgr._download_and_install_plugin(_PR1_PLUGIN_ENTRY)

        assert result["success"] is True
        assert result["files_copied"] == 0
        assert result["preserved"] == 1
        assert result["errors"] == []
        mock_mm.return_value.upsert_many.assert_not_called()

    def test_scenario3_partial_download_error(self, tmp_path: Path) -> None:
        """Scenario 3 — Errore parziale download: primo file OK, secondo URLError.

        URLError per singolo file non è fatale: l'operazione continua e
        l'errore finisce in result["errors"] senza bloccare il successo globale.

        Asserzioni:
            - success == True
            - files_copied == 1 (solo il primo file riuscito)
            - errors contiene almeno una entry con 'Download fallito'
            - upsert_many chiamata con 1 solo file
        """
        github_root = tmp_path / ".github"
        github_root.mkdir()
        mgr = RegistryManager(github_root, tmp_path / "engine")

        manifest_two_files: dict = {
            "package": "my-plugin",
            "version": "1.0.0",
            "workspace_files": [
                ".github/agents/file-a.md",
                ".github/agents/file-b.md",
            ],
        }

        call_count = 0

        def _fake_urlopen(url: str, timeout: int = 10) -> MagicMock:
            """Prima chiamata restituisce contenuto, seconda lancia URLError."""
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_urlopen_ctx(b"FILE-A-CONTENT")
            raise URLError("network error")

        with (
            patch.object(mgr, "_fetch_remote_manifest", return_value=manifest_two_files),
            patch("urllib.request.urlopen", side_effect=_fake_urlopen),
            patch("spark.manifest.manifest.ManifestManager") as mock_mm,
        ):
            result = mgr._download_and_install_plugin(_PR1_PLUGIN_ENTRY)

        assert result["success"] is True
        assert result["files_copied"] == 1
        assert any("Download fallito" in e for e in result["errors"])
        mock_mm.return_value.upsert_many.assert_called_once()
        upsert_args = mock_mm.return_value.upsert_many.call_args[0]
        assert len(upsert_args[2]) == 1

    def test_scenario_bonus_mcp_only(self, tmp_path: Path) -> None:
        """Scenario bonus — delivery_mode mcp_only: redirect a PackageManager.

        Il pacchetto non viene installato via RegistryManager; viene stampato
        un messaggio di reindirizzamento e il dict di ritorno indica fallimento.

        Asserzioni:
            - success == False
            - files_copied == 0
            - errors contiene entry con 'mcp_only'
            - upsert_many NON chiamata
        """
        github_root = tmp_path / ".github"
        github_root.mkdir()
        mgr = RegistryManager(github_root, tmp_path / "engine")

        mcp_only_manifest: dict = {
            "package": "my-plugin",
            "version": "1.0.0",
            "delivery_mode": "mcp_only",
            "workspace_files": [".github/agents/my-agent.md"],
        }

        with (
            patch.object(mgr, "_fetch_remote_manifest", return_value=mcp_only_manifest),
            patch("spark.manifest.manifest.ManifestManager") as mock_mm,
        ):
            result = mgr._download_and_install_plugin(_PR1_PLUGIN_ENTRY)

        assert result["success"] is False
        assert result["files_copied"] == 0
        assert any("mcp_only" in e for e in result["errors"])
        mock_mm.return_value.upsert_many.assert_not_called()

    def test_fix_c_plugin_files_inclusi_nel_loop(self, tmp_path: Path) -> None:
        """Fix C — plugin_files elaborati insieme a workspace_files.

        Verifica che i file in ``plugin_files`` vengano scaricati e scritti
        esattamente come quelli in ``workspace_files``, contando verso
        ``files_copied`` e passati a ``upsert_many``.

        Asserzioni:
            - files_copied == 2 (1 da workspace_files + 1 da plugin_files)
            - success == True
            - upsert_many chiamata con 2 file
        """
        github_root = tmp_path / ".github"
        github_root.mkdir()
        mgr = RegistryManager(github_root, tmp_path / "engine")

        manifest_mixed: dict = {
            "package": "my-plugin",
            "version": "1.0.0",
            "workspace_files": [".github/agents/workspace-agent.md"],
            "plugin_files": [".github/agents/plugin-agent.md"],
        }

        with (
            patch.object(mgr, "_fetch_remote_manifest", return_value=manifest_mixed),
            patch(
                "urllib.request.urlopen",
                return_value=_make_urlopen_ctx(b"FILE-CONTENT"),
            ),
            patch("spark.manifest.manifest.ManifestManager") as mock_mm,
        ):
            result = mgr._download_and_install_plugin(_PR1_PLUGIN_ENTRY)

        assert result["success"] is True
        assert result["files_copied"] == 2
        assert result["errors"] == []
        upsert_args = mock_mm.return_value.upsert_many.call_args[0]
        assert len(upsert_args[2]) == 2

