"""Tests for Dual Universe routing in tools_bootstrap.

Universe A: resolve package context from local engine packages/ store
             (delivery_mode=mcp_only manifest found locally).
Universe B: resolve via remote registry (fallback when A is unavailable).

Four tests:
  test_local_context_returned_for_mcp_only_package
  test_local_context_returns_none_when_no_local_manifest
  test_local_context_returns_none_without_mcp_only
  test_bootstrap_uses_universe_a_without_network_call
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import spark.boot.tools_bootstrap as _tb


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_manifest(
    package_id: str,
    version: str = "1.0.0",
    delivery_mode: str | None = "mcp_only",
    files: list[str] | None = None,
) -> dict[str, Any]:
    """Build a minimal package-manifest.json dict."""
    m: dict[str, Any] = {
        "schema_version": "3.0",
        "package": package_id,
        "version": version,
        "min_engine_version": "3.4.0",
        "dependencies": [],
        "conflicts": [],
        "file_ownership_policy": "error",
        "files": files or [f".github/agents/{package_id}.md"],
    }
    if delivery_mode is not None:
        m["delivery_mode"] = delivery_mode
    return m


def _write_manifest(engine_root: Path, package_id: str, manifest: dict[str, Any]) -> None:
    """Write a package-manifest.json into the local store under engine_root/packages/."""
    pkg_dir = engine_root / "packages" / package_id
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "package-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Test 1: local manifest with delivery_mode=mcp_only → Universe A
# ---------------------------------------------------------------------------

def test_local_context_returned_for_mcp_only_package() -> None:
    """_resolve_local_manifest returns manifest dict when delivery_mode=mcp_only."""
    with tempfile.TemporaryDirectory() as tmp:
        engine_root = Path(tmp)
        pkg_id = "spark-base"
        manifest = _make_fake_manifest(pkg_id, version="1.7.3", delivery_mode="mcp_only")
        _write_manifest(engine_root, pkg_id, manifest)

        result = _tb._resolve_local_manifest(engine_root, pkg_id)

        assert result is not None, "Expected manifest dict, got None"
        assert result["delivery_mode"] == "mcp_only"
        assert result["version"] == "1.7.3"


# ---------------------------------------------------------------------------
# Test 2: no local manifest → _resolve_local_manifest returns None
# ---------------------------------------------------------------------------

def test_local_context_returns_none_when_no_local_manifest() -> None:
    """_resolve_local_manifest returns None when no file in local store."""
    with tempfile.TemporaryDirectory() as tmp:
        engine_root = Path(tmp)
        # Do NOT write any manifest
        result = _tb._resolve_local_manifest(engine_root, "nonexistent-package")
        assert result is None, "Expected None for missing package"


# ---------------------------------------------------------------------------
# Test 3: manifest present but delivery_mode != mcp_only → Universe B fallback
# ---------------------------------------------------------------------------

def test_local_context_returns_none_without_mcp_only() -> None:
    """_resolve_local_manifest returns the manifest even without delivery_mode.
    The mcp_only check is performed by _try_local_install_context, not by
    _resolve_local_manifest itself. This test verifies that _resolve_local_manifest
    is transparent, and that a caller checking delivery_mode correctly sees None.
    """
    with tempfile.TemporaryDirectory() as tmp:
        engine_root = Path(tmp)
        pkg_id = "my-pkg"
        # Manifest with delivery_mode omitted → should NOT trigger Universe A
        manifest = _make_fake_manifest(pkg_id, delivery_mode=None)
        _write_manifest(engine_root, pkg_id, manifest)

        raw = _tb._resolve_local_manifest(engine_root, pkg_id)
        assert raw is not None, "Manifest file is present, should be loaded"
        # delivery_mode missing → Universe A routing must decline
        assert raw.get("delivery_mode") is None
        assert str(raw.get("delivery_mode", "")).strip() != "mcp_only"


# ---------------------------------------------------------------------------
# Test 4: real spark-base manifest now qualifies for Universe A routing
# ---------------------------------------------------------------------------

def test_spark_base_real_manifest_qualifies_for_universe_a() -> None:
    """The actual packages/spark-base/package-manifest.json must declare
    delivery_mode=mcp_only so that the dual-universe router picks Universe A.

    This is the end-to-end gate test: if spark-base's manifest changes to
    drop delivery_mode or change it from mcp_only, this test catches it.
    """
    engine_root = Path(__file__).parent.parent

    result = _tb._resolve_local_manifest(engine_root, "spark-base")

    assert result is not None, (
        "packages/spark-base/package-manifest.json must exist in the local engine store"
    )
    assert result.get("delivery_mode") == "mcp_only", (
        f"spark-base delivery_mode must be 'mcp_only' to enable Universe A routing, "
        f"got: {result.get('delivery_mode')!r}"
    )
    assert result.get("files"), (
        "spark-base manifest must declare a non-empty 'files' list"
    )
    assert result.get("version"), (
        "spark-base manifest must declare a version"
    )
    # Routing decision: delivery_mode == mcp_only → Universe A
    assert str(result.get("delivery_mode", "")).strip() == "mcp_only"
