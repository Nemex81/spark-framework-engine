"""tests.test_cli_init_manager — Test unitari per spark.cli.init_manager.

Coprono: happy path, workspace assente/presente, errori FS con rollback,
trasferimento idempotente e generazione mcp.json.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from spark.cli.init_manager import InitManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_spark_ops_manifest(engine_root: Path, workspace_files: list[str]) -> None:
    """Scrive un package-manifest.json minimale per spark-ops nell'engine root."""
    ops_dir = engine_root / "packages" / "spark-ops"
    ops_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "package": "spark-ops",
        "version": "1.0.0",
        "workspace_files": workspace_files,
    }
    (ops_dir / "package-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def _make_spark_ops_file(engine_root: Path, rel_path: str, content: str = "SPARK-FILE") -> None:
    """Crea un file fittizio nel package spark-ops dell'engine root."""
    full_path = engine_root / "packages" / "spark-ops" / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Test _create_workspace_structure
# ---------------------------------------------------------------------------


class TestCreateWorkspaceStructure:
    """Test per InitManager._create_workspace_structure."""

    def test_creates_github_dir_and_packages_file(self, tmp_path: Path) -> None:
        """Crea .github/ e spark-packages.json quando entrambi sono assenti."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        mgr = InitManager(engine_root)
        target = tmp_path / "workspace"
        target.mkdir()

        result = mgr._create_workspace_structure(target)

        assert result is True
        assert (target / ".github").is_dir()
        assert (target / ".github" / "spark-packages.json").is_file()

    def test_idempotent_when_both_exist(self, tmp_path: Path) -> None:
        """Restituisce False quando tutto è già presente (idempotente)."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        mgr = InitManager(engine_root)
        target = tmp_path / "workspace"
        github_dir = target / ".github"
        github_dir.mkdir(parents=True)
        (github_dir / "spark-packages.json").write_text("{}", encoding="utf-8")

        result = mgr._create_workspace_structure(target)

        assert result is False

    def test_creates_packages_file_when_only_dir_exists(self, tmp_path: Path) -> None:
        """Crea spark-packages.json quando .github/ esiste ma il file manca."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        mgr = InitManager(engine_root)
        target = tmp_path / "workspace"
        (target / ".github").mkdir(parents=True)

        result = mgr._create_workspace_structure(target)

        assert result is True
        assert (target / ".github" / "spark-packages.json").is_file()

    def test_packages_file_content(self, tmp_path: Path) -> None:
        """Il contenuto di spark-packages.json include spark-base e spark-ops."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        mgr = InitManager(engine_root)
        target = tmp_path / "workspace"
        target.mkdir()

        mgr._create_workspace_structure(target)

        content = json.loads(
            (target / ".github" / "spark-packages.json").read_text(encoding="utf-8")
        )
        assert "spark-base" in content.get("packages", [])
        assert "spark-ops" in content.get("packages", [])
        assert content.get("auto_install") is True


# ---------------------------------------------------------------------------
# Test _transfer_spark_ops
# ---------------------------------------------------------------------------


class TestTransferSparkOps:
    """Test per InitManager._transfer_spark_ops."""

    def test_copies_workspace_files(self, tmp_path: Path) -> None:
        """Copia correttamente i workspace_files di spark-ops nel target."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        rel = ".github/agents/spark-assistant.agent.md"
        _write_spark_ops_manifest(engine_root, [rel])
        _make_spark_ops_file(engine_root, rel, "AGENT-CONTENT")

        mgr = InitManager(engine_root)
        target = tmp_path / "workspace"
        target.mkdir()

        result = mgr._transfer_spark_ops(target)

        assert result["success"] is True
        assert result["files_copied"] == 1
        assert result["files_skipped"] == 0
        dest = target / ".github" / "agents" / "spark-assistant.agent.md"
        assert dest.is_file()
        assert dest.read_text(encoding="utf-8") == "AGENT-CONTENT"

    def test_skips_existing_files(self, tmp_path: Path) -> None:
        """Salta i file già presenti nel workspace target."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        rel = ".github/agents/spark-guide.agent.md"
        _write_spark_ops_manifest(engine_root, [rel])
        _make_spark_ops_file(engine_root, rel, "NEW-CONTENT")

        mgr = InitManager(engine_root)
        target = tmp_path / "workspace"
        dest = target / ".github" / "agents" / "spark-guide.agent.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("EXISTING-CONTENT", encoding="utf-8")

        result = mgr._transfer_spark_ops(target)

        assert result["success"] is True
        assert result["files_skipped"] == 1
        assert result["files_copied"] == 0
        # File non deve essere stato sovrascritto
        assert dest.read_text(encoding="utf-8") == "EXISTING-CONTENT"

    def test_missing_manifest_returns_error(self, tmp_path: Path) -> None:
        """Ritorna success=False se spark-ops manifest non esiste."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        # NON crea il manifest
        mgr = InitManager(engine_root)
        target = tmp_path / "workspace"
        target.mkdir()

        result = mgr._transfer_spark_ops(target)

        assert result["success"] is False
        assert result["files_copied"] == 0

    def test_rollback_on_os_error(self, tmp_path: Path) -> None:
        """Esegue rollback (elimina file copiati) su OSError durante la copia."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        rel1 = ".github/agents/file1.md"
        rel2 = ".github/agents/file2.md"
        _write_spark_ops_manifest(engine_root, [rel1, rel2])
        _make_spark_ops_file(engine_root, rel1, "CONTENT1")
        _make_spark_ops_file(engine_root, rel2, "CONTENT2")

        mgr = InitManager(engine_root)
        target = tmp_path / "workspace"
        target.mkdir()

        dest1 = target / ".github" / "agents" / "file1.md"

        call_count = 0

        original_copy2 = shutil.copy2

        def failing_copy(src: str, dst: str) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                original_copy2(src, dst)  # primo file OK
            else:
                raise OSError("Errore simulato")

        with patch("shutil.copy2", side_effect=failing_copy):
            result = mgr._transfer_spark_ops(target)

        # Rollback: file1 deve essere stato eliminato dopo la rollback
        assert result["success"] is False
        assert result["files_copied"] == 0
        # Dopo il rollback il primo file non deve essere presente
        assert not dest1.is_file()

    def test_no_workspace_files_returns_success(self, tmp_path: Path) -> None:
        """Ritorna success=True quando workspace_files è lista vuota."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        _write_spark_ops_manifest(engine_root, [])  # lista vuota
        mgr = InitManager(engine_root)
        target = tmp_path / "workspace"
        target.mkdir()

        result = mgr._transfer_spark_ops(target)

        assert result["success"] is True
        assert result["files_copied"] == 0


# ---------------------------------------------------------------------------
# Test _write_mcp_config
# ---------------------------------------------------------------------------


class TestWriteMcpConfig:
    """Test per InitManager._write_mcp_config."""

    def test_creates_mcp_json_when_absent(self, tmp_path: Path) -> None:
        """Crea .vscode/mcp.json se non presente."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        mgr = InitManager(engine_root)
        target = tmp_path / "workspace"
        target.mkdir()

        changed = mgr._write_mcp_config(target)

        assert changed is True
        mcp_json = target / ".vscode" / "mcp.json"
        assert mcp_json.is_file()
        content = json.loads(mcp_json.read_text(encoding="utf-8"))
        assert "spark-framework-engine" in content.get("servers", {})

    def test_adds_server_to_existing_mcp_json(self, tmp_path: Path) -> None:
        """Aggiunge il server SPARK a un mcp.json già esistente."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        mgr = InitManager(engine_root)
        target = tmp_path / "workspace"
        vscode_dir = target / ".vscode"
        vscode_dir.mkdir(parents=True)
        mcp_json = vscode_dir / "mcp.json"
        mcp_json.write_text(
            json.dumps({"servers": {"other-server": {}}}), encoding="utf-8"
        )

        changed = mgr._write_mcp_config(target)

        assert changed is True
        content = json.loads(mcp_json.read_text(encoding="utf-8"))
        assert "spark-framework-engine" in content["servers"]
        assert "other-server" in content["servers"]  # preservato

    def test_no_change_when_server_already_present(self, tmp_path: Path) -> None:
        """Ritorna False senza modificare se il server è già presente."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        mgr = InitManager(engine_root)
        target = tmp_path / "workspace"
        vscode_dir = target / ".vscode"
        vscode_dir.mkdir(parents=True)
        mcp_json = vscode_dir / "mcp.json"
        mcp_json.write_text(
            json.dumps({"servers": {"spark-framework-engine": {"type": "stdio"}}}),
            encoding="utf-8",
        )
        original_content = mcp_json.read_text(encoding="utf-8")

        changed = mgr._write_mcp_config(target)

        assert changed is False
        assert mcp_json.read_text(encoding="utf-8") == original_content  # nessuna modifica


# ---------------------------------------------------------------------------
# Test _signal_reload
# ---------------------------------------------------------------------------


class TestSignalReload:
    """Test per InitManager._signal_reload."""

    def test_creates_reload_marker(self, tmp_path: Path) -> None:
        """Scrive .github/.spark-reload-requested con timestamp ISO."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        mgr = InitManager(engine_root)
        target = tmp_path / "workspace"
        (target / ".github").mkdir(parents=True)

        mgr._signal_reload(target)

        marker = target / ".github" / ".spark-reload-requested"
        assert marker.is_file()
        content = marker.read_text(encoding="utf-8")
        # Il contenuto deve essere un ISO timestamp (contiene 'T' e '+')
        assert "T" in content

    def test_creates_github_dir_if_absent(self, tmp_path: Path) -> None:
        """Crea .github/ se non presente prima di scrivere il marker."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        mgr = InitManager(engine_root)
        target = tmp_path / "workspace"
        target.mkdir()  # .github/ assente

        mgr._signal_reload(target)

        assert (target / ".github" / ".spark-reload-requested").is_file()


# ---------------------------------------------------------------------------
# Test run() — happy path con input simulato
# ---------------------------------------------------------------------------


class TestInitManagerRun:
    """Test per il flusso completo di InitManager.run()."""

    def test_run_happy_path(self, tmp_path: Path) -> None:
        """Esegue run() con workspace fittizio senza errori."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        rel = ".github/agents/spark-assistant.agent.md"
        _write_spark_ops_manifest(engine_root, [rel])
        _make_spark_ops_file(engine_root, rel, "AGENT-CONTENT")

        target = tmp_path / "workspace"
        target.mkdir()

        mgr = InitManager(engine_root)

        # Side effects: (1) percorso workspace, (2) risposta a "Aprire VS Code? [s/N]"
        with patch("builtins.input", side_effect=[str(target), "n"]):
            mgr.run()

        assert (target / ".github").is_dir()
        assert (target / ".github" / "spark-packages.json").is_file()
        assert (target / ".github" / ".spark-reload-requested").is_file()

    def test_run_cancel_returns_without_creating(self, tmp_path: Path) -> None:
        """Annullando (input='0') non crea nessuna struttura."""
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        mgr = InitManager(engine_root)
        target = tmp_path / "workspace_not_created"

        with patch("builtins.input", side_effect=["0"]):
            mgr.run()

        assert not target.exists()


# ---------------------------------------------------------------------------
# Test _offer_vscode_open (CICLO 5)
# ---------------------------------------------------------------------------


class TestOfferVscodeOpen:
    """Test per InitManager._offer_vscode_open."""

    def test_i1_utente_conferma_code_nel_path(self, tmp_path: Path) -> None:
        """I1: utente dice 's', code nel PATH — subprocess.run chiamato con .code-workspace.

        Args:
            tmp_path: Directory temporanea isolata del test.
        """
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        target = tmp_path / "workspace"
        target.mkdir()
        ws_file = target / "mio-progetto.code-workspace"
        ws_file.write_text("{}", encoding="utf-8")

        mgr = InitManager(engine_root)

        with (
            patch("builtins.input", return_value="s"),
            patch("subprocess.run") as mock_run,
        ):
            mgr._offer_vscode_open(target)

        mock_run.assert_called_once_with(["code", str(ws_file)], check=False)

    def test_i2_utente_rifiuta_apertura(self, tmp_path: Path) -> None:
        """I2: utente dice 'n' — subprocess.run non viene chiamato.

        Args:
            tmp_path: Directory temporanea isolata del test.
        """
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        target = tmp_path / "workspace"
        target.mkdir()

        mgr = InitManager(engine_root)

        with (
            patch("builtins.input", return_value="n"),
            patch("subprocess.run") as mock_run,
        ):
            mgr._offer_vscode_open(target)

        mock_run.assert_not_called()

    def test_i3_code_non_nel_path_file_not_found(self, tmp_path: Path) -> None:
        """I3: code non nel PATH — FileNotFoundError non propaga, warning su stderr.

        Args:
            tmp_path: Directory temporanea isolata del test.
        """
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        target = tmp_path / "workspace"
        target.mkdir()

        mgr = InitManager(engine_root)

        with (
            patch("builtins.input", return_value="s"),
            patch("subprocess.run", side_effect=FileNotFoundError("code not found")),
        ):
            # Non deve sollevare eccezioni
            mgr._offer_vscode_open(target)

    def test_i1_fallback_su_cartella_senza_workspace_file(self, tmp_path: Path) -> None:
        """I1b: nessun .code-workspace — subprocess.run usa la cartella target.

        Args:
            tmp_path: Directory temporanea isolata del test.
        """
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        target = tmp_path / "workspace"
        target.mkdir()

        mgr = InitManager(engine_root)

        with (
            patch("builtins.input", return_value="s"),
            patch("subprocess.run") as mock_run,
        ):
            mgr._offer_vscode_open(target)

        mock_run.assert_called_once_with(["code", str(target)], check=False)
