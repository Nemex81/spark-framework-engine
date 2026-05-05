"""Unit tests for PackageResourceStore (Phase 2)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

PackageResourceStore = _module.PackageResourceStore


def _seed_pkg(engine_dir: Path, pkg_id: str) -> Path:
    pkg_root = engine_dir / "packages" / pkg_id / ".github"
    (pkg_root / "agents").mkdir(parents=True)
    (pkg_root / "prompts").mkdir(parents=True)
    (pkg_root / "skills").mkdir(parents=True)
    (pkg_root / "instructions").mkdir(parents=True)
    (pkg_root / "agents" / "Agent-Foo.agent.md").write_text("foo", encoding="utf-8")
    (pkg_root / "agents" / "Agent-Bar.md").write_text("bar", encoding="utf-8")
    (pkg_root / "prompts" / "do-thing.prompt.md").write_text("p", encoding="utf-8")
    (pkg_root / "skills" / "flat-skill.skill.md").write_text("s", encoding="utf-8")
    (pkg_root / "skills" / "nested").mkdir()
    (pkg_root / "skills" / "nested" / "SKILL.md").write_text("ns", encoding="utf-8")
    (pkg_root / "instructions" / "rule.instructions.md").write_text(
        "r", encoding="utf-8"
    )
    return pkg_root


class TestPackageResourceStore(unittest.TestCase):
    def test_resolve_agents_both_naming(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = Path(tmp)
            _seed_pkg(engine, "pkg-x")
            store = PackageResourceStore(engine)
            p1 = store.resolve("pkg-x", "agents", "Agent-Foo")
            p2 = store.resolve("pkg-x", "agents", "Agent-Bar")
            self.assertIsNotNone(p1)
            self.assertIsNotNone(p2)
            self.assertTrue(p1.name.endswith(".agent.md"))
            self.assertTrue(p2.name.endswith("Agent-Bar.md"))

    def test_resolve_returns_none_for_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = Path(tmp)
            store = PackageResourceStore(engine)
            self.assertIsNone(store.resolve("none", "agents", "X"))

    def test_resolve_invalid_type(self) -> None:
        with TemporaryDirectory() as tmp:
            store = PackageResourceStore(Path(tmp))
            self.assertIsNone(store.resolve("p", "bogus", "x"))

    def test_list_resources_all_types(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = Path(tmp)
            _seed_pkg(engine, "pkg-x")
            store = PackageResourceStore(engine)
            self.assertEqual(
                store.list_resources("pkg-x", "agents"),
                ["Agent-Bar", "Agent-Foo"],
            )
            self.assertEqual(
                store.list_resources("pkg-x", "prompts"), ["do-thing"]
            )
            self.assertEqual(
                store.list_resources("pkg-x", "skills"),
                ["flat-skill", "nested"],
            )
            self.assertEqual(
                store.list_resources("pkg-x", "instructions"), ["rule"]
            )

    def test_list_resources_invalid_type(self) -> None:
        with TemporaryDirectory() as tmp:
            store = PackageResourceStore(Path(tmp))
            self.assertEqual(store.list_resources("p", "bogus"), [])

    def test_list_resources_empty_when_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            store = PackageResourceStore(Path(tmp))
            self.assertEqual(store.list_resources("nope", "agents"), [])

    def test_verify_integrity_no_manifest(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = Path(tmp)
            _seed_pkg(engine, "pkg-x")
            store = PackageResourceStore(engine)
            result = store.verify_integrity("pkg-x")
            self.assertFalse(result["ok"])
            self.assertIn("error", result)

    def test_verify_integrity_ok(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = Path(tmp)
            pkg_root = _seed_pkg(engine, "pkg-x")
            target = pkg_root / "agents" / "Agent-Foo.agent.md"
            sha = hashlib.sha256(target.read_bytes()).hexdigest()
            manifest = {
                "files_metadata": [
                    {"path": ".github/agents/Agent-Foo.agent.md", "sha256": sha}
                ]
            }
            (pkg_root.parent / "package-manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            store = PackageResourceStore(engine)
            result = store.verify_integrity("pkg-x")
            self.assertTrue(result["ok"])
            self.assertEqual(result["mismatches"], [])

    def test_verify_integrity_detects_mismatch(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = Path(tmp)
            pkg_root = _seed_pkg(engine, "pkg-x")
            target = pkg_root / "agents" / "Agent-Foo.agent.md"
            manifest = {
                "files_metadata": [
                    {
                        "path": ".github/agents/Agent-Foo.agent.md",
                        "sha256": "deadbeef" * 8,
                    },
                    {
                        "path": ".github/agents/Missing.agent.md",
                        "sha256": "x" * 64,
                    },
                ]
            }
            (pkg_root.parent / "package-manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            store = PackageResourceStore(engine)
            result = store.verify_integrity("pkg-x")
            self.assertFalse(result["ok"])
            paths = {m["path"] for m in result["mismatches"]}
            self.assertIn(".github/agents/Agent-Foo.agent.md", paths)
            self.assertIn(".github/agents/Missing.agent.md", paths)

    def test_has_workspace_override_true(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = Path(tmp) / "engine"
            engine.mkdir()
            workspace_gh = Path(tmp) / "ws" / ".github"
            (workspace_gh / "overrides" / "agents").mkdir(parents=True)
            (workspace_gh / "overrides" / "agents" / "Agent-Foo.agent.md").write_text(
                "ov", encoding="utf-8"
            )
            store = PackageResourceStore(engine)
            self.assertTrue(
                store.has_workspace_override(workspace_gh, "agents", "Agent-Foo")
            )

    def test_has_workspace_override_false(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = Path(tmp) / "engine"
            engine.mkdir()
            workspace_gh = Path(tmp) / "ws" / ".github"
            workspace_gh.mkdir(parents=True)
            store = PackageResourceStore(engine)
            self.assertFalse(
                store.has_workspace_override(workspace_gh, "agents", "Agent-Foo")
            )


if __name__ == "__main__":
    unittest.main()
