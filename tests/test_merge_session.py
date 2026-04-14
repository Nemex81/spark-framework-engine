"""Tests for Phase 3 manual merge sessions and finalize flow."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Coroutine, cast
from unittest.mock import MagicMock

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

FrameworkInventory = _module.FrameworkInventory
ManifestManager = _module.ManifestManager
MergeSessionManager = _module.MergeSessionManager
SnapshotManager = _module.SnapshotManager
SparkFrameworkEngine = _module.SparkFrameworkEngine
WorkspaceContext = _module.WorkspaceContext


class FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Coroutine[Any, Any, dict[str, Any]]]] = {}

    def tool(
        self,
    ) -> Callable[
        [Callable[..., Coroutine[Any, Any, dict[str, Any]]]],
        Callable[..., Coroutine[Any, Any, dict[str, Any]]],
    ]:
        def decorator(
            func: Callable[..., Coroutine[Any, Any, dict[str, Any]]],
        ) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
            self.tools[func.__name__] = func
            return func

        return decorator


class TestMergeSession(unittest.TestCase):
    def _sha256(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _make_context(self, workspace_root: Path) -> object:
        return WorkspaceContext(
            workspace_root=workspace_root,
            github_root=workspace_root / ".github",
            engine_root=workspace_root / "spark-framework-engine",
        )

    def _build_engine(self, workspace_root: Path) -> FakeMCP:
        context = self._make_context(workspace_root)
        inventory = FrameworkInventory(context)
        fake_mcp = FakeMCP()
        engine = SparkFrameworkEngine(fake_mcp, context, inventory)
        engine.register_tools()
        return fake_mcp

    def _session_file_entry(
        self,
        file_path: str,
        base_text: str,
        ours_text: str,
        theirs_text: str,
        marker_text: str,
    ) -> dict[str, Any]:
        rel = file_path.removeprefix(".github/")
        return {
            "file": file_path,
            "workspace_path": file_path,
            "manifest_rel": rel,
            "conflict_id": rel,
            "base_text": base_text,
            "ours_text": ours_text,
            "theirs_text": theirs_text,
            "proposed_text": None,
            "resolution_status": "pending",
            "validator_results": None,
            "marker_text": marker_text,
            "original_sha_at_session_open": self._sha256(ours_text),
        }

    def test_finalize_update_fails_when_markers_are_still_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "agents" / "shared.md"
            target_file.parent.mkdir(parents=True)
            target_file.write_text(
                "alpha\n<<<<<<< YOURS\nours\n=======\ntheirs\n>>>>>>> OFFICIAL\nomega\n",
                encoding="utf-8",
            )

            sessions = MergeSessionManager(github_root / "runtime" / "merge-sessions")
            session = sessions.create_session(
                "pkg-a",
                "2.0.0",
                [
                    {
                        "file": ".github/agents/shared.md",
                        "workspace_path": ".github/agents/shared.md",
                        "manifest_rel": "agents/shared.md",
                        "original_sha_at_session_open": self._sha256("alpha\nours\nomega\n"),
                    }
                ],
            )

            fake_mcp = self._build_engine(workspace_root)
            finalize_update = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_finalize_update"],
            )

            result = asyncio.run(finalize_update(session["session_id"]))

            self.assertFalse(result["success"])
            self.assertEqual(result["session_id"], session["session_id"])
            self.assertEqual(result["manual_pending"][0]["reason"], "conflict_markers_present")

    def test_finalize_update_updates_manifest_and_snapshot_when_markers_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "agents" / "shared.md"
            target_file.parent.mkdir(parents=True)
            resolved_text = "alpha\nresolved\nomega\n"
            target_file.write_text(resolved_text, encoding="utf-8")

            sessions = MergeSessionManager(github_root / "runtime" / "merge-sessions")
            session = sessions.create_session(
                "pkg-a",
                "2.0.0",
                [
                    {
                        "file": ".github/agents/shared.md",
                        "workspace_path": ".github/agents/shared.md",
                        "manifest_rel": "agents/shared.md",
                        "original_sha_at_session_open": self._sha256("alpha\nours\nomega\n"),
                    }
                ],
            )

            fake_mcp = self._build_engine(workspace_root)
            finalize_update = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_finalize_update"],
            )

            result = asyncio.run(finalize_update(session["session_id"]))

            self.assertTrue(result["success"])
            self.assertEqual(result["session_status"], "finalized")
            self.assertEqual(result["written_files"], [".github/agents/shared.md"])
            self.assertEqual(result["manifest_updated"], ["agents/shared.md"])
            self.assertEqual(result["snapshot_updated"], [".github/agents/shared.md"])

            manifest = ManifestManager(github_root)
            self.assertEqual(manifest.get_installed_versions(), {"pkg-a": "2.0.0"})
            snapshots = SnapshotManager(github_root / "runtime" / "snapshots")
            self.assertEqual(
                snapshots.load_snapshot("pkg-a", "agents/shared.md"),
                resolved_text,
            )
            finalized_session = sessions.load_session(session["session_id"])
            self.assertEqual(finalized_session["status"], "finalized")

    def test_resolve_conflict_ai_when_safe_case_returns_proposed_text_and_validator_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "agents" / "shared.md"
            target_file.parent.mkdir(parents=True)
            marker_text = (
                "<<<<<<< YOURS\n## Local\n# Agent\nBody\n=======\n# Agent\nBody\n## Remote\n>>>>>>> OFFICIAL\n"
            )
            target_file.write_text(marker_text, encoding="utf-8")

            base_text = "# Agent\nBody\n"
            ours_text = "## Local\n# Agent\nBody\n"
            theirs_text = "# Agent\nBody\n## Remote\n"
            sessions = MergeSessionManager(github_root / "runtime" / "merge-sessions")
            session = sessions.create_session(
                "pkg-a",
                "2.0.0",
                [
                    self._session_file_entry(
                        ".github/agents/shared.md",
                        base_text,
                        ours_text,
                        theirs_text,
                        marker_text,
                    )
                ],
                conflict_mode="assisted",
            )

            fake_mcp = self._build_engine(workspace_root)
            resolve_conflict = cast(
                Callable[[str, str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_resolve_conflict_ai"],
            )

            result = asyncio.run(resolve_conflict(session["session_id"], "agents/shared.md"))

            self.assertTrue(result["success"])
            self.assertEqual(result["resolution_status"], "auto_resolved")
            self.assertIn("## Local", result["proposed_text"])
            self.assertIn("## Remote", result["proposed_text"])
            self.assertTrue(result["validator_results"]["passed"])

    def test_approve_conflict_writes_proposed_text_and_decrements_remaining_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "agents" / "shared.md"
            target_file.parent.mkdir(parents=True)
            marker_text = (
                "<<<<<<< YOURS\n## Local\n# Agent\nBody\n=======\n# Agent\nBody\n## Remote\n>>>>>>> OFFICIAL\n"
            )
            target_file.write_text(marker_text, encoding="utf-8")

            base_text = "# Agent\nBody\n"
            ours_text = "## Local\n# Agent\nBody\n"
            theirs_text = "# Agent\nBody\n## Remote\n"
            sessions = MergeSessionManager(github_root / "runtime" / "merge-sessions")
            session = sessions.create_session(
                "pkg-a",
                "2.0.0",
                [
                    self._session_file_entry(
                        ".github/agents/shared.md",
                        base_text,
                        ours_text,
                        theirs_text,
                        marker_text,
                    )
                ],
                conflict_mode="assisted",
            )

            fake_mcp = self._build_engine(workspace_root)
            resolve_conflict = cast(
                Callable[[str, str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_resolve_conflict_ai"],
            )
            approve_conflict = cast(
                Callable[[str, str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_approve_conflict"],
            )

            asyncio.run(resolve_conflict(session["session_id"], "agents/shared.md"))
            result = asyncio.run(approve_conflict(session["session_id"], "agents/shared.md"))

            self.assertTrue(result["success"])
            self.assertEqual(result["remaining_conflicts"], 0)
            written_text = target_file.read_text(encoding="utf-8")
            self.assertIn("## Local", written_text)
            self.assertIn("## Remote", written_text)
            self.assertNotIn("<<<<<<< YOURS", written_text)

    def test_reject_conflict_keeps_markers_and_finalize_remains_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            github_root = workspace_root / ".github"
            target_file = github_root / "agents" / "shared.md"
            target_file.parent.mkdir(parents=True)
            marker_text = (
                "alpha\n<<<<<<< YOURS\nours\n=======\ntheirs\n>>>>>>> OFFICIAL\nomega\n"
            )
            target_file.write_text(marker_text, encoding="utf-8")

            sessions = MergeSessionManager(github_root / "runtime" / "merge-sessions")
            session = sessions.create_session(
                "pkg-a",
                "2.0.0",
                [
                    self._session_file_entry(
                        ".github/agents/shared.md",
                        "alpha\nbase\nomega\n",
                        "alpha\nours\nomega\n",
                        "alpha\ntheirs\nomega\n",
                        marker_text,
                    )
                ],
                conflict_mode="assisted",
            )

            fake_mcp = self._build_engine(workspace_root)
            reject_conflict = cast(
                Callable[[str, str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_reject_conflict"],
            )
            finalize_update = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_finalize_update"],
            )

            reject_result = asyncio.run(reject_conflict(session["session_id"], "agents/shared.md"))
            finalize_result = asyncio.run(finalize_update(session["session_id"]))

            self.assertTrue(reject_result["success"])
            self.assertGreaterEqual(reject_result["remaining_conflicts"], 1)
            self.assertIn("<<<<<<< YOURS", target_file.read_text(encoding="utf-8"))
            self.assertFalse(finalize_result["success"])
            self.assertEqual(finalize_result["manual_pending"][0]["reason"], "conflict_markers_present")

    def test_atomic_write_json_creates_readable_final_file_without_tmp_leftovers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            session_file = workspace_root / ".github" / "runtime" / "merge-sessions" / "session-a.json"
            payload = {
                "session_id": "session-a",
                "status": "active",
                "files": [],
            }

            MergeSessionManager._atomic_write_json(session_file, payload)

            self.assertTrue(session_file.is_file())
            self.assertEqual(json.loads(session_file.read_text(encoding="utf-8")), payload)
            self.assertEqual(list(session_file.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()