"""Unit tests per _install_standalone_files_v3 — Task B.1."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

_spec = importlib.util.spec_from_file_location("spark_framework_engine_b1", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine_b1"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

SparkFrameworkEngine: Any = _module.SparkFrameworkEngine
ManifestManager: Any = _module.ManifestManager
PackageResourceStore: Any = _module.PackageResourceStore
WorkspaceContext: Any = _module.WorkspaceContext


def _make_engine_stub(tmp: Path) -> Any:
    """Crea un'istanza minimale di SparkFrameworkEngine per testare i metodi lifecycle."""
    engine_root = tmp / "engine"
    workspace = tmp / "workspace"
    ws_github = workspace / ".github"
    ws_github.mkdir(parents=True)
    engine_root.mkdir(parents=True)

    ctx = WorkspaceContext(
        workspace_root=workspace,
        github_root=ws_github,
        engine_root=engine_root,
    )
    eng = object.__new__(SparkFrameworkEngine)
    eng._ctx = ctx
    return eng


def _make_manifest(ws_github: Path) -> Any:
    return ManifestManager(ws_github)


def _seed_store_file(engine_root: Path, pkg_id: str, rel_path: str, content: str) -> None:
    """Crea un file fittizio nello store del pacchetto."""
    target = engine_root / "packages" / pkg_id / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


class TestInstallStandaloneFilesV3(unittest.TestCase):
    """Test di _install_standalone_files_v3."""

    def test_empty_standalone_files_returns_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            eng = _make_engine_stub(root)
            mfr = _make_manifest(eng._ctx.github_root)
            result = eng._install_standalone_files_v3(
                package_id="pkg-a",
                pkg_version="1.0.0",
                pkg_manifest={"deployment_modes": {"standalone_files": []}},
                manifest=mfr,
            )
            self.assertTrue(result["success"])
            self.assertEqual(result["files_written"], [])
            self.assertEqual(result["errors"], [])

    def test_absent_deployment_modes_returns_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            eng = _make_engine_stub(root)
            mfr = _make_manifest(eng._ctx.github_root)
            result = eng._install_standalone_files_v3(
                package_id="pkg-b",
                pkg_version="1.0.0",
                pkg_manifest={},
                manifest=mfr,
            )
            self.assertTrue(result["success"])
            self.assertEqual(result["files_written"], [])

    def test_standalone_file_written_to_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            eng = _make_engine_stub(root)
            mfr = _make_manifest(eng._ctx.github_root)
            _seed_store_file(
                eng._ctx.engine_root,
                "pkg-c",
                ".github/instructions/python.instructions.md",
                "# Python instructions",
            )
            pkg_manifest = {
                "deployment_modes": {
                    "standalone_files": [".github/instructions/python.instructions.md"],
                }
            }
            result = eng._install_standalone_files_v3(
                package_id="pkg-c",
                pkg_version="1.0.0",
                pkg_manifest=pkg_manifest,
                manifest=mfr,
            )
            self.assertTrue(result["success"])
            self.assertIn(".github/instructions/python.instructions.md", result["files_written"])
            dest = eng._ctx.github_root / "instructions" / "python.instructions.md"
            self.assertTrue(dest.is_file())
            self.assertEqual(dest.read_text(encoding="utf-8"), "# Python instructions")

    def test_missing_source_in_store_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            eng = _make_engine_stub(root)
            mfr = _make_manifest(eng._ctx.github_root)
            pkg_manifest = {
                "deployment_modes": {
                    "standalone_files": [".github/instructions/missing.instructions.md"],
                }
            }
            result = eng._install_standalone_files_v3(
                package_id="pkg-d",
                pkg_version="1.0.0",
                pkg_manifest=pkg_manifest,
                manifest=mfr,
            )
            self.assertFalse(result["success"])
            self.assertTrue(any("missing" in e for e in result["errors"]))

    def test_idempotent_on_repeated_install(self) -> None:
        """Seconda chiamata con contenuto identico non riscrive il file."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            eng = _make_engine_stub(root)
            mfr = _make_manifest(eng._ctx.github_root)
            content = "idempotent content"
            _seed_store_file(
                eng._ctx.engine_root,
                "pkg-e",
                ".github/copilot-instructions.md",
                content,
            )
            pkg_manifest = {
                "deployment_modes": {
                    "standalone_files": [".github/copilot-instructions.md"],
                }
            }
            result1 = eng._install_standalone_files_v3(
                package_id="pkg-e",
                pkg_version="1.0.0",
                pkg_manifest=pkg_manifest,
                manifest=mfr,
            )
            self.assertTrue(result1["success"])
            self.assertEqual(len(result1["files_written"]), 1)

            # Seconda installazione: stesso contenuto → preserved (sha match).
            result2 = eng._install_standalone_files_v3(
                package_id="pkg-e",
                pkg_version="1.0.0",
                pkg_manifest=pkg_manifest,
                manifest=mfr,
            )
            self.assertTrue(result2["success"])
            self.assertIn(".github/copilot-instructions.md", result2["preserved"])


if __name__ == "__main__":
    unittest.main()
