# tests/test_workspace_gateway.py
"""Test suite per WorkspaceWriteGateway — tracciamento scritture workspace .github/."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from spark.manifest.gateway import WorkspaceWriteGateway
from spark.manifest.manifest import ManifestManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Crea una struttura workspace minimale e restituisce (workspace_root, github_root)."""
    github_root = tmp_path / ".github"
    github_root.mkdir(parents=True, exist_ok=True)
    return tmp_path, github_root


def _make_gateway(tmp_path: Path) -> tuple[WorkspaceWriteGateway, ManifestManager, Path]:
    """Restituisce (gateway, manifest, github_root) per un workspace temporaneo."""
    workspace_root, github_root = _make_workspace(tmp_path)
    manifest = ManifestManager(github_root)
    gateway = WorkspaceWriteGateway(workspace_root, manifest)
    return gateway, manifest, github_root


# ---------------------------------------------------------------------------
# Test: write
# ---------------------------------------------------------------------------


class TestGatewayWrite:
    def test_write_creates_file(self, tmp_path: Path) -> None:
        gateway, _, github_root = _make_gateway(tmp_path)
        target = gateway.write("AGENTS.md", "# Agents\n", "spark-engine", "3.1.0")
        assert target == github_root / "AGENTS.md"
        assert target.read_text(encoding="utf-8") == "# Agents\n"

    def test_write_tracks_in_manifest(self, tmp_path: Path) -> None:
        gateway, manifest, _ = _make_gateway(tmp_path)
        gateway.write("AGENTS.md", "# Agents\n", "spark-engine", "3.1.0")
        entries = manifest.load()
        match = [e for e in entries if e.get("file") == "AGENTS.md"]
        assert len(match) == 1
        entry = match[0]
        assert entry["package"] == "spark-engine"
        assert entry["package_version"] == "3.1.0"
        assert "sha256" in entry

    def test_write_creates_parent_dirs(self, tmp_path: Path) -> None:
        gateway, _, github_root = _make_gateway(tmp_path)
        gateway.write("agents/spark-assistant.agent.md", "content", "spark-engine", "3.1.0")
        assert (github_root / "agents" / "spark-assistant.agent.md").is_file()

    def test_write_overwrites_existing_and_updates_manifest(self, tmp_path: Path) -> None:
        gateway, manifest, github_root = _make_gateway(tmp_path)
        gateway.write("AGENTS.md", "v1\n", "spark-engine", "3.1.0")
        gateway.write("AGENTS.md", "v2\n", "spark-engine", "3.1.0")
        assert (github_root / "AGENTS.md").read_text(encoding="utf-8") == "v2\n"
        entries = [e for e in manifest.load() if e.get("file") == "AGENTS.md"]
        # upsert should keep only one entry per (file, owner)
        assert len(entries) == 1

    def test_write_returns_absolute_path(self, tmp_path: Path) -> None:
        gateway, _, github_root = _make_gateway(tmp_path)
        result = gateway.write("test.md", "x", "pkg", "1.0.0")
        assert result.is_absolute()
        assert result == github_root / "test.md"


# ---------------------------------------------------------------------------
# Test: write_bytes
# ---------------------------------------------------------------------------


class TestGatewayWriteBytes:
    def test_write_bytes_creates_file(self, tmp_path: Path) -> None:
        gateway, _, github_root = _make_gateway(tmp_path)
        data = b"\x89PNG\r\n"
        gateway.write_bytes("assets/icon.png", data, "spark-engine", "3.1.0")
        assert (github_root / "assets" / "icon.png").read_bytes() == data

    def test_write_bytes_tracks_in_manifest(self, tmp_path: Path) -> None:
        gateway, manifest, _ = _make_gateway(tmp_path)
        gateway.write_bytes("assets/icon.png", b"bytes", "spark-engine", "3.1.0")
        entries = [e for e in manifest.load() if e.get("file") == "assets/icon.png"]
        assert len(entries) == 1
        assert entries[0]["package"] == "spark-engine"


# ---------------------------------------------------------------------------
# Test: delete
# ---------------------------------------------------------------------------


