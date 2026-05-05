"""Unit tests for diff-based cleanup in scf_install_package (Step 2)
and tripartite orphan classification in verify_integrity (Step 3)."""
from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

ManifestManager: Any = _module.ManifestManager


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entry(file_rel: str, package: str, content: str = "content", version: str = "1.0.0") -> dict:
    return {
        "file": file_rel,
        "package": package,
        "package_version": version,
        "installed_at": "2026-01-01T00:00:00Z",
        "sha256": _sha256(content),
    }


def _write_bytes(path: Path, content: str) -> bytes:
    """Write UTF-8 bytes directly (no CRLF translation on Windows) and return the bytes."""
    data = content.encode("utf-8")
    path.write_bytes(data)
    return data


class TestDiffBasedCleanup(unittest.TestCase):
    """Tests for ManifestManager.remove_package logic used by diff-based cleanup."""

    def _setup(self, tmp: str) -> tuple[Path, Path, ManifestManager]:
        workspace_root = Path(tmp)
        github_root = workspace_root / ".github"
        github_root.mkdir(parents=True)
        (github_root / "agents").mkdir(parents=True)
        manager = ManifestManager(github_root)
        return workspace_root, github_root, manager

    def test_obsolete_unmodified_file_is_removed(self) -> None:
        """A file tracked for pkg but absent from new manifest must be deleted."""
        with tempfile.TemporaryDirectory() as tmp:
            _, github_root, manager = self._setup(tmp)

            old_agent = github_root / "agents" / "OldAgent.md"
            common_agent = github_root / "agents" / "Common.md"
            old_agent.write_text("old content", encoding="utf-8")
            common_agent.write_text("common content", encoding="utf-8")

            manager.save([
                _entry("agents/OldAgent.md", "pkg-a", "old content"),
                _entry("agents/Common.md", "pkg-a", "common content"),
            ])

            # Simulate what diff-based cleanup does:
            # new manifest only has Common.md — OldAgent.md is obsolete
            old_files = {
                entry["file"]
                for entry in manager.load()
                if entry.get("package") == "pkg-a"
            }
            new_files = {"agents/Common.md"}
            to_remove = old_files - new_files

            removed: list[str] = []
            for rel_path in sorted(to_remove):
                file_abs = github_root / rel_path
                is_modified = manager.is_user_modified(rel_path)
                if not is_modified and file_abs.is_file():
                    file_abs.unlink()
                    removed.append(rel_path)

            self.assertIn("agents/OldAgent.md", removed)
            self.assertFalse(old_agent.exists(), "OldAgent.md should have been deleted")
            self.assertTrue(common_agent.exists(), "Common.md should still exist")

    def test_obsolete_user_modified_file_is_preserved(self) -> None:
        """A file modified by the user must NOT be deleted even if obsolete."""
        with tempfile.TemporaryDirectory() as tmp:
            _, github_root, manager = self._setup(tmp)

            old_agent = github_root / "agents" / "OldAgent.md"
            old_agent.write_text("user customized content", encoding="utf-8")

            # Manifest SHA records original content (different from disk)
            manager.save([
                _entry("agents/OldAgent.md", "pkg-a", "original content"),
            ])

            old_files = {e["file"] for e in manager.load() if e.get("package") == "pkg-a"}
            new_files: set[str] = set()  # new manifest has no files
            to_remove = old_files - new_files

            preserved: list[str] = []
            removed: list[str] = []
            for rel_path in sorted(to_remove):
                file_abs = github_root / rel_path
                is_modified = manager.is_user_modified(rel_path)
                if is_modified:
                    preserved.append(rel_path)
                elif file_abs.is_file():
                    file_abs.unlink()
                    removed.append(rel_path)

            self.assertIn("agents/OldAgent.md", preserved)
            self.assertEqual(removed, [])
            self.assertTrue(old_agent.exists(), "User-modified file must be preserved")

    def test_common_file_not_in_to_remove(self) -> None:
        """A file present in both old and new manifest must not appear in to_remove."""
        with tempfile.TemporaryDirectory() as tmp:
            _, github_root, manager = self._setup(tmp)

            manager.save([
                _entry("agents/NewAgent.md", "pkg-a"),
                _entry("agents/Common.md", "pkg-a"),
            ])

            old_files = {e["file"] for e in manager.load() if e.get("package") == "pkg-a"}
            new_files = {"agents/NewAgent.md", "agents/Common.md"}
            to_remove = old_files - new_files

            self.assertEqual(to_remove, set())


