"""Unit tests for SnapshotManager CRUD, UTF-8 handling and path validation."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

SnapshotManager = _module.SnapshotManager


class TestSnapshotManager(unittest.TestCase):
    def test_snapshot_crud_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            snapshots_root = workspace_root / ".github" / "runtime" / "snapshots"
            manager = SnapshotManager(snapshots_root)
            source_file = workspace_root / "agents" / "example.md"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("snapshot content", encoding="utf-8")

            saved = manager.save_snapshot("pkg-a", "agents/example.md", source_file)

            self.assertTrue(saved)
            self.assertTrue(manager.snapshot_exists("pkg-a", "agents/example.md"))
            self.assertEqual(
                manager.load_snapshot("pkg-a", "agents/example.md"),
                "snapshot content",
            )
            self.assertEqual(
                manager.list_package_snapshots("pkg-a"),
                ["agents/example.md"],
            )

            deleted = manager.delete_package_snapshots("pkg-a")

            self.assertEqual(deleted, ["agents/example.md"])
            self.assertFalse(manager.snapshot_exists("pkg-a", "agents/example.md"))
            self.assertIsNone(manager.load_snapshot("pkg-a", "agents/example.md"))
            self.assertEqual(manager.list_package_snapshots("pkg-a"), [])

    def test_save_snapshot_returns_false_for_missing_or_non_utf8_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            manager = SnapshotManager(workspace_root / ".github" / "runtime" / "snapshots")
            missing_file = workspace_root / "missing.md"
            binary_file = workspace_root / "binary.bin"
            binary_file.write_bytes(b"\xff\xfe\x00\x01")

            self.assertFalse(manager.save_snapshot("pkg-a", "agents/missing.md", missing_file))
            self.assertFalse(manager.save_snapshot("pkg-a", "agents/binary.bin", binary_file))
            self.assertEqual(manager.list_package_snapshots("pkg-a"), [])

    def test_invalid_relative_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            manager = SnapshotManager(workspace_root / ".github" / "runtime" / "snapshots")
            source_file = workspace_root / "valid.md"
            source_file.write_text("ok", encoding="utf-8")

            self.assertFalse(manager.save_snapshot("pkg-a", "../agents/example.md", source_file))
            self.assertFalse(manager.save_snapshot("../pkg-a", "agents/example.md", source_file))
            self.assertIsNone(manager.load_snapshot("pkg-a", "../agents/example.md"))
            self.assertFalse(manager.snapshot_exists("pkg-a", "../agents/example.md"))
            self.assertEqual(manager.list_package_snapshots("../pkg-a"), [])
            self.assertEqual(manager.delete_package_snapshots("../pkg-a"), [])


    def test_delete_package_snapshots_partial_failure_returns_already_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            snapshots_root = workspace_root / ".github" / "runtime" / "snapshots"
            manager = SnapshotManager(snapshots_root)

            source_a = workspace_root / "a.md"
            source_b = workspace_root / "b.md"
            source_a.write_text("content a", encoding="utf-8")
            source_b.write_text("content b", encoding="utf-8")
            manager.save_snapshot("pkg-x", "a.md", source_a)
            manager.save_snapshot("pkg-x", "b.md", source_b)

            self.assertEqual(sorted(manager.list_package_snapshots("pkg-x")), ["a.md", "b.md"])

            call_count = 0
            original_unlink = Path.unlink

            def failing_unlink(self: Path, missing_ok: bool = False) -> None:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise OSError("simulated failure")
                original_unlink(self, missing_ok=missing_ok)

            with MagicMock() as _:
                import unittest.mock as _mock
                with _mock.patch.object(Path, "unlink", failing_unlink):
                    result = manager.delete_package_snapshots("pkg-x")

            self.assertEqual(len(result), 1)
            self.assertIsInstance(result, list)

    def test_delete_package_snapshots_empty_package_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            manager = SnapshotManager(workspace_root / ".github" / "runtime" / "snapshots")

            result = manager.delete_package_snapshots("pkg-nonexistent")

            self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()