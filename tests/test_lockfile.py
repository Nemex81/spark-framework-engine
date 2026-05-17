"""Tests for spark.manifest.lockfile — LockfileManager."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from spark.manifest.lockfile import LockfileManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Return a tmp workspace root with no lockfile."""
    return tmp_path


@pytest.fixture()
def mgr(workspace: Path) -> LockfileManager:
    return LockfileManager(workspace)


# ---------------------------------------------------------------------------
# Test: load on missing file
# ---------------------------------------------------------------------------


def test_load_missing_returns_empty(mgr: LockfileManager) -> None:
    """load() on a non-existing lockfile returns an empty structure."""
    data = mgr.load()
    assert data["schema_version"] == "1.0"
    assert data["entries"] == {}


# ---------------------------------------------------------------------------
# Test: upsert crea entry e persiste su disco
# ---------------------------------------------------------------------------


def test_upsert_creates_entry(mgr: LockfileManager, workspace: Path) -> None:
    """upsert() crea l'entry nel lockfile e salva su disco."""
    mgr.upsert("spark-base", "1.2.0", "U2", ["dep-a"], {"agents/foo.md": "abc123"})

    lock_path = workspace / ".spark" / "scf-lock.json"
    assert lock_path.is_file()

    data = json.loads(lock_path.read_text(encoding="utf-8"))
    assert "spark-base" in data["entries"]
    entry = data["entries"]["spark-base"]
    assert entry["version"] == "1.2.0"
    assert entry["source"] == "U2"
    assert entry["dependencies"] == ["dep-a"]
    assert entry["files"] == {"agents/foo.md": "abc123"}
    assert "installed_at" in entry


# ---------------------------------------------------------------------------
# Test: upsert è idempotente (sovrascrive versione precedente)
# ---------------------------------------------------------------------------


def test_upsert_idempotent(mgr: LockfileManager) -> None:
    """upsert() sullo stesso package_id sovrascrive l'entry esistente."""
    mgr.upsert("spark-base", "1.0.0", "U2", [], None)
    mgr.upsert("spark-base", "2.0.0", "U2", ["dep-x"], None)

    entry = mgr.get("spark-base")
    assert entry is not None
    assert entry["version"] == "2.0.0"
    assert entry["dependencies"] == ["dep-x"]


# ---------------------------------------------------------------------------
# Test: remove entry
# ---------------------------------------------------------------------------


def test_remove_existing_entry(mgr: LockfileManager) -> None:
    """remove() elimina l'entry e restituisce True."""
    mgr.upsert("pkg-a", "0.1.0", "U1", [], None)
    assert mgr.get("pkg-a") is not None

    result = mgr.remove("pkg-a")
    assert result is True
    assert mgr.get("pkg-a") is None


def test_remove_missing_entry_returns_false(mgr: LockfileManager) -> None:
    """remove() su un package non esistente restituisce False."""
    result = mgr.remove("non-existent")
    assert result is False


# ---------------------------------------------------------------------------
# Test: get()
# ---------------------------------------------------------------------------


def test_get_returns_none_for_missing(mgr: LockfileManager) -> None:
    """get() restituisce None se il package non è nel lockfile."""
    assert mgr.get("ghost-package") is None


def test_get_returns_entry_for_known(mgr: LockfileManager) -> None:
    """get() restituisce l'entry corretta."""
    mgr.upsert("my-pkg", "3.0.0", "U2", ["dep1", "dep2"], None)
    entry = mgr.get("my-pkg")
    assert entry is not None
    assert entry["version"] == "3.0.0"
    assert sorted(entry["dependencies"]) == ["dep1", "dep2"]


# ---------------------------------------------------------------------------
# Test: compute_file_hashes
# ---------------------------------------------------------------------------


def test_compute_file_hashes_returns_sha256(tmp_path: Path) -> None:
    """compute_file_hashes() restituisce gli hash SHA-256 dei file leggibili."""
    (tmp_path / "hello.txt").write_text("hello world", encoding="utf-8")

    hashes = LockfileManager.compute_file_hashes(tmp_path, ["hello.txt"])
    assert "hello.txt" in hashes
    # Verifica che sia un hex sha256 (64 chars)
    assert len(hashes["hello.txt"]) == 64


def test_compute_file_hashes_skips_missing(tmp_path: Path) -> None:
    """compute_file_hashes() ignora silenziosamente i file non leggibili."""
    hashes = LockfileManager.compute_file_hashes(tmp_path, ["non_existent.txt"])
    assert hashes == {}


# ---------------------------------------------------------------------------
# Test: lockfile schema_version preservata dopo upsert multipli
# ---------------------------------------------------------------------------


def test_schema_version_preserved(mgr: LockfileManager) -> None:
    """La schema_version non cambia dopo operazioni multiple."""
    mgr.upsert("pkg-1", "1.0.0", "U2", [], None)
    mgr.upsert("pkg-2", "2.0.0", "U1", [], None)
    mgr.remove("pkg-1")

    data = mgr.load()
    assert data["schema_version"] == "1.0"
    assert "pkg-2" in data["entries"]
    assert "pkg-1" not in data["entries"]


# ---------------------------------------------------------------------------
# Test: lockfile corretto su file JSON corrotto
# ---------------------------------------------------------------------------


def test_load_corrupt_json_returns_empty(workspace: Path) -> None:
    """load() su file JSON non valido restituisce struttura vuota."""
    lock_dir = workspace / ".spark"
    lock_dir.mkdir(parents=True, exist_ok=True)
    (lock_dir / "scf-lock.json").write_text("{ INVALID JSON }", encoding="utf-8")

    mgr = LockfileManager(workspace)
    data = mgr.load()
    assert data["entries"] == {}


# ---------------------------------------------------------------------------
# Test: upsert senza files (None)
# ---------------------------------------------------------------------------


def test_upsert_without_files(mgr: LockfileManager) -> None:
    """upsert() con files=None non include 'files' nell'entry."""
    mgr.upsert("pkg-no-files", "1.0.0", "U2", [], None)
    entry = mgr.get("pkg-no-files")
    assert entry is not None
    assert "files" not in entry
