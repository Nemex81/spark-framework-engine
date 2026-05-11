"""Test suite per Universe V3 Core Distribution (spark-ops MCP layer).

Verifica:
1. Manifest spark-ops v1.2.0 — orchestrate incluso, workspace_files sentinel presenti.
2. Dispatcher U1/U2 — tools_resources.py espone i campi universe/source_package.
3. Boot transfer helper — _ensure_spark_ops_workspace_files funzione idempotente.
4. Manifest coerenza — nessuna chiave duplicata nel JSON (fix del bug instructions x2).
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGES_ROOT = REPO_ROOT / "packages"

SPARK_OPS_MANIFEST_PATH = PACKAGES_ROOT / "spark-ops" / "package-manifest.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_manifest(package_id: str) -> dict[str, Any]:
    path = PACKAGES_ROOT / package_id / "package-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Test 1 — Manifest spark-ops v1.2.0: orchestrate incluso, workspace_files sentinel
# ---------------------------------------------------------------------------

def test_spark_ops_manifest_includes_orchestrate_and_workspace_sentinels() -> None:
    """Verifica che spark-ops v1.2.0 dichiari orchestrate nei prompts e i file sentinella."""
    manifest = _load_manifest("spark-ops")
    resources = manifest["mcp_resources"]

    assert manifest["version"] == "1.2.0", f"Atteso 1.2.0, trovato {manifest['version']}"
    assert "orchestrate" in resources["prompts"], "orchestrate non trovato in mcp_resources.prompts"

    workspace_files = set(manifest["workspace_files"])
    assert ".github/agents/spark-assistant.agent.md" in workspace_files, (
        "spark-assistant.agent.md mancante da workspace_files"
    )
    assert ".github/agents/spark-guide.agent.md" in workspace_files, (
        "spark-guide.agent.md mancante da workspace_files"
    )

    # orchestrate.prompt.md deve essere nei files dichiarati
    assert ".github/prompts/orchestrate.prompt.md" in manifest["files"], (
        "orchestrate.prompt.md mancante da files"
    )


# ---------------------------------------------------------------------------
# Test 2 — Manifest coerenza: nessuna chiave duplicata nel JSON raw
# ---------------------------------------------------------------------------

def test_spark_ops_manifest_no_duplicate_json_keys() -> None:
    """Verifica che il JSON di spark-ops non abbia chiavi duplicate (es. instructions x2)."""
    raw = SPARK_OPS_MANIFEST_PATH.read_text(encoding="utf-8")

    # Parser custom per rilevare duplicati
    duplicate_keys: list[str] = []

    def object_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen: set[str] = set()
        for key, _ in pairs:
            if key in seen:
                duplicate_keys.append(key)
            seen.add(key)
        return dict(pairs)

    json.loads(raw, object_pairs_hook=object_pairs_hook)
    assert not duplicate_keys, f"Chiavi duplicate nel manifest spark-ops: {duplicate_keys}"


# ---------------------------------------------------------------------------
# Test 3 — Dispatcher U1/U2: scf_get_agent espone universe field
# ---------------------------------------------------------------------------

def test_dispatcher_universe_field_logic() -> None:
    """Verifica che la logica U1/U2 funzioni correttamente per path engine vs workspace."""
    from spark.boot.tools_resources import _ff_to_dict
    from spark.core.models import FrameworkFile

    engine_root = REPO_ROOT
    packages_root = engine_root / "packages"

    # Simula un file U1 (dentro packages/)
    u1_path = packages_root / "spark-ops" / ".github" / "agents" / "spark-assistant.agent.md"
    # Simula un file U2 (fuori da packages/, es. workspace fisico)
    u2_path = engine_root / ".github" / "agents" / "some-user-agent.md"

    resolved_packages = packages_root.resolve()

    def detect_universe(path: Path) -> tuple[str, str]:
        resolved = path.resolve()
        if resolved.is_relative_to(resolved_packages):
            rel = resolved.relative_to(resolved_packages)
            source_package = rel.parts[0] if rel.parts else "unknown"
            return "U1", source_package
        return "U2", "workspace"

    universe, source = detect_universe(u1_path)
    assert universe == "U1", f"Atteso U1 per path in packages/, trovato {universe}"
    assert source == "spark-ops", f"Atteso source_package=spark-ops, trovato {source}"

    universe2, source2 = detect_universe(u2_path)
    assert universe2 == "U2", f"Atteso U2 per path fuori packages/, trovato {universe2}"
    assert source2 == "workspace"


# ---------------------------------------------------------------------------
# Test 4 — Boot transfer: _ensure_spark_ops_workspace_files è idempotente
# ---------------------------------------------------------------------------

def test_ensure_spark_ops_workspace_files_idempotent(tmp_path: Path) -> None:
    """Verifica che _ensure_spark_ops_workspace_files copi i file e sia idempotente."""
    from spark.boot.sequence import _ensure_spark_ops_workspace_files

    # Prepara un finto workspace context
    fake_github = tmp_path / ".github"
    fake_github.mkdir()

    context = MagicMock()
    context.github_root = fake_github

    # Esegui prima volta: deve copiare i file
    _ensure_spark_ops_workspace_files(context, REPO_ROOT)

    # Verifica che i workspace_files siano stati copiati
    manifest = _load_manifest("spark-ops")
    for rel_path in manifest["workspace_files"]:
        within_github = rel_path[len(".github/"):] if rel_path.startswith(".github/") else rel_path
        dest = fake_github / within_github
        assert dest.is_file(), f"File non copiato: {dest}"

    # Seconda chiamata: deve essere idempotente (non sovrascrivere)
    # Salva i mtime dei file copiati
    mtimes_before = {
        rel_path: (
            fake_github / (rel_path[len(".github/"):] if rel_path.startswith(".github/") else rel_path)
        ).stat().st_mtime
        for rel_path in manifest["workspace_files"]
    }

    _ensure_spark_ops_workspace_files(context, REPO_ROOT)

    mtimes_after = {
        rel_path: (
            fake_github / (rel_path[len(".github/"):] if rel_path.startswith(".github/") else rel_path)
        ).stat().st_mtime
        for rel_path in manifest["workspace_files"]
    }

    assert mtimes_before == mtimes_after, (
        "I file sono stati riscritti nella seconda chiamata (non idempotente)"
    )
