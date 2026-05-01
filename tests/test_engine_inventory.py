"""Unit tests for EngineInventory engine-manifest.json loader (Phase 1)."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

EngineInventory = _module.EngineInventory


class TestEngineInventoryManifest(unittest.TestCase):
    """Verify EngineInventory loads engine-manifest.json correctly."""

    def test_loads_real_engine_manifest(self) -> None:
        """The repository ships engine-manifest.json; loader must populate it."""
        inv = EngineInventory(engine_root=_ENGINE_PATH.parent)
        self.assertIsInstance(inv.engine_manifest, dict)
        self.assertEqual(inv.engine_manifest.get("schema_version"), "3.0")
        self.assertEqual(inv.engine_manifest.get("package"), "spark-framework-engine")

    def test_workspace_files_helper(self) -> None:
        inv = EngineInventory(engine_root=_ENGINE_PATH.parent)
        ws_files = inv.get_engine_workspace_files()
        self.assertIsInstance(ws_files, list)
        # Almeno le 6 instruction engine dichiarate dal design §3.5
        joined = " ".join(ws_files)
        for expected in (
            "framework-guard",
            "personality",
            "verbosity",
            "workflow-standard",
            "git-policy",
            "model-policy",
        ):
            self.assertIn(expected, joined)

    def test_mcp_resources_helper(self) -> None:
        inv = EngineInventory(engine_root=_ENGINE_PATH.parent)
        resources = inv.get_engine_mcp_resources()
        self.assertEqual(
            set(resources.keys()), {"agents", "instructions", "prompts", "skills"}
        )
        self.assertIn("spark-welcome", resources["agents"])
        self.assertIn("spark-assistant", resources["agents"])
        self.assertIn("project-reset", resources["instructions"])

    def test_missing_manifest_returns_empty(self) -> None:
        """When engine-manifest.json is missing, loader logs warning and returns empty."""
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            inv = EngineInventory(engine_root=_ENGINE_PATH.parent)
            empty = inv._load_engine_manifest(tmp_path)
            self.assertEqual(empty, {})

    def test_invalid_json_returns_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "engine-manifest.json").write_text(
                "not-valid-json", encoding="utf-8"
            )
            inv = EngineInventory(engine_root=_ENGINE_PATH.parent)
            self.assertEqual(inv._load_engine_manifest(tmp_path), {})

    def test_non_object_root_returns_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "engine-manifest.json").write_text(
                "[1, 2, 3]", encoding="utf-8"
            )
            inv = EngineInventory(engine_root=_ENGINE_PATH.parent)
            self.assertEqual(inv._load_engine_manifest(tmp_path), {})

    def test_helpers_robust_to_malformed_manifest(self) -> None:
        """Helpers must not crash on partially malformed manifest."""
        inv = EngineInventory(engine_root=_ENGINE_PATH.parent)
        inv.engine_manifest = {"workspace_files": "not-a-list"}
        self.assertEqual(inv.get_engine_workspace_files(), [])

        inv.engine_manifest = {"mcp_resources": "not-a-dict"}
        out = inv.get_engine_mcp_resources()
        self.assertEqual(
            out, {"agents": [], "instructions": [], "prompts": [], "skills": []}
        )


class TestManifestSchemaCompatibility(unittest.TestCase):
    """Verify package manifest v3.0 schema is parsed without crash."""

    def _make_v3_manifest(self, tmp_path: Path) -> Path:
        manifest = {
            "schema_version": "3.0",
            "package": "test-pkg",
            "version": "1.0.0",
            "min_engine_version": "2.4.0",
            "workspace_files": [
                ".github/copilot-instructions.md",
                ".github/instructions/example.instructions.md",
            ],
            "mcp_resources": {
                "agents": ["agent-foo"],
                "prompts": ["prompt-bar"],
                "skills": ["skill-baz"],
                "instructions": ["example"],
            },
            "files": [
                ".github/copilot-instructions.md",
                ".github/instructions/example.instructions.md",
                ".github/agents/agent-foo.agent.md",
            ],
            "files_metadata": [],
        }
        path = tmp_path / "package-manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def test_v3_manifest_loads_as_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            path = self._make_v3_manifest(tmp_path)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["schema_version"], "3.0")
            self.assertIn("workspace_files", data)
            self.assertIn("mcp_resources", data)
            # Fallback v2.x: 'files' deve restare presente
            self.assertIn("files", data)

    def test_v3_real_manifests_have_required_fields(self) -> None:
        """The 3 real package manifests in the workspace must satisfy v3.0 schema."""
        roots = [
            _ENGINE_PATH.parent.parent / "spark-base" / "package-manifest.json",
            _ENGINE_PATH.parent.parent / "scf-master-codecrafter" / "package-manifest.json",
            _ENGINE_PATH.parent.parent / "scf-pycode-crafter" / "package-manifest.json",
        ]
        for path in roots:
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                data["schema_version"], "3.0", f"{path}: schema_version != 3.0"
            )
            self.assertIn("workspace_files", data, f"{path}: workspace_files missing")
            self.assertIn("mcp_resources", data, f"{path}: mcp_resources missing")
            self.assertIn("files", data, f"{path}: files (v2.x fallback) missing")
            for key in ("agents", "prompts", "skills", "instructions"):
                self.assertIn(
                    key,
                    data["mcp_resources"],
                    f"{path}: mcp_resources.{key} missing",
                )


if __name__ == "__main__":
    unittest.main()
