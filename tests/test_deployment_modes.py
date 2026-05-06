"""Unit tests for _get_deployment_modes helper in spark.packages.lifecycle."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from typing import Any

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

_get_deployment_modes: Any = _module._get_deployment_modes


class TestGetDeploymentModes(unittest.TestCase):
    """Casi unitari per _get_deployment_modes."""

    def test_fallback_when_key_missing(self) -> None:
        """Manifest senza chiave deployment_modes → fallback completo."""
        result = _get_deployment_modes({})
        self.assertEqual(result["mcp_store"], True)
        self.assertEqual(result["standalone_copy"], False)
        self.assertEqual(result["standalone_files"], [])

    def test_fallback_when_value_is_not_dict(self) -> None:
        """deployment_modes = stringa (malformato) → fallback completo."""
        result = _get_deployment_modes({"deployment_modes": "copy"})
        self.assertEqual(result["mcp_store"], True)
        self.assertEqual(result["standalone_copy"], False)
        self.assertEqual(result["standalone_files"], [])

    def test_fallback_when_value_is_none(self) -> None:
        """deployment_modes = None → fallback completo."""
        result = _get_deployment_modes({"deployment_modes": None})
        self.assertEqual(result["mcp_store"], True)
        self.assertEqual(result["standalone_copy"], False)
        self.assertEqual(result["standalone_files"], [])

    def test_partial_manifest_uses_fallback_for_missing_keys(self) -> None:
        """deployment_modes con solo mcp_store → merge con fallback per gli altri."""
        result = _get_deployment_modes({"deployment_modes": {"mcp_store": False}})
        self.assertEqual(result["mcp_store"], False)
        self.assertEqual(result["standalone_copy"], False)
        self.assertEqual(result["standalone_files"], [])

    def test_all_fields_correct(self) -> None:
        """Manifest con tutti i campi → valori letti senza alterazioni."""
        manifest = {
            "deployment_modes": {
                "mcp_store": True,
                "standalone_copy": True,
                "standalone_files": [".github/agents/Agent-Foo.agent.md"],
            }
        }
        result = _get_deployment_modes(manifest)
        self.assertEqual(result["mcp_store"], True)
        self.assertEqual(result["standalone_copy"], True)
        self.assertEqual(result["standalone_files"], [".github/agents/Agent-Foo.agent.md"])

    def test_standalone_files_none_becomes_empty_list(self) -> None:
        """standalone_files = None → lista vuota."""
        result = _get_deployment_modes(
            {"deployment_modes": {"standalone_copy": True, "standalone_files": None}}
        )
        self.assertEqual(result["standalone_files"], [])

    def test_standalone_files_multiple_entries(self) -> None:
        """standalone_files con più voci → lista preservata."""
        files = [
            ".github/agents/A.agent.md",
            ".github/instructions/x.instructions.md",
        ]
        result = _get_deployment_modes(
            {"deployment_modes": {"standalone_copy": True, "standalone_files": files}}
        )
        self.assertEqual(result["standalone_files"], files)

    def test_does_not_mutate_fallback_across_calls(self) -> None:
        """Chiamate successive con manifest vuoto non condividono la stessa lista."""
        r1 = _get_deployment_modes({})
        r2 = _get_deployment_modes({})
        r1["standalone_files"].append("x")
        self.assertEqual(r2["standalone_files"], [])


if __name__ == "__main__":
    unittest.main()
