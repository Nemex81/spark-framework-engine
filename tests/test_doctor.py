"""Tests for spark.cli.doctor — scf doctor command."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from spark.cli.doctor import run_doctor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Un workspace tmp con .github/ presente."""
    github = tmp_path / ".github"
    github.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture()
def github_root(workspace: Path) -> Path:
    return workspace / ".github"


@pytest.fixture()
def engine_root(tmp_path: Path) -> Path:
    return tmp_path / "engine"


# ---------------------------------------------------------------------------
# Test 1: basic call returns a dict with required keys
# ---------------------------------------------------------------------------


def test_doctor_returns_required_keys(github_root: Path, engine_root: Path) -> None:
    """run_doctor() restituisce sempre un dict con success, status, checks."""
    result = run_doctor(github_root, engine_root)
    assert isinstance(result, dict)
    assert "success" in result
    assert "status" in result
    assert "checks" in result
    assert "errors" in result
    assert "warnings" in result
    assert "engine_version" in result
    assert "timestamp" in result


# ---------------------------------------------------------------------------
# Test 2: github_root presente → check ok
# ---------------------------------------------------------------------------


def test_doctor_github_root_present_ok(github_root: Path, engine_root: Path) -> None:
    """Se .github/ esiste, il check github_root ha status 'ok'."""
    result = run_doctor(github_root, engine_root)
    check = next(c for c in result["checks"] if c["name"] == "github_root")
    assert check["status"] == "ok"


# ---------------------------------------------------------------------------
# Test 3: github_root assente → check error
# ---------------------------------------------------------------------------


def test_doctor_detects_missing_github_root(tmp_path: Path, engine_root: Path) -> None:
    """Se .github/ è assente, il check ha status 'error'."""
    missing = tmp_path / "nonexistent" / ".github"
    result = run_doctor(missing, engine_root)
    check = next(c for c in result["checks"] if c["name"] == "github_root")
    assert check["status"] == "error"
    assert result["success"] is False
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Test 4: github_root assente + fix → crea directory
# ---------------------------------------------------------------------------


def test_doctor_fix_creates_github_root(tmp_path: Path, engine_root: Path) -> None:
    """Con fix=True, .github/ assente viene creata automaticamente."""
    missing = tmp_path / "new_workspace" / ".github"
    assert not missing.exists()
    result = run_doctor(missing, engine_root, fix=True)
    assert missing.is_dir()
    check = next(c for c in result["checks"] if c["name"] == "github_root")
    assert check["status"] == "ok"
    assert result.get("fixed")
    assert any("github" in f.lower() for f in result["fixed"])


# ---------------------------------------------------------------------------
# Test 5: engine_version sempre riportata correttamente
# ---------------------------------------------------------------------------


def test_doctor_engine_version_check(github_root: Path, engine_root: Path) -> None:
    """Il check engine_version riporta la versione motore corrente."""
    from spark.core.constants import ENGINE_VERSION

    result = run_doctor(github_root, engine_root)
    check = next(c for c in result["checks"] if c["name"] == "engine_version")
    assert check["status"] == "ok"
    assert ENGINE_VERSION in check["message"]
    assert result["engine_version"] == ENGINE_VERSION


# ---------------------------------------------------------------------------
# Test 6: update_policy.json assente → warning (non errore)
# ---------------------------------------------------------------------------


def test_doctor_missing_update_policy_is_warning(
    github_root: Path, engine_root: Path
) -> None:
    """update_policy.json assente genera un warning, non un errore critico."""
    result = run_doctor(github_root, engine_root)
    check = next(c for c in result["checks"] if c["name"] == "update_policy")
    assert check["status"] == "warning"
    # Non deve essere un errore critico
    assert result["status"] != "error" or len(result["errors"]) == 0 or all(
        "update_policy" not in e for e in result["errors"]
    )


# ---------------------------------------------------------------------------
# Test 7: report=True → emette JSON valido su stdout
# ---------------------------------------------------------------------------


def test_doctor_report_flag_emits_json(
    github_root: Path, engine_root: Path, capsys: pytest.CaptureFixture
) -> None:
    """Con report=True, il JSON del report viene stampato su stdout."""
    run_doctor(github_root, engine_root, report=True)
    out = capsys.readouterr().out
    # Deve essere JSON valido
    parsed = json.loads(out)
    assert "success" in parsed
    assert "checks" in parsed


# ---------------------------------------------------------------------------
# Test 8: lockfile out-of-sync → warning
# ---------------------------------------------------------------------------


def test_doctor_lockfile_out_of_sync_warning(
    github_root: Path, workspace: Path, engine_root: Path
) -> None:
    """.spark/scf-lock.json con entry stale genera un warning."""
    from spark.manifest.lockfile import LockfileManager

    # Aggiungi entry stale nel lockfile (package non nel manifest)
    mgr = LockfileManager(workspace)
    mgr.upsert("ghost-package", "1.0.0", "U2", [], None)

    result = run_doctor(github_root, engine_root)
    check = next(c for c in result["checks"] if c["name"] == "lockfile")
    assert check["status"] == "warning"
    assert "ghost-package" in check["message"]


# ---------------------------------------------------------------------------
# Test 9: fix=True sincronizza lockfile stale
# ---------------------------------------------------------------------------


def test_doctor_fix_removes_stale_lockfile_entry(
    github_root: Path, workspace: Path, engine_root: Path
) -> None:
    """Con fix=True, le entry stale nel lockfile vengono rimosse."""
    from spark.manifest.lockfile import LockfileManager

    mgr = LockfileManager(workspace)
    mgr.upsert("stale-pkg", "1.0.0", "U2", [], None)
    assert mgr.get("stale-pkg") is not None

    result = run_doctor(github_root, engine_root, fix=True)

    # Dopo fix, l'entry stale deve essere rimossa
    assert mgr.get("stale-pkg") is None
    assert result.get("fixed")


# ---------------------------------------------------------------------------
# Test 10: status ok se tutto presente e sincronizzato
# ---------------------------------------------------------------------------


def test_doctor_full_ok_status(
    github_root: Path, workspace: Path, engine_root: Path
) -> None:
    """Se .github/ e lockfile sono in sync e non ci sono errori, status='ok'."""
    # Non ci sono pacchetti installati né entry lockfile → tutto in sync
    result = run_doctor(github_root, engine_root)
    # Non deve avere errori critici
    assert result["errors"] == []
    assert result["success"] is True
    assert result["status"] in ("ok", "warning")  # warning da policy assente è ok
