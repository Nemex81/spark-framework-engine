"""Tests for v3 workspace_files install/remove helpers.

Verifica scenari multi-owner (incluso ``scf-engine-bootstrap``) e file non
tracciati nel manifest, per garantire che il refactoring Round 2/3 preservi
correttamente i file modificati dall'utente.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

FrameworkInventory: Any = _module.FrameworkInventory
ManifestManager: Any = _module.ManifestManager
SparkFrameworkEngine: Any = _module.SparkFrameworkEngine
WorkspaceContext: Any = _module.WorkspaceContext


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self):
        def _decorator(func):
            self.tools[func.__name__] = func
            return func

        return _decorator

    def resource(self, *_args, **_kwargs):
        def _decorator(func):
            return func

        return _decorator


def _build_engine(workspace_root: Path) -> Any:
    ctx = WorkspaceContext(
        workspace_root=workspace_root,
        github_root=workspace_root / ".github",
        engine_root=_ENGINE_PATH.parent,
    )
    inventory = FrameworkInventory(ctx)
    mcp = _FakeMCP()
    engine = SparkFrameworkEngine(mcp, ctx, inventory)
    return engine


def _seed_store_file(
    engine_root: Path,
    package_id: str,
    rel_path: str,
    content: str,
) -> Path:
    """Crea un file fittizio nel deposito centrale dello store v3."""
    target = engine_root / "packages" / package_id / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


class TestInstallWorkspaceFilesMultiOwner(unittest.TestCase):
    """Fix 1 + Fix 5 Round 3 — preservation gate con bootstrap shadow owner."""

    def test_preserve_user_modified_multi_owner_with_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_engine, tempfile.TemporaryDirectory() as tmp_ws:
            engine_root = Path(tmp_engine)
            workspace_root = Path(tmp_ws)
            # Costruiamo il pacchetto installer fittizio (scf-pycode-crafter).
            entry = ".github/copilot-instructions.md"
            _seed_store_file(
                engine_root,
                "scf-pycode-crafter",
                entry,
                "fresh content from pycode crafter v1.0.0\n",
            )
            ctx = WorkspaceContext(
                workspace_root=workspace_root,
                github_root=workspace_root / ".github",
                engine_root=engine_root,
            )
            inventory = FrameworkInventory(ctx)
            mcp = _FakeMCP()
            engine = SparkFrameworkEngine(mcp, ctx, inventory)
            manifest = ManifestManager(ctx.github_root)
            pkg_manifest = {
                "package": "scf-pycode-crafter",
                "version": "1.0.0",
                "workspace_files": [entry],
            }
            with patch.object(
                ManifestManager,
                "get_file_owners",
                return_value=["scf-engine-bootstrap", "spark-base"],
            ), patch.object(
                ManifestManager,
                "is_user_modified",
                return_value=True,
            ):
                result = engine._install_workspace_files_v3(
                    package_id="scf-pycode-crafter",
                    pkg_version="1.0.0",
                    pkg_manifest=pkg_manifest,
                    manifest=manifest,
                )
            self.assertTrue(result["success"])
            self.assertIn(entry, result["preserved"])
            self.assertEqual(result["files_written"], [])

    def test_write_unmodified_multi_owner_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_engine, tempfile.TemporaryDirectory() as tmp_ws:
            engine_root = Path(tmp_engine)
            workspace_root = Path(tmp_ws)
            entry = ".github/copilot-instructions.md"
            _seed_store_file(
                engine_root,
                "scf-pycode-crafter",
                entry,
                "fresh content\n",
            )
            ctx = WorkspaceContext(
                workspace_root=workspace_root,
                github_root=workspace_root / ".github",
                engine_root=engine_root,
            )
            inventory = FrameworkInventory(ctx)
            mcp = _FakeMCP()
            engine = SparkFrameworkEngine(mcp, ctx, inventory)
            manifest = ManifestManager(ctx.github_root)
            pkg_manifest = {
                "package": "scf-pycode-crafter",
                "version": "1.0.0",
                "workspace_files": [entry],
            }
            with patch.object(
                ManifestManager,
                "get_file_owners",
                return_value=["scf-engine-bootstrap", "spark-base"],
            ), patch.object(
                ManifestManager,
                "is_user_modified",
                return_value=False,
            ):
                result = engine._install_workspace_files_v3(
                    package_id="scf-pycode-crafter",
                    pkg_version="1.0.0",
                    pkg_manifest=pkg_manifest,
                    manifest=manifest,
                )
            self.assertTrue(result["success"])
            self.assertIn(entry, result["files_written"])
            self.assertEqual(result["preserved"], [])
            written = workspace_root / ".github" / "copilot-instructions.md"
            self.assertTrue(written.is_file())


class TestRemoveWorkspaceFilesUntracked(unittest.TestCase):
    """Fix 2 Round 3 — file non tracciato nel manifest deve essere preservato."""

    def test_preserve_untracked_on_remove(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_engine, tempfile.TemporaryDirectory() as tmp_ws:
            engine_root = Path(tmp_engine)
            workspace_root = Path(tmp_ws)
            entry = ".github/copilot-instructions.md"
            target = workspace_root / ".github" / "copilot-instructions.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("untracked file content\n", encoding="utf-8")
            ctx = WorkspaceContext(
                workspace_root=workspace_root,
                github_root=workspace_root / ".github",
                engine_root=engine_root,
            )
            inventory = FrameworkInventory(ctx)
            mcp = _FakeMCP()
            engine = SparkFrameworkEngine(mcp, ctx, inventory)
            manifest = ManifestManager(ctx.github_root)
            pkg_manifest = {
                "package": "spark-base",
                "version": "1.6.1",
                "workspace_files": [entry],
            }
            with patch.object(
                ManifestManager,
                "get_file_owners",
                return_value=[],
            ), patch.object(
                ManifestManager,
                "is_user_modified",
                return_value=False,
            ):
                result = engine._remove_workspace_files_v3(
                    package_id="spark-base",
                    pkg_manifest=pkg_manifest,
                    manifest=manifest,
                )
            self.assertIn(entry, result["preserved"])
            self.assertEqual(result["removed"], [])
            self.assertTrue(
                target.is_file(),
                "Untracked workspace_files entry must NOT be deleted on remove.",
            )


if __name__ == "__main__":
    unittest.main()
