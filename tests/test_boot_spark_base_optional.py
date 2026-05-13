"""Test per _optional_spark_base_install in spark.boot.sequence.

Copertura:
- test_salta_se_gia_installato
- test_installa_se_risposta_si
- test_salta_se_risposta_no
- test_non_interattivo_salta_silenziosamente
- test_input_non_valido_richiede_conferma_poi_no
- test_fallimento_download_non_blocca_bootstrap
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from spark.boot.sequence import _optional_spark_base_install

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_context(tmp_path: Path) -> MagicMock:
    """Restituisce un WorkspaceContext mock con github_root in tmp_path."""
    ctx = MagicMock()
    ctx.github_root = tmp_path / ".github"
    ctx.github_root.mkdir(parents=True, exist_ok=True)
    return ctx


_SPARK_BASE_ENTRY: dict[str, object] = {
    "id": "spark-base",
    "display_name": "SPARK Base Layer",
    "latest_version": "2.1.0",
    "repo_url": "https://github.com/Nemex81/spark-base",
    "engine_managed_resources": False,
}

_SAMPLE_REGISTRY: dict[str, object] = {
    "packages": [
        _SPARK_BASE_ENTRY,
        {
            "id": "spark-ops",
            "display_name": "SPARK Ops Layer",
            "latest_version": "1.1.0",
            "repo_url": "https://github.com/Nemex81/spark-ops",
            "engine_managed_resources": True,
        },
    ]
}

# ---------------------------------------------------------------------------
# Test 1: skip se spark-base già installato
# ---------------------------------------------------------------------------


def test_salta_se_gia_installato(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """_optional_spark_base_install ritorna senza prompt se spark-base è già installato."""
    context = _make_context(tmp_path)
    engine_root = tmp_path / "engine"
    engine_root.mkdir()

    with patch("spark.manifest.manifest.ManifestManager") as MockMM:
        MockMM.return_value.get_installed_versions.return_value = {"spark-base": "2.1.0"}

        _optional_spark_base_install(context, engine_root, interactive=True)

    out, _ = capsys.readouterr()
    assert out == ""


# ---------------------------------------------------------------------------
# Test 2: installazione se risposta 's'
# ---------------------------------------------------------------------------


def test_installa_se_risposta_si(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """_optional_spark_base_install chiama _download_and_install_plugin se l'utente sceglie 's'."""
    context = _make_context(tmp_path)
    engine_root = tmp_path / "engine"
    engine_root.mkdir()

    with (
        patch("spark.manifest.manifest.ManifestManager") as MockMM,
        patch(
            "spark.cli.registry_manager.RegistryManager._load_registry",
            return_value=_SAMPLE_REGISTRY,
        ),
        patch(
            "spark.cli.registry_manager.RegistryManager._download_and_install_plugin",
            return_value={"success": True, "files_copied": 5, "error": ""},
        ) as mock_install,
        patch("builtins.input", return_value="s"),
    ):
        MockMM.return_value.get_installed_versions.return_value = {}

        _optional_spark_base_install(context, engine_root, interactive=True)

    mock_install.assert_called_once()
    out, _ = capsys.readouterr()
    assert "installato" in out.lower()


# ---------------------------------------------------------------------------
# Test 3: skip se risposta 'n'
# ---------------------------------------------------------------------------


def test_salta_se_risposta_no(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """_optional_spark_base_install non installa nulla se l'utente sceglie 'n'."""
    context = _make_context(tmp_path)
    engine_root = tmp_path / "engine"
    engine_root.mkdir()

    with (
        patch("spark.manifest.manifest.ManifestManager") as MockMM,
        patch(
            "spark.cli.registry_manager.RegistryManager._load_registry",
            return_value=_SAMPLE_REGISTRY,
        ),
        patch(
            "spark.cli.registry_manager.RegistryManager._download_and_install_plugin",
        ) as mock_install,
        patch("builtins.input", return_value="n"),
    ):
        MockMM.return_value.get_installed_versions.return_value = {}

        _optional_spark_base_install(context, engine_root, interactive=True)

    mock_install.assert_not_called()
    out, _ = capsys.readouterr()
    assert "mcp" in out.lower()


# ---------------------------------------------------------------------------
# Test 4: modalità non-interattiva salta silenziosamente
# ---------------------------------------------------------------------------


def test_non_interattivo_salta_silenziosamente(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Con interactive=False, la funzione ritorna senza output né prompt."""
    context = _make_context(tmp_path)
    engine_root = tmp_path / "engine"
    engine_root.mkdir()

    with patch("spark.manifest.manifest.ManifestManager") as MockMM:
        MockMM.return_value.get_installed_versions.return_value = {}

        _optional_spark_base_install(context, engine_root, interactive=False)

    out, _ = capsys.readouterr()
    assert out == ""


# ---------------------------------------------------------------------------
# Test 5: input non valido → richiede conferma → risposta 'n'
# ---------------------------------------------------------------------------


def test_input_non_valido_richiede_conferma_poi_no(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Con risposta non riconosciuta, viene mostrata una seconda richiesta."""
    context = _make_context(tmp_path)
    engine_root = tmp_path / "engine"
    engine_root.mkdir()

    with (
        patch("spark.manifest.manifest.ManifestManager") as MockMM,
        patch(
            "spark.cli.registry_manager.RegistryManager._load_registry",
            return_value=_SAMPLE_REGISTRY,
        ),
        patch(
            "spark.cli.registry_manager.RegistryManager._download_and_install_plugin",
        ) as mock_install,
        patch("builtins.input", side_effect=["xyz", "n"]),
    ):
        MockMM.return_value.get_installed_versions.return_value = {}

        _optional_spark_base_install(context, engine_root, interactive=True)

    mock_install.assert_not_called()


# ---------------------------------------------------------------------------
# Test 6: errore download non blocca bootstrap
# ---------------------------------------------------------------------------


def test_fallimento_download_non_blocca_bootstrap(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Se _download_and_install_plugin solleva un'eccezione, il bootstrap continua."""
    context = _make_context(tmp_path)
    engine_root = tmp_path / "engine"
    engine_root.mkdir()

    with (
        patch("spark.manifest.manifest.ManifestManager") as MockMM,
        patch(
            "spark.cli.registry_manager.RegistryManager._load_registry",
            return_value=_SAMPLE_REGISTRY,
        ),
        patch(
            "spark.cli.registry_manager.RegistryManager._download_and_install_plugin",
            side_effect=RuntimeError("network error"),
        ),
        patch("builtins.input", return_value="s"),
    ):
        MockMM.return_value.get_installed_versions.return_value = {}

        # Non deve sollevare eccezioni
        _optional_spark_base_install(context, engine_root, interactive=True)

    out, _ = capsys.readouterr()
    # Deve stampare un messaggio di errore
    assert "errore" in out.lower() or "installazione" in out.lower()
