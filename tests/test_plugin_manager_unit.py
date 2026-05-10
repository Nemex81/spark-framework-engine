"""Test unitari per spark.plugins — Plugin Manager (Step 1).

Verifica i componenti del package spark/plugins/ in isolamento con
filesystem mockato tramite tmp_path e mock di urllib.request.urlopen.
Nessuna chiamata HTTP reale viene eseguita in questi test.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from spark.plugins.facade import PluginManagerFacade
from spark.plugins.installer import PluginInstaller
from spark.plugins.registry import PluginRegistry
from spark.plugins.remover import PluginRemover
from spark.plugins.schema import (
    PluginInstallError,
    PluginManifest,
    PluginRecord,
)


# ---------------------------------------------------------------------------
# Fixtures comuni
# ---------------------------------------------------------------------------


def _make_record(
    pkg_id: str = "test-plugin",
    version: str = "1.0.0",
    files: list[str] | None = None,
    migrated: bool = False,
) -> PluginRecord:
    """Factory di PluginRecord per i test."""
    return PluginRecord(
        pkg_id=pkg_id,
        version=version,
        source_repo="Nemex81/test-plugin",
        installed_at="2026-05-08T09:00:00Z",
        files=files or [],
        file_hashes={},
        migrated=migrated,
    )


def _make_manifest(
    pkg_id: str = "test-plugin",
    version: str = "1.0.0",
    plugin_files: list[str] | None = None,
) -> PluginManifest:
    """Factory di PluginManifest per i test."""
    return PluginManifest(
        pkg_id=pkg_id,
        version=version,
        source_repo="Nemex81/test-plugin",
        plugin_files=plugin_files or [],
    )


# ---------------------------------------------------------------------------
# PluginRegistry — register() e get()
# ---------------------------------------------------------------------------


class TestPluginRegistryRegisterAndGet:
    """Verifica che register() salvi su disco e get() recuperi il record."""

    def test_register_creates_file(self, tmp_path: Path) -> None:
        """Dopo register(), il file .spark-plugins deve esistere."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        registry = PluginRegistry(github_root)

        record = _make_record()
        registry.register(record)

        plugins_file = github_root / ".spark-plugins"
        assert plugins_file.is_file(), ".spark-plugins deve essere creato"

    def test_register_and_get_round_trip(self, tmp_path: Path) -> None:
        """Il record salvato deve essere recuperabile con get()."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        registry = PluginRegistry(github_root)

        record = _make_record(pkg_id="my-plugin", version="2.0.0")
        registry.register(record)

        retrieved = registry.get("my-plugin")
        assert retrieved is not None
        assert retrieved.pkg_id == "my-plugin"
        assert retrieved.version == "2.0.0"
        assert retrieved.migrated is False

    def test_get_returns_none_when_absent(self, tmp_path: Path) -> None:
        """get() deve restituire None se il plugin non è registrato."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        registry = PluginRegistry(github_root)

        assert registry.get("nonexistent") is None

    def test_register_updates_existing_record(self, tmp_path: Path) -> None:
        """register() su un pkg_id già esistente deve sovrascrivere il record."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        registry = PluginRegistry(github_root)

        v1 = _make_record(version="1.0.0")
        registry.register(v1)

        v2 = _make_record(version="2.0.0")
        registry.register(v2)

        retrieved = registry.get("test-plugin")
        assert retrieved is not None
        assert retrieved.version == "2.0.0"

    def test_load_returns_empty_when_file_absent(self, tmp_path: Path) -> None:
        """load() deve restituire {} se il file non esiste ancora."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        registry = PluginRegistry(github_root)

        assert registry.load() == {}

    def test_unregister_removes_record(self, tmp_path: Path) -> None:
        """unregister() deve rimuovere il record e aggiornare il file."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        registry = PluginRegistry(github_root)

        registry.register(_make_record())
        registry.unregister("test-plugin")

        assert registry.get("test-plugin") is None

    def test_unregister_noop_when_absent(self, tmp_path: Path) -> None:
        """unregister() su plugin non presente non deve sollevare eccezioni."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        registry = PluginRegistry(github_root)

        # Nessuna eccezione attesa.
        registry.unregister("nonexistent")


# ---------------------------------------------------------------------------
# PluginRegistry — migrate_from_manifest()
# ---------------------------------------------------------------------------