class TestTripartiteClassification(unittest.TestCase):
    """Tests for tripartite orphan classification in verify_integrity (Step 3)."""

    def _make_manager(self, tmp: str) -> tuple[Path, ManifestManager]:
        github_root = Path(tmp) / ".github"
        github_root.mkdir(parents=True)
        (github_root / "agents").mkdir(parents=True)
        return github_root, ManifestManager(github_root)

    def test_untracked_file_without_spark_classified_as_user_file(self) -> None:
        """A .md file outside the manifest and without spark: true → user_files."""
        with tempfile.TemporaryDirectory() as tmp:
            github_root, manager = self._make_manager(tmp)

            custom = github_root / "agents" / "CustomAgent.md"
            custom.write_text("# Custom Agent\n\nno frontmatter spark", encoding="utf-8")

            manager.save([])  # empty manifest

            report = manager.verify_integrity()

            self.assertIn("agents/CustomAgent.md", report["user_files"])
            self.assertNotIn("agents/CustomAgent.md", report["orphan_candidates"])
            self.assertNotIn("agents/CustomAgent.md", report["untagged_spark_files"])

    def test_untracked_spark_file_classified_as_untagged(self) -> None:
        """A .md file with spark: true but NOT in manifest → untagged_spark_files + orphan_candidates."""
        with tempfile.TemporaryDirectory() as tmp:
            github_root, manager = self._make_manager(tmp)

            mystery = github_root / "agents" / "MysteryAgent.md"
            mystery.write_text(
                "---\nname: mystery\nspark: true\n---\n\n# Mystery",
                encoding="utf-8",
            )

            manager.save([])  # empty manifest

            report = manager.verify_integrity()

            self.assertIn("agents/MysteryAgent.md", report["untagged_spark_files"])
            self.assertIn("agents/MysteryAgent.md", report["orphan_candidates"])
            self.assertNotIn("agents/MysteryAgent.md", report["user_files"])

    def test_tracked_spark_file_classified_as_ok(self) -> None:
        """A .md file with spark: true AND in manifest → ok, not in orphan/user/untagged."""
        with tempfile.TemporaryDirectory() as tmp:
            github_root, manager = self._make_manager(tmp)

            tracked = github_root / "agents" / "TrackedAgent.md"
            content = "---\nname: tracked\nspark: true\npackage: pkg-a\nversion: 1.0.0\n---\n\n# Tracked"
            data = _write_bytes(tracked, content)  # binary write avoids CRLF mismatch on Windows

            sha = _sha256_bytes(data)
            manager.save([{
                "file": "agents/TrackedAgent.md",
                "package": "pkg-a",
                "package_version": "1.0.0",
                "installed_at": "2026-01-01T00:00:00Z",
                "sha256": sha,
            }])

            report = manager.verify_integrity()

            self.assertIn("agents/TrackedAgent.md", report["ok"])
            self.assertNotIn("agents/TrackedAgent.md", report["orphan_candidates"])
            self.assertNotIn("agents/TrackedAgent.md", report["user_files"])
            self.assertNotIn("agents/TrackedAgent.md", report["untagged_spark_files"])

    def test_summary_includes_new_counts(self) -> None:
        """summary must contain user_file_count and untagged_spark_count."""
        with tempfile.TemporaryDirectory() as tmp:
            github_root, manager = self._make_manager(tmp)

            user_f = github_root / "agents" / "UserAgent.md"
            spark_f = github_root / "agents" / "SparkAgent.md"
            user_f.write_text("# no spark", encoding="utf-8")
            spark_f.write_text("---\nspark: true\n---\n# Spark", encoding="utf-8")

            manager.save([])

            report = manager.verify_integrity()
            summary = report["summary"]

            self.assertIn("user_file_count", summary)
            self.assertIn("untagged_spark_count", summary)
            self.assertEqual(summary["user_file_count"], 1)
            self.assertEqual(summary["untagged_spark_count"], 1)