class TestGatewayDelete:
    def test_delete_existing_file(self, tmp_path: Path) -> None:
        gateway, manifest, github_root = _make_gateway(tmp_path)
        gateway.write("AGENTS.md", "# Agents\n", "spark-engine", "3.1.0")
        result = gateway.delete("AGENTS.md", "spark-engine")
        assert result is True
        assert not (github_root / "AGENTS.md").exists()

    def test_delete_removes_manifest_entry(self, tmp_path: Path) -> None:
        gateway, manifest, _ = _make_gateway(tmp_path)
        gateway.write("AGENTS.md", "# Agents\n", "spark-engine", "3.1.0")
        gateway.delete("AGENTS.md", "spark-engine")
        entries = [e for e in manifest.load() if e.get("file") == "AGENTS.md"]
        assert len(entries) == 0

    def test_delete_missing_file_returns_false(self, tmp_path: Path) -> None:
        gateway, _, _ = _make_gateway(tmp_path)
        result = gateway.delete("nonexistent.md", "pkg")
        assert result is False

    def test_delete_only_removes_matching_owner_entry(self, tmp_path: Path) -> None:
        """Delete rimuove solo l'entry dell'owner specificato, lascia le altre."""
        workspace_root, github_root = _make_workspace(tmp_path)
        manifest = ManifestManager(github_root)
        # Aggiungiamo manualmente due entry per lo stesso file ma owner diverso.
        target = github_root / "shared.md"
        target.write_text("shared", encoding="utf-8")
        manifest.upsert("shared.md", "pkg-a", "1.0.0", target)
        manifest.upsert("shared.md", "pkg-b", "2.0.0", target)
        assert len([e for e in manifest.load() if e.get("file") == "shared.md"]) == 2

        gateway = WorkspaceWriteGateway(workspace_root, manifest)
        gateway.delete("shared.md", "pkg-a")
        entries = [e for e in manifest.load() if e.get("file") == "shared.md"]
        # pkg-b entry should remain
        assert len(entries) == 1
        assert entries[0]["package"] == "pkg-b"


# ---------------------------------------------------------------------------
# Test: idempotency
# ---------------------------------------------------------------------------


class TestGatewayIdempotency:
    def test_write_same_content_twice_is_idempotent(self, tmp_path: Path) -> None:
        gateway, manifest, _ = _make_gateway(tmp_path)
        gateway.write("AGENTS.md", "content\n", "spark-engine", "3.1.0")
        sha_before = [e for e in manifest.load() if e.get("file") == "AGENTS.md"][0]["sha256"]
        gateway.write("AGENTS.md", "content\n", "spark-engine", "3.1.0")
        sha_after = [e for e in manifest.load() if e.get("file") == "AGENTS.md"][0]["sha256"]
        assert sha_before == sha_after


# ---------------------------------------------------------------------------
# Test: integration with _apply_phase6_assets
# ---------------------------------------------------------------------------


class TestPhase6GatewayIntegration:
    def test_apply_phase6_with_gateway_tracks_agents_md(self, tmp_path: Path) -> None:
        from spark.assets.phase6 import _apply_phase6_assets

        workspace_root, github_root = _make_workspace(tmp_path)
        # Create minimal engine structure for phase6 collectors
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        (engine_root / "packages").mkdir()

        manifest = ManifestManager(github_root)
        gateway = WorkspaceWriteGateway(workspace_root, manifest)

        report = _apply_phase6_assets(
            workspace_root=workspace_root,
            engine_root=engine_root,
            installed_packages=[],
            github_write_authorized=True,
            gateway=gateway,
            engine_version="3.1.0",
        )

        # AGENTS.md should be created and tracked
        assert (github_root / "AGENTS.md").is_file()
        agents_entries = [
            e for e in manifest.load() if e.get("file") == "AGENTS.md"
        ]
        assert len(agents_entries) == 1
        assert agents_entries[0]["package"] == "spark-engine"
        assert agents_entries[0]["package_version"] == "3.1.0"

    def test_apply_phase6_without_gateway_no_manifest_tracking(self, tmp_path: Path) -> None:
        from spark.assets.phase6 import _apply_phase6_assets

        workspace_root, github_root = _make_workspace(tmp_path)
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        (engine_root / "packages").mkdir()

        manifest = ManifestManager(github_root)

        report = _apply_phase6_assets(
            workspace_root=workspace_root,
            engine_root=engine_root,
            installed_packages=[],
            github_write_authorized=True,
            # No gateway → legacy direct write
        )

        # AGENTS.md written but NOT tracked in manifest
        assert (github_root / "AGENTS.md").is_file()
        agents_entries = [
            e for e in manifest.load() if e.get("file") == "AGENTS.md"
        ]
        assert len(agents_entries) == 0
