"""Unit tests for _get_deployment_modes helper in spark.packages.lifecycle."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Coroutine, cast
from unittest.mock import patch

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

_get_deployment_modes: Any = _module._get_deployment_modes
FrameworkInventory = _module.FrameworkInventory
ManifestManager = _module.ManifestManager
RegistryClient = _module.RegistryClient
SparkFrameworkEngine = _module.SparkFrameworkEngine
WorkspaceContext = _module.WorkspaceContext


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


# ---------------------------------------------------------------------------
# Helpers per i test di integrazione scf_install_package + deployment_notice
# ---------------------------------------------------------------------------

def _build_engine_dm(workspace_root: Path) -> tuple[Any, Any]:
    context = WorkspaceContext(
        workspace_root=workspace_root,
        github_root=workspace_root / ".github",
        engine_root=workspace_root / "spark-framework-engine",
    )
    inventory = FrameworkInventory(context)

    class FakeMCP:
        def __init__(self) -> None:
            self.tools: dict[str, Any] = {}

        def tool(self) -> Any:  # type: ignore[return]
            def decorator(func: Any) -> Any:
                self.tools[func.__name__] = func
                return func
            return decorator

    fake_mcp = FakeMCP()
    engine = SparkFrameworkEngine(fake_mcp, context, inventory)
    engine.register_tools()
    return fake_mcp, engine


def _authorize_dm(workspace_root: Path) -> None:
    state_path = workspace_root / ".github" / "runtime" / "orchestrator-state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"github_write_authorized": True}, indent=2),
        encoding="utf-8",
    )


def _v3_manifest_no_standalone(package_id: str) -> dict[str, Any]:
    """Manifest v3 senza deployment_modes (no standalone_copy)."""
    return {
        "package": package_id,
        "version": "3.0.0",
        "min_engine_version": "3.0.0",
        "dependencies": [],
        "conflicts": [],
        "file_ownership_policy": "error",
        "files": [f".github/agents/{package_id}.agent.md"],
        "mcp_resources": {"agents": [f"{package_id}"]},
    }


def _v3_manifest_with_standalone(package_id: str) -> dict[str, Any]:
    """Manifest v3 con standalone_copy=True."""
    return {
        "package": package_id,
        "version": "3.0.0",
        "min_engine_version": "3.0.0",
        "dependencies": [],
        "conflicts": [],
        "file_ownership_policy": "error",
        "files": [f".github/agents/{package_id}.agent.md"],
        "mcp_resources": {"agents": [f"{package_id}"]},
        "deployment_modes": {
            "mcp_store": True,
            "standalone_copy": True,
            "standalone_files": [f".github/agents/{package_id}.agent.md"],
        },
    }


def _v3_manifest_with_empty_standalone(package_id: str) -> dict[str, Any]:
    """Manifest v3 con deployment_modes ma standalone_files vuoto."""
    return {
        "package": package_id,
        "version": "3.0.0",
        "min_engine_version": "3.0.0",
        "dependencies": [],
        "conflicts": [],
        "file_ownership_policy": "error",
        "files": [f".github/agents/{package_id}.agent.md"],
        "mcp_resources": {"agents": [f"{package_id}"]},
        "deployment_modes": {
            "mcp_store": True,
            "standalone_copy": True,
            "standalone_files": [],
        },
    }


def _v3_manifest_with_plugin_file(package_id: str) -> dict[str, Any]:
    """Manifest v3.1 con plugin_files e senza standalone_copy."""
    plugin_path = ".github/workflows/notify-engine.yml"
    return {
        "schema_version": "3.1",
        "package": package_id,
        "version": "3.1.0",
        "min_engine_version": "3.0.0",
        "dependencies": [],
        "conflicts": [],
        "file_ownership_policy": "error",
        "files": [f".github/agents/{package_id}.agent.md", plugin_path],
        "mcp_resources": {"agents": [f"{package_id}"]},
        "plugin_files": [plugin_path],
    }


def _registry_pkg_dm(package_id: str) -> dict[str, Any]:
    return {
        "id": package_id,
        "description": f"Package {package_id}",
        "repo_url": f"https://github.com/example/{package_id}",
        "latest_version": "3.0.0",
        "status": "active",
        "min_engine_version": "3.0.0",
    }


class TestDeploymentNotice(unittest.TestCase):
    """Verifica deployment_notice e deployment_summary nel path v3."""

    def test_auto_mode_no_standalone_copy_adds_notice(self) -> None:
        """auto + manifest senza standalone_copy → deployment_notice presente."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _authorize_dm(ws)
            fake_mcp, _engine = _build_engine_dm(ws)
            install = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )
            pkg_id = "pkg-no-standalone"
            with (
                patch.object(
                    RegistryClient, "list_packages",
                    return_value=[_registry_pkg_dm(pkg_id)],
                ),
                patch.object(
                    RegistryClient, "fetch_package_manifest",
                    return_value=_v3_manifest_no_standalone(pkg_id),
                ),
                patch.object(
                    RegistryClient, "fetch_raw_file",
                    return_value="# contenuto",
                ),
            ):
                result = asyncio.run(install(pkg_id))

            self.assertTrue(result.get("success"), msg=result)
            notice = result.get("deployment_notice", "")
            self.assertIn("engine store", notice, msg=notice)
            self.assertIn(".github/", notice, msg=notice)
            summary = result.get("deployment_summary", {})
            self.assertTrue(summary.get("engine_store"))
            self.assertFalse(summary.get("standalone_copy"))

    def test_store_mode_adds_deployment_summary_no_notice(self) -> None:
        """deployment_mode='store' → deployment_summary presente; deployment_notice assente."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _authorize_dm(ws)
            fake_mcp, _engine = _build_engine_dm(ws)
            install = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )
            pkg_id = "pkg-store-only"
            with (
                patch.object(
                    RegistryClient, "list_packages",
                    return_value=[_registry_pkg_dm(pkg_id)],
                ),
                patch.object(
                    RegistryClient, "fetch_package_manifest",
                    return_value=_v3_manifest_no_standalone(pkg_id),
                ),
                patch.object(
                    RegistryClient, "fetch_raw_file",
                    return_value="# contenuto",
                ),
            ):
                result = asyncio.run(install(pkg_id, deployment_mode="store"))

            self.assertTrue(result.get("success"), msg=result)
            self.assertNotIn("deployment_notice", result)
            summary = result.get("deployment_summary", {})
            self.assertTrue(summary.get("engine_store"))
            self.assertFalse(summary.get("standalone_copy"))
            self.assertEqual(summary.get("standalone_files_count"), 0)

    def test_copy_mode_no_notice_summary_standalone_true(self) -> None:
        """deployment_mode='copy' con standalone_copy=True → no notice; summary standalone_copy=True."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _authorize_dm(ws)
            fake_mcp, _engine = _build_engine_dm(ws)
            install = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )
            pkg_id = "pkg-with-standalone"
            with (
                patch.object(
                    RegistryClient, "list_packages",
                    return_value=[_registry_pkg_dm(pkg_id)],
                ),
                patch.object(
                    RegistryClient, "fetch_package_manifest",
                    return_value=_v3_manifest_with_standalone(pkg_id),
                ),
                patch.object(
                    RegistryClient, "fetch_raw_file",
                    return_value="# contenuto agente",
                ),
            ):
                result = asyncio.run(install(pkg_id, deployment_mode="copy"))

            self.assertTrue(result.get("success"), msg=result)
            self.assertNotIn("deployment_notice", result)
            summary = result.get("deployment_summary", {})
            self.assertTrue(summary.get("engine_store"))
            self.assertTrue(summary.get("standalone_copy"))

    def test_auto_mode_installs_plugin_files_without_standalone_notice(self) -> None:
        """plugin_files espliciti vengono installati in auto senza deployment_notice."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _authorize_dm(ws)
            fake_mcp, _engine = _build_engine_dm(ws)
            install = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )
            pkg_id = "pkg-plugin-file"
            with (
                patch.object(
                    RegistryClient, "list_packages",
                    return_value=[_registry_pkg_dm(pkg_id)],
                ),
                patch.object(
                    RegistryClient, "fetch_package_manifest",
                    return_value=_v3_manifest_with_plugin_file(pkg_id),
                ),
                patch.object(
                    RegistryClient, "fetch_raw_file",
                    return_value="name: Notify Engine",
                ),
            ):
                result = asyncio.run(install(pkg_id))

            self.assertTrue(result.get("success"), msg=result)
            self.assertNotIn("deployment_notice", result)
            self.assertEqual(
                result.get("plugin_files_installed"),
                [".github/workflows/notify-engine.yml"],
            )
            self.assertIn(".github/workflows/notify-engine.yml", result.get("installed", []))
            self.assertIn("agents://pkg-plugin-file", result.get("mcp_services_activated", []))
            summary = result.get("deployment_summary", {})
            self.assertEqual(summary.get("plugin_files_count"), 1)
            target = ws / ".github" / "workflows" / "notify-engine.yml"
            self.assertTrue(target.is_file())

    def test_copy_mode_empty_standalone_files_adds_warning(self) -> None:
        """copy + standalone_files=[] → deployment_warning; standalone_copy=False nel summary."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _authorize_dm(ws)
            fake_mcp, _engine = _build_engine_dm(ws)
            install = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )
            pkg_id = "pkg-empty-standalone"
            with (
                patch.object(
                    RegistryClient, "list_packages",
                    return_value=[_registry_pkg_dm(pkg_id)],
                ),
                patch.object(
                    RegistryClient, "fetch_package_manifest",
                    return_value=_v3_manifest_with_empty_standalone(pkg_id),
                ),
                patch.object(
                    RegistryClient, "fetch_raw_file",
                    return_value="# contenuto",
                ),
            ):
                result = asyncio.run(install(pkg_id, deployment_mode="copy"))

            self.assertTrue(result.get("success"), msg=result)
            warning = result.get("deployment_warning", "")
            self.assertIn("standalone_files", warning, msg=warning)
            self.assertIn(".github/", warning, msg=warning)
            self.assertNotIn("deployment_notice", result)
            summary = result.get("deployment_summary", {})
            self.assertTrue(summary.get("engine_store"))
            self.assertFalse(summary.get("standalone_copy"))
            self.assertEqual(summary.get("standalone_files_count"), 0)

    def test_copy_mode_no_deployment_modes_section_adds_warning(self) -> None:
        """copy + manifest senza sezione deployment_modes → deployment_warning."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _authorize_dm(ws)
            fake_mcp, _engine = _build_engine_dm(ws)
            install = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )
            pkg_id = "pkg-no-dm-section"
            with (
                patch.object(
                    RegistryClient, "list_packages",
                    return_value=[_registry_pkg_dm(pkg_id)],
                ),
                patch.object(
                    RegistryClient, "fetch_package_manifest",
                    return_value=_v3_manifest_no_standalone(pkg_id),
                ),
                patch.object(
                    RegistryClient, "fetch_raw_file",
                    return_value="# contenuto",
                ),
            ):
                result = asyncio.run(install(pkg_id, deployment_mode="copy"))

            self.assertTrue(result.get("success"), msg=result)
            self.assertIn("deployment_warning", result)
            summary = result.get("deployment_summary", {})
            self.assertFalse(summary.get("standalone_copy"))

    def test_store_mode_skips_standalone_and_sets_summary(self) -> None:
        """store + manifest con standalone_files → _install_standalone_files_v3 non chiamato."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _authorize_dm(ws)
            fake_mcp, engine = _build_engine_dm(ws)
            install = cast(
                Callable[..., Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )
            pkg_id = "pkg-store-skip-standalone"
            with (
                patch.object(
                    RegistryClient, "list_packages",
                    return_value=[_registry_pkg_dm(pkg_id)],
                ),
                patch.object(
                    RegistryClient, "fetch_package_manifest",
                    return_value=_v3_manifest_with_standalone(pkg_id),
                ),
                patch.object(
                    RegistryClient, "fetch_raw_file",
                    return_value="# contenuto",
                ),
                patch.object(
                    engine, "_install_standalone_files_v3"
                ) as mock_standalone,
            ):
                result = asyncio.run(install(pkg_id, deployment_mode="store"))

            self.assertTrue(result.get("success"), msg=result)
            self.assertNotIn("deployment_notice", result)
            self.assertNotIn("deployment_warning", result)
            summary = result.get("deployment_summary", {})
            self.assertTrue(summary.get("engine_store"))
            self.assertFalse(summary.get("standalone_copy"))
            self.assertEqual(summary.get("standalone_files_count"), 0)
            mock_standalone.assert_not_called()


if __name__ == "__main__":
    unittest.main()
