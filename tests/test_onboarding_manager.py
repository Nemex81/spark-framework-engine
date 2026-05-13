"""Unit tests for OnboardingManager (V6 gap from audit-system-state-v1.0).

Cover the public API of ``spark.boot.onboarding.OnboardingManager`` covering
positive/negative branches of ``is_first_run``, ``run_onboarding`` and the
internal step ``_install_declared_packages``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from spark.boot.onboarding import OnboardingManager
from spark.core.models import WorkspaceContext
from spark.manifest.manifest import ManifestManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(workspace_root: Path, engine_root: Path) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_root=workspace_root,
        github_root=workspace_root / ".github",
        engine_root=engine_root,
    )


def _write_spark_packages(github_root: Path, packages: list[str], auto_install: bool = True) -> None:
    github_root.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"packages": packages, "auto_install": auto_install}
    (github_root / "spark-packages.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def _seed_manifest(github_root: Path, owners: dict[str, str]) -> None:
    """Crea un manifest con almeno un file per owner per simulare 'installato'."""
    manifest = ManifestManager(github_root)
    for owner, version in owners.items():
        rel = f"agents/{owner}-fixture.md"
        path = github_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# fixture {owner}\n", encoding="utf-8")
        manifest.upsert_many(owner, version, [(rel, path)])


def _make_manager(
    workspace_root: Path,
    engine_root: Path,
) -> tuple[OnboardingManager, MagicMock, MagicMock]:
    ctx = _make_ctx(workspace_root, engine_root)
    inventory = MagicMock(name="FrameworkInventory")
    app = MagicMock(name="SparkFrameworkEngine")
    manager = OnboardingManager(ctx, inventory, app)
    return manager, inventory, app


# ---------------------------------------------------------------------------
# is_first_run
# ---------------------------------------------------------------------------


def test_is_first_run_all_packages_installed_returns_false(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()
    _write_spark_packages(workspace / ".github", ["spark-base"])
    _seed_manifest(workspace / ".github", {"spark-base": "1.0.0"})

    manager, _, _ = _make_manager(workspace, engine)
    assert manager.is_first_run() is False


def test_is_first_run_missing_package_returns_true(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()
    _write_spark_packages(workspace / ".github", ["spark-base", "scf-pycode-crafter"])
    _seed_manifest(workspace / ".github", {"spark-base": "1.0.0"})

    manager, _, _ = _make_manager(workspace, engine)
    assert manager.is_first_run() is True


def test_is_first_run_no_file_legacy_empty_manifest_returns_true(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()
    (workspace / ".github").mkdir(parents=True)

    manager, _, _ = _make_manager(workspace, engine)
    assert manager.is_first_run() is True


def test_is_first_run_no_file_legacy_with_manifest_returns_false(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()
    _seed_manifest(workspace / ".github", {"spark-base": "1.0.0"})

    manager, _, _ = _make_manager(workspace, engine)
    assert manager.is_first_run() is False


def test_is_first_run_auto_install_false_returns_false(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()
    _write_spark_packages(workspace / ".github", ["spark-base"], auto_install=False)

    manager, _, _ = _make_manager(workspace, engine)
    assert manager.is_first_run() is False


def test_is_first_run_empty_packages_list_returns_false(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()
    _write_spark_packages(workspace / ".github", [])

    manager, _, _ = _make_manager(workspace, engine)
    assert manager.is_first_run() is False


def test_is_first_run_corrupted_file_returns_false(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()
    gh = workspace / ".github"
    gh.mkdir(parents=True)
    (gh / "spark-packages.json").write_text("{not valid json", encoding="utf-8")

    manager, _, _ = _make_manager(workspace, engine)
    assert manager.is_first_run() is False


# ---------------------------------------------------------------------------
# _install_declared_packages
# ---------------------------------------------------------------------------


def test_install_declared_no_file_returns_empty(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()
    (workspace / ".github").mkdir(parents=True)

    manager, _, app = _make_manager(workspace, engine)
    result = manager._install_declared_packages()
    assert result == []
    app.install_package_for_onboarding.assert_not_called()


def test_install_declared_auto_install_false_returns_empty(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()
    _write_spark_packages(workspace / ".github", ["spark-base"], auto_install=False)

    manager, _, app = _make_manager(workspace, engine)
    result = manager._install_declared_packages()
    assert result == []
    app.install_package_for_onboarding.assert_not_called()


def test_install_declared_already_installed_skipped(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()
    _write_spark_packages(workspace / ".github", ["spark-base"])
    _seed_manifest(workspace / ".github", {"spark-base": "1.0.0"})

    manager, _, app = _make_manager(workspace, engine)
    result = manager._install_declared_packages()
    assert result == []
    app.install_package_for_onboarding.assert_not_called()


def test_install_declared_installs_missing_package(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()
    _write_spark_packages(workspace / ".github", ["spark-base"])

    manager, _, app = _make_manager(workspace, engine)

    async def _ok(_pkg: str) -> dict[str, Any]:
        return {"success": True, "message": "installed"}

    app.install_package_for_onboarding.side_effect = _ok

    result = manager._install_declared_packages()
    assert result == ["spark-base"]
    app.install_package_for_onboarding.assert_called_once_with("spark-base")


def test_install_declared_install_failure_no_crash(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()
    _write_spark_packages(workspace / ".github", ["spark-base"])

    manager, _, app = _make_manager(workspace, engine)

    async def _fail(_pkg: str) -> dict[str, Any]:
        return {"success": False, "error": "registry down"}

    app.install_package_for_onboarding.side_effect = _fail

    result = manager._install_declared_packages()
    assert result == []


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_install_declared_runtime_error_skipped_silently(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()
    _write_spark_packages(workspace / ".github", ["spark-base"])

    manager, _, app = _make_manager(workspace, engine)
    # Simula event loop attivo: install_package_for_onboarding non viene
    # mai await-ata perché asyncio.run rifiuta. Configuriamo il mock per
    # restituire una coroutine valida; il RuntimeError viene generato
    # iniettando un side_effect di asyncio.run via monkeypatching.

    async def _coro(_pkg: str) -> dict[str, Any]:
        return {"success": True}

    app.install_package_for_onboarding.side_effect = _coro

    import asyncio as _asyncio

    original_run = _asyncio.run

    def _raise(*_a: Any, **_kw: Any) -> Any:
        raise RuntimeError("event loop is already running")

    try:
        _asyncio.run = _raise  # type: ignore[assignment]
        result = manager._install_declared_packages()
    finally:
        _asyncio.run = original_run  # type: ignore[assignment]

    assert result == []


def test_install_declared_packages_field_not_list_returns_empty(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()
    gh = workspace / ".github"
    gh.mkdir(parents=True)
    (gh / "spark-packages.json").write_text(
        json.dumps({"packages": "spark-base", "auto_install": True}),
        encoding="utf-8",
    )

    manager, _, app = _make_manager(workspace, engine)
    result = manager._install_declared_packages()
    assert result == []
    app.install_package_for_onboarding.assert_not_called()


# ---------------------------------------------------------------------------
# run_onboarding
# ---------------------------------------------------------------------------


def _setup_app_for_run_onboarding(
    app: MagicMock,
    bootstrap_required_paths: tuple[Path, ...],
    bootstrap_status: str = "bootstrapped",
    bootstrap_success: bool = True,
) -> None:
    app._minimal_bootstrap_required_paths.return_value = bootstrap_required_paths
    app.ensure_minimal_bootstrap.return_value = {
        "success": bootstrap_success,
        "status": bootstrap_status,
    }


def test_run_onboarding_status_completed(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()
    _write_spark_packages(workspace / ".github", ["spark-base"])
    # Prepara un sentinel mancante per forzare _ensure_bootstrap a chiamare l'app
    sentinel = workspace / ".github" / "AGENTS.md"
    sentinel.parent.mkdir(parents=True, exist_ok=True)

    manager, _, app = _make_manager(workspace, engine)
    _setup_app_for_run_onboarding(app, (sentinel,))

    # Crea uno store fittizio con un pacchetto: store_populated → True
    store_dir = engine / "packages" / "spark-base"
    store_dir.mkdir(parents=True)
    (store_dir / "package-manifest.json").write_text("{}", encoding="utf-8")

    async def _ok(_pkg: str) -> dict[str, Any]:
        # Simula side-effect dell'install: registra il pacchetto nel manifest
        # così il prossimo is_first_run torna False (idempotenza).
        _seed_manifest(workspace / ".github", {"spark-base": "1.0.0"})
        return {"success": True, "message": "installed"}

    app.install_package_for_onboarding.side_effect = _ok

    result = manager.run_onboarding()

    assert result["status"] == "completed"
    assert "bootstrap" in result["steps_completed"]
    assert "store_populated" in result["steps_completed"]
    assert "declared_packages" in result["steps_completed"]
    assert result["packages_installed"] == ["spark-base"]
    assert result["errors"] == []


def test_run_onboarding_partial_when_bootstrap_step_raises(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()
    (workspace / ".github").mkdir(parents=True)

    manager, _, app = _make_manager(workspace, engine)
    sentinel = workspace / ".github" / "AGENTS.md"
    app._minimal_bootstrap_required_paths.return_value = (sentinel,)
    app.ensure_minimal_bootstrap.side_effect = RuntimeError("bootstrap failure")

    result = manager.run_onboarding()
    assert result["status"] == "partial"
    assert "bootstrap" in result["steps_skipped"]
    assert any("Bootstrap step error" in e for e in result["errors"])


def test_run_onboarding_skipped_when_no_steps_completed(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()
    (workspace / ".github").mkdir(parents=True)
    # spark-packages.json presente con auto_install=False → _ensure_workspace_dir
    # ritorna False (nulla da creare) e _install_declared_packages salta.
    _write_spark_packages(workspace / ".github", ["spark-base"], auto_install=False)

    manager, _, app = _make_manager(workspace, engine)
    # Bootstrap già presente → step bootstrap saltato (returns False)
    sentinel = workspace / ".github" / "AGENTS.md"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text("present", encoding="utf-8")
    app._minimal_bootstrap_required_paths.return_value = (sentinel,)
    # Store assente, auto_install=False → tutti gli step business skipped

    result = manager.run_onboarding()
    assert result["status"] == "skipped"
    assert result["steps_completed"] == []
    assert "workspace_dir" in result["steps_skipped"]
    assert "bootstrap" in result["steps_skipped"]
    assert "store_populated" in result["steps_skipped"]
    assert "declared_packages" in result["steps_skipped"]


# ---------------------------------------------------------------------------
# E2E minimal-mock (R2 — audit Step 5 2026-05-09)
# ---------------------------------------------------------------------------
#
# Obiettivo: verificare l'intera catena run_onboarding() su workspace vergine
# con mock limitati alle sole dipendenze esterne (rete + engine core).
# Conferma che ANOMALIA-NEW (import path corretto) non sia l'unica causa
# storica dei "partial" rilevando regressioni future di idempotenza.


def test_run_onboarding_e2e_minimal_mock_virgin_workspace(tmp_path: Path) -> None:
    """E2E run_onboarding() con mock minimi su workspace vergine.

    Verifica:
    - is_first_run() == True prima dell'onboarding (workspace vergine)
    - run_onboarding() restituisce status == "completed"
    - packages_installed contiene il pacchetto dichiarato
    - steps_completed copre bootstrap, store_populated, declared_packages
    - errors è lista vuota
    - idempotenza: dopo l'install il manifest contiene il pacchetto

    Mock applicati (e motivazione):
    - ``app._minimal_bootstrap_required_paths``: restituisce un path non
      esistente per forzare l'esecuzione del bootstrap. Necessario perché
      ``SparkFrameworkEngine`` non è istanziabile senza FastMCP + server.
    - ``app.ensure_minimal_bootstrap``: evita la scrittura reale su .github/.
      L'output del bootstrap Cat.A non è oggetto di questo test.
    - ``app.install_package_for_onboarding``: evita download di rete.
      Il side_effect registra il pacchetto nel manifest (come farebbe il
      codice reale) per garantire idempotenza del flusso.

    Tutti gli altri componenti (WorkspaceContext, ManifestManager,
    PackageResourceStore, FileSystem) sono reali e operano su tmp_path.
    """
    workspace = tmp_path / "ws"
    engine = tmp_path / "engine"
    engine.mkdir()

    # --- Setup workspace vergine con spark-packages.json ---
    _write_spark_packages(workspace / ".github", ["spark-base"], auto_install=True)

    # --- Setup store locale reale (simula pacchetto già nel bundle engine) ---
    store_dir = engine / "packages" / "spark-base"
    store_dir.mkdir(parents=True)
    (store_dir / "package-manifest.json").write_text("{}", encoding="utf-8")

    # --- Costruisce manager con mock minimi ---
    manager, _, app = _make_manager(workspace, engine)

    # Mock 1: sentinel non esistente → bootstrap viene eseguito
    sentinel = workspace / ".github" / "AGENTS.md"
    app._minimal_bootstrap_required_paths.return_value = (sentinel,)
    app.ensure_minimal_bootstrap.return_value = {"success": True, "status": "bootstrapped"}

    # Mock 2: install con side-effect reale (scrive manifest come il vero install)
    async def _install_and_register(pkg: str) -> dict[str, Any]:
        # Registra il pacchetto nel manifest, come farebbe _install_package_v3.
        _seed_manifest(workspace / ".github", {pkg: "1.0.0"})
        return {"success": True, "message": f"installed {pkg}"}

    app.install_package_for_onboarding.side_effect = _install_and_register

    # --- Verifica precondizione: workspace vergine = primo avvio ---
    assert manager.is_first_run() is True, "il workspace vergine deve essere primo avvio"

    # --- Esegue onboarding ---
    result = manager.run_onboarding()

    # --- Asserzioni stato finale ---
    assert result["status"] == "completed", f"stato atteso 'completed', ottenuto: {result}"
    assert result["errors"] == [], f"nessun errore atteso, trovati: {result['errors']}"
    assert "spark-base" in result["packages_installed"]
    assert "bootstrap" in result["steps_completed"]
    assert "store_populated" in result["steps_completed"]
    assert "declared_packages" in result["steps_completed"]

    # --- Verifica idempotenza post-install ---
    # Il manifest deve ora contenere spark-base → is_first_run deve tornare False.
    assert manager.is_first_run() is False, (
        "dopo l'installazione is_first_run deve tornare False (idempotenza)"
    )

    # --- Verifica che app.install_package_for_onboarding sia stato chiamato una volta ---
    app.install_package_for_onboarding.assert_called_once_with("spark-base")