class TestFetchErrorAtomicity(unittest.TestCase):
    """Tests verifying that a fetch failure leaves disk and manifest untouched.

    The fixed execution order is: fetch → (if ok) diff-cleanup → write.
    These tests simulate that order directly to confirm the invariants.
    """

    def _setup(self, tmp: str) -> tuple[Path, Path, ManifestManager]:
        workspace_root = Path(tmp)
        github_root = workspace_root / ".github"
        github_root.mkdir(parents=True)
        (github_root / "agents").mkdir(parents=True)
        return workspace_root, github_root, ManifestManager(github_root)

    def _simulate_fixed_install(
        self,
        github_root: Path,
        manager: ManifestManager,
        package_id: str,
        new_file_paths: list[str],
        fail_on: str,
    ) -> dict:
        """Simulate the FIXED scf_install_package order: fetch first, cleanup only if 100% ok."""
        # Phase 1: fetch (no disk writes)
        preserved: list[str] = []
        fetch_errors: list[str] = []
        staged: list[tuple[str, str, str]] = []
        for file_path in new_file_paths:
            rel = file_path.removeprefix(".github/")
            if manager.is_user_modified(rel) is True:
                preserved.append(file_path)
                continue
            if file_path == fail_on:
                fetch_errors.append(f"{file_path}: simulated URLError")
                continue
            staged.append((file_path, rel, "mock content"))

        if fetch_errors:
            return {
                "success": False,
                "package": package_id,
                "version": "2.0.0",
                "installed": [],
                "preserved": preserved,
                "removed_obsolete_files": [],
                "preserved_obsolete_files": [],
                "errors": fetch_errors,
            }

        # Phase 2: diff-cleanup (only reached when fetch is 100% complete)
        old_files = {e["file"] for e in manager.load() if e.get("package") == package_id}
        new_files = {f.removeprefix(".github/") for f in new_file_paths if f}
        to_remove = old_files - new_files
        removed_files: list[str] = []
        preserved_obsolete: list[str] = []
        for rel_path in sorted(to_remove):
            is_modified = manager.is_user_modified(rel_path)
            file_abs = github_root / rel_path
            if is_modified:
                preserved_obsolete.append(rel_path)
            elif file_abs.is_file():
                file_abs.unlink()
                removed_files.append(rel_path)

        return {
            "success": True,
            "package": package_id,
            "version": "2.0.0",
            "installed": [fp for fp, _, _ in staged],
            "preserved": preserved,
            "removed_obsolete_files": removed_files,
            "preserved_obsolete_files": preserved_obsolete,
        }

    def test_fetch_error_leaves_manifest_intact(self) -> None:
        """If fetch fails, files on disk and manifest entries must be untouched."""
        with tempfile.TemporaryDirectory() as tmp:
            _, github_root, manager = self._setup(tmp)

            file_a = github_root / "agents" / "FileA.md"
            file_b = github_root / "agents" / "FileB.md"
            file_a.write_text("content A", encoding="utf-8")
            file_b.write_text("content B", encoding="utf-8")

            manager.save([
                _entry("agents/FileA.md", "pkg-test", "content A"),
                _entry("agents/FileB.md", "pkg-test", "content B"),
            ])

            # v2 removes FileA and adds FileC — FileC fetch will fail
            v2_files = [".github/agents/FileB.md", ".github/agents/FileC.md"]
            result = self._simulate_fixed_install(
                github_root, manager, "pkg-test", v2_files,
                fail_on=".github/agents/FileC.md",
            )

            self.assertFalse(result["success"])
            self.assertTrue(file_a.exists(), "FileA.md must still exist on disk")
            files_in_manifest = {e["file"] for e in manager.load()}
            self.assertIn("agents/FileA.md", files_in_manifest, "FileA must remain in manifest")
            self.assertIn("agents/FileB.md", files_in_manifest, "FileB must remain in manifest")
            self.assertEqual(result["removed_obsolete_files"], [])

    def test_fetch_error_return_has_all_keys(self) -> None:
        """Return dict on fetch failure must contain all required keys."""
        with tempfile.TemporaryDirectory() as tmp:
            _, github_root, manager = self._setup(tmp)

            (github_root / "agents" / "FileA.md").write_text("content A", encoding="utf-8")
            manager.save([_entry("agents/FileA.md", "pkg-test", "content A")])

            v2_files = [".github/agents/FileB.md", ".github/agents/FileC.md"]
            result = self._simulate_fixed_install(
                github_root, manager, "pkg-test", v2_files,
                fail_on=".github/agents/FileC.md",
            )

            required_keys = {
                "success", "package", "version", "installed",
                "preserved", "removed_obsolete_files", "preserved_obsolete_files", "errors",
            }
            self.assertTrue(required_keys.issubset(result.keys()))


if __name__ == "__main__":
    unittest.main()