class TestPluginRegistryMigrateFromManifest:
    """Verifica il comportamento di migrate_from_manifest()."""

    def test_migrate_creates_records_from_manifest(self, tmp_path: Path) -> None:
        """migrate_from_manifest() deve importare i pacchetti dal ManifestManager."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        registry = PluginRegistry(github_root)

        # Mock ManifestManager con due pacchetti installati.
        mock_manifest = MagicMock()
        mock_manifest.get_installed_versions.return_value = {
            "spark-base": "1.6.0",
            "scf-master-codecrafter": "2.5.0",
        }
        mock_manifest.load.return_value = [
            {
                "file": "instructions/python.md",
                "package": "spark-base",
                "package_version": "1.6.0",
                "installation_mode": "",
            },
            {
                "file": "agents/code-Agent-Code.md",
                "package": "scf-master-codecrafter",
                "package_version": "2.5.0",
                "installation_mode": "",
            },
        ]

        count = registry.migrate_from_manifest(mock_manifest)
        assert count == 2

        # I record devono essere presenti e marcati come migrated.
        base_record = registry.get("spark-base")
        assert base_record is not None
        assert base_record.migrated is True
        assert base_record.version == "1.6.0"

    def test_migrate_skips_if_file_exists(self, tmp_path: Path) -> None:
        """migrate_from_manifest() deve essere no-op se .spark-plugins esiste già."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        # Crea il file .spark-plugins con un record esistente.
        plugins_file = github_root / ".spark-plugins"
        plugins_file.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "installed": {
                        "existing-plugin": {
                            "version": "1.0.0",
                            "source_repo": "",
                            "installed_at": "2026-01-01T00:00:00Z",
                            "files": [],
                            "file_hashes": {},
                            "migrated": False,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        registry = PluginRegistry(github_root)
        mock_manifest = MagicMock()
        mock_manifest.get_installed_versions.return_value = {"new-pkg": "1.0.0"}
        mock_manifest.load.return_value = []

        count = registry.migrate_from_manifest(mock_manifest)
        assert count == 0, "Migrazione deve essere no-op se il file esiste già"

    def test_migrate_returns_zero_for_empty_manifest(self, tmp_path: Path) -> None:
        """migrate_from_manifest() deve restituire 0 con manifest vuoto."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        registry = PluginRegistry(github_root)

        mock_manifest = MagicMock()
        mock_manifest.get_installed_versions.return_value = {}
        mock_manifest.load.return_value = []

        count = registry.migrate_from_manifest(mock_manifest)
        assert count == 0


# ---------------------------------------------------------------------------
# PluginInstaller — _build_raw_url()
# ---------------------------------------------------------------------------


class TestPluginInstallerBuildRawUrl:
    """Verifica la costruzione delle URL raw GitHub (test puri, no I/O)."""

    def _make_installer(self, tmp_path: Path) -> PluginInstaller:
        """Helper: crea un PluginInstaller con dipendenze mock."""
        mock_manifest = MagicMock()
        mock_gateway = MagicMock()
        return PluginInstaller(
            workspace_root=tmp_path,
            manifest_manager=mock_manifest,
            gateway=mock_gateway,
        )

    def test_build_raw_url_standard(self, tmp_path: Path) -> None:
        """URL costruita correttamente per file standard."""
        installer = self._make_installer(tmp_path)
        url = installer._build_raw_url(
            "Nemex81/scf-master-codecrafter",
            ".github/instructions/scf-master-codecrafter.md",
        )
        expected = (
            "https://raw.githubusercontent.com/Nemex81/scf-master-codecrafter"
            "/main/.github/instructions/scf-master-codecrafter.md"
        )
        assert url == expected

    def test_build_raw_url_nested_path(self, tmp_path: Path) -> None:
        """URL costruita correttamente per path con sottodirectory."""
        installer = self._make_installer(tmp_path)
        url = installer._build_raw_url(
            "Nemex81/spark-base",
            ".github/agents/spark-assistant.agent.md",
        )
        assert url.startswith("https://raw.githubusercontent.com/Nemex81/spark-base/main/")
        assert url.endswith(".github/agents/spark-assistant.agent.md")

    def test_build_raw_url_no_double_slash(self, tmp_path: Path) -> None:
        """La URL non deve contenere slash doppi nel path."""
        installer = self._make_installer(tmp_path)
        url = installer._build_raw_url("owner/repo", "file.md")
        assert "//" not in url.replace("https://", "")


# ---------------------------------------------------------------------------
# PluginInstaller — _add_instruction_reference()
# ---------------------------------------------------------------------------


class TestPluginInstallerAddInstructionReference:
    """Verifica l'inserimento delle referenze #file: in copilot-instructions.md."""

    def _make_installer(self, workspace_root: Path) -> PluginInstaller:
        """Helper: crea un PluginInstaller che usa il filesystem reale."""
        mock_manifest = MagicMock()
        mock_gateway = MagicMock()
        return PluginInstaller(
            workspace_root=workspace_root,
            manifest_manager=mock_manifest,
            gateway=mock_gateway,
        )

    def test_adds_file_ref_when_instruction_file_exists(self, tmp_path: Path) -> None:
        """La riga #file: deve essere aggiunta se il file istruzioni esiste."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        instructions_dir = github_root / "instructions"
        instructions_dir.mkdir()

        # Crea il file istruzioni del plugin.
        plugin_instruction = instructions_dir / "my-plugin.md"
        plugin_instruction.write_text("# My Plugin Instructions\n", encoding="utf-8")

        # Crea copilot-instructions.md.
        copilot_md = github_root / "copilot-instructions.md"
        copilot_md.write_text("# Existing content\n\nSome text.\n", encoding="utf-8")

        installer = self._make_installer(tmp_path)
        installer._add_instruction_reference("my-plugin")

        content = copilot_md.read_text(encoding="utf-8")
        assert "#file:.github/instructions/my-plugin.md" in content

    def test_noop_when_instruction_file_missing(self, tmp_path: Path) -> None:
        """Nessuna modifica se il file istruzioni del plugin non esiste."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        copilot_md = github_root / "copilot-instructions.md"
        original = "# Existing content\n"
        copilot_md.write_text(original, encoding="utf-8")

        installer = self._make_installer(tmp_path)
        # Non esiste .github/instructions/my-plugin.md.
        installer._add_instruction_reference("my-plugin")

        # Il file non deve essere modificato.
        assert copilot_md.read_text(encoding="utf-8") == original

    def test_noop_when_ref_already_present(self, tmp_path: Path) -> None:
        """No-op se la referenza è già presente nel file."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        instructions_dir = github_root / "instructions"
        instructions_dir.mkdir()

        plugin_instruction = instructions_dir / "my-plugin.md"
        plugin_instruction.write_text("# My Plugin\n", encoding="utf-8")

        ref_line = "#file:.github/instructions/my-plugin.md"
        original = f"# Header\n{ref_line}\n"
        copilot_md = github_root / "copilot-instructions.md"
        copilot_md.write_text(original, encoding="utf-8")

        installer = self._make_installer(tmp_path)
        installer._add_instruction_reference("my-plugin")

        content = copilot_md.read_text(encoding="utf-8")
        # La referenza deve apparire esattamente una volta.
        assert content.count(ref_line) == 1

    def test_creates_section_when_absent(self, tmp_path: Path) -> None:
        """La sezione plugin viene creata se non è presente in copilot-instructions.md."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        instructions_dir = github_root / "instructions"
        instructions_dir.mkdir()

        plugin_instruction = instructions_dir / "new-plugin.md"
        plugin_instruction.write_text("# New Plugin\n", encoding="utf-8")

        copilot_md = github_root / "copilot-instructions.md"
        copilot_md.write_text("# Copilot Instructions\n\nSome content.\n", encoding="utf-8")

        installer = self._make_installer(tmp_path)
        installer._add_instruction_reference("new-plugin")

        content = copilot_md.read_text(encoding="utf-8")
        assert "#file:.github/instructions/new-plugin.md" in content
        # La sezione header deve essere presente.
        assert "Plugin instructions" in content


# ---------------------------------------------------------------------------
# PluginRemover — _remove_instruction_reference()
# ---------------------------------------------------------------------------


class TestPluginRemoverRemoveInstructionReference:
    """Verifica la rimozione delle referenze #file: da copilot-instructions.md."""

    def _make_remover(self, workspace_root: Path) -> PluginRemover:
        """Helper: crea un PluginRemover che usa il filesystem reale."""
        mock_manifest = MagicMock()
        mock_gateway = MagicMock()
        return PluginRemover(
            workspace_root=workspace_root,
            manifest_manager=mock_manifest,
            gateway=mock_gateway,
        )

    def test_removes_file_ref(self, tmp_path: Path) -> None:
        """La riga #file: deve essere rimossa dal file."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        copilot_md = github_root / "copilot-instructions.md"
        copilot_md.write_text(
            "# Copilot Instructions\n\n"
            "# Plugin instructions (managed by SPARK Plugin Manager \u2014 do not edit manually)\n"
            "#file:.github/instructions/my-plugin.md\n",
            encoding="utf-8",
        )

        remover = self._make_remover(tmp_path)
        remover._remove_instruction_reference("my-plugin")

        content = copilot_md.read_text(encoding="utf-8")
        assert "#file:.github/instructions/my-plugin.md" not in content

    def test_noop_when_ref_absent(self, tmp_path: Path) -> None:
        """No-op se la referenza non è presente nel file."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        original = "# Copilot Instructions\n\nNo plugin references here.\n"
        copilot_md = github_root / "copilot-instructions.md"
        copilot_md.write_text(original, encoding="utf-8")

        remover = self._make_remover(tmp_path)
        remover._remove_instruction_reference("my-plugin")

        assert copilot_md.read_text(encoding="utf-8") == original

    def test_noop_when_copilot_instructions_missing(self, tmp_path: Path) -> None:
        """No-op se copilot-instructions.md non esiste nel workspace."""
        github_root = tmp_path / ".github"
        github_root.mkdir()

        remover = self._make_remover(tmp_path)
        # Nessuna eccezione attesa.
        remover._remove_instruction_reference("my-plugin")

    def test_removes_section_header_when_empty(self, tmp_path: Path) -> None:
        """La sezione plugin viene rimossa se rimane vuota dopo la rimozione."""
        github_root = tmp_path / ".github"
        github_root.mkdir()
        copilot_md = github_root / "copilot-instructions.md"
        copilot_md.write_text(
            "# Copilot Instructions\n\n"
            "# Plugin instructions (managed by SPARK Plugin Manager \u2014 do not edit manually)\n"
            "#file:.github/instructions/only-plugin.md\n",
            encoding="utf-8",
        )

        remover = self._make_remover(tmp_path)
        remover._remove_instruction_reference("only-plugin")

        content = copilot_md.read_text(encoding="utf-8")
        assert "#file:" not in content
        # La sezione header deve essere rimossa quando è vuota.
        assert "Plugin instructions" not in content


# ---------------------------------------------------------------------------
# PluginManagerFacade — __init__()
# ---------------------------------------------------------------------------


class TestPluginManagerFacadeInit:
    """Verifica l'instanziazione di PluginManagerFacade con workspace fittizio."""

    def test_instantiation_with_tmp_path(self, tmp_path: Path) -> None:
        """PluginManagerFacade deve essere instanziabile senza eccezioni."""
        github_root = tmp_path / ".github"
        github_root.mkdir()

        facade = PluginManagerFacade(workspace_root=tmp_path)

        assert facade is not None
        assert facade._workspace_root == tmp_path

    def test_instantiation_creates_internal_components(self, tmp_path: Path) -> None:
        """Tutti i componenti interni devono essere inizializzati."""
        github_root = tmp_path / ".github"
        github_root.mkdir()

        facade = PluginManagerFacade(workspace_root=tmp_path)

        assert facade._manifest is not None
        assert facade._gateway is not None
        assert facade._remote_registry is not None
        assert facade._plugin_registry is not None
        assert facade._installer is not None
        assert facade._remover is not None
        assert facade._updater is not None

    def test_instantiation_with_custom_registry_url(self, tmp_path: Path) -> None:
        """PluginManagerFacade accetta un registry_url personalizzato."""
        github_root = tmp_path / ".github"
        github_root.mkdir()

        custom_url = (
            "https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json"
        )
        facade = PluginManagerFacade(workspace_root=tmp_path, registry_url=custom_url)
        assert facade is not None

    def test_list_installed_empty_workspace(self, tmp_path: Path) -> None:
        """list_installed() deve restituire lista vuota su workspace vergine."""
        github_root = tmp_path / ".github"
        github_root.mkdir()

        facade = PluginManagerFacade(workspace_root=tmp_path)
        result = facade.list_installed()

        assert result["success"] is True
        assert result["plugins"] == []
        assert result["count"] == 0

    def test_status_not_installed(self, tmp_path: Path) -> None:
        """status() deve restituire installed=False per plugin non presente."""
        github_root = tmp_path / ".github"
        github_root.mkdir()

        facade = PluginManagerFacade(workspace_root=tmp_path)
        result = facade.status("nonexistent-plugin")

        assert result["success"] is True
        assert result["installed"] is False
