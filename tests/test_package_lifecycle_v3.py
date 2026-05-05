"""Unit tests for v3-aware package lifecycle (install/update/remove).

These tests exercise the v3 store-based flow that activates when a package
declares ``min_engine_version >= 3.0.0`` in its package-manifest.json.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Coroutine, cast
from unittest.mock import MagicMock, patch

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

FrameworkInventory = _module.FrameworkInventory
ManifestManager = _module.ManifestManager
RegistryClient = _module.RegistryClient
SparkFrameworkEngine = _module.SparkFrameworkEngine
WorkspaceContext = _module.WorkspaceContext
PackageResourceStore = _module.PackageResourceStore


class FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Coroutine[Any, Any, dict[str, Any]]]] = {}

    def tool(self):  # type: ignore[no-untyped-def]
        def decorator(func):  # type: ignore[no-untyped-def]
            self.tools[func.__name__] = func
            return func
        return decorator


def _build_engine(workspace_root: Path) -> tuple[FakeMCP, SparkFrameworkEngine]:
    context = WorkspaceContext(
        workspace_root=workspace_root,
        github_root=workspace_root / ".github",
        engine_root=workspace_root / "spark-framework-engine",
    )
    inventory = FrameworkInventory(context)
    fake_mcp = FakeMCP()
    engine = SparkFrameworkEngine(fake_mcp, context, inventory)
    engine.register_tools()
    return fake_mcp, engine


def _authorize(workspace_root: Path) -> None:
    state_path = workspace_root / ".github" / "runtime" / "orchestrator-state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"github_write_authorized": True}, indent=2),
        encoding="utf-8",
    )


def _v3_pkg_manifest(
    package_id: str,
    version: str = "3.1.0",
    files: list[str] | None = None,
    mcp_resources: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    return {
        "package": package_id,
        "version": version,
        "min_engine_version": "3.0.0",
        "dependencies": [],
        "conflicts": [],
        "file_ownership_policy": "error",
        "files": files
        or [
            f".github/agents/{package_id}-agent.md",
            f".github/skills/{package_id}-skill.skill.md",
        ],
        "mcp_resources": mcp_resources
        or {
            "agents": [f"{package_id}-agent"],
            "skills": [f"{package_id}-skill"],
        },
    }


def _registry_pkg(package_id: str, version: str = "3.1.0") -> dict[str, Any]:
    return {
        "id": package_id,
        "description": f"Package {package_id}",
        "repo_url": f"https://github.com/example/{package_id}",
        "latest_version": version,
        "status": "active",
        "min_engine_version": "3.0.0",
    }


class TestV3PackageLifecycle(unittest.TestCase):
    """End-to-end behaviour of v3 install/update/remove."""

    def test_install_v3_writes_to_engine_store_not_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _authorize(ws)
            fake_mcp, _engine = _build_engine(ws)
            install = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )
            with (
                patch.object(RegistryClient, "list_packages", return_value=[_registry_pkg("pkg-v3")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value=_v3_pkg_manifest("pkg-v3"),
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="# v3 file content"),
            ):
                result = asyncio.run(install("pkg-v3"))

            self.assertTrue(result.get("success"), msg=result)
            self.assertEqual(result.get("installation_mode"), "v3_store")
            # Lo store engine deve contenere i file.
            store_root = ws / "spark-framework-engine" / "packages" / "pkg-v3"
            self.assertTrue((store_root / ".github" / "agents" / "pkg-v3-agent.md").is_file())
            self.assertTrue((store_root / ".github" / "skills" / "pkg-v3-skill.skill.md").is_file())
            self.assertTrue((store_root / "package-manifest.json").is_file())
            # Workspace .github NON deve contenere i file di pacchetto.
            self.assertFalse((ws / ".github" / "agents" / "pkg-v3-agent.md").exists())
            self.assertFalse((ws / ".github" / "skills" / "pkg-v3-skill.skill.md").exists())

    def test_install_v3_idempotent_on_same_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _authorize(ws)
            fake_mcp, _engine = _build_engine(ws)
            install = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )
            with (
                patch.object(RegistryClient, "list_packages", return_value=[_registry_pkg("pkg-v3")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value=_v3_pkg_manifest("pkg-v3"),
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="content"),
            ):
                first = asyncio.run(install("pkg-v3"))
                second = asyncio.run(install("pkg-v3"))

            self.assertTrue(first.get("success"))
            self.assertTrue(second.get("success"))
            self.assertTrue(second.get("idempotent"))

    def test_install_v3_writes_sentinel_manifest_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _authorize(ws)
            fake_mcp, _engine = _build_engine(ws)
            install = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )
            with (
                patch.object(RegistryClient, "list_packages", return_value=[_registry_pkg("pkg-v3")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value=_v3_pkg_manifest("pkg-v3"),
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="content"),
            ):
                asyncio.run(install("pkg-v3"))

            manifest = ManifestManager(ws / ".github")
            entries = manifest.load()
            v3_entries = [e for e in entries if e.get("installation_mode") == "v3_store"]
            self.assertEqual(len(v3_entries), 1)
            self.assertEqual(v3_entries[0]["package"], "pkg-v3")
            self.assertEqual(v3_entries[0]["package_version"], "3.1.0")
            self.assertTrue(v3_entries[0]["file"].startswith("__store__/"))

    def test_install_v3_registers_resources_in_mcp_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _authorize(ws)
            fake_mcp, engine = _build_engine(ws)
            install = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )
            with (
                patch.object(RegistryClient, "list_packages", return_value=[_registry_pkg("pkg-v3")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value=_v3_pkg_manifest("pkg-v3"),
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="content"),
            ):
                asyncio.run(install("pkg-v3"))

            registry = engine._inventory.mcp_registry
            self.assertIsNotNone(registry)
            uris = registry.list_all()
            self.assertIn("agents://pkg-v3-agent", uris)
            self.assertIn("skills://pkg-v3-skill", uris)

    def test_install_v3_preserves_existing_workspace_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _authorize(ws)
            override_path = ws / ".github" / "overrides" / "agents" / "pkg-v3-agent.md"
            override_path.parent.mkdir(parents=True, exist_ok=True)
            override_path.write_text("# user override", encoding="utf-8")

            fake_mcp, _engine = _build_engine(ws)
            install = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )
            with (
                patch.object(RegistryClient, "list_packages", return_value=[_registry_pkg("pkg-v3")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value=_v3_pkg_manifest("pkg-v3"),
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="upstream"),
            ):
                result = asyncio.run(install("pkg-v3"))

            self.assertTrue(result.get("success"))
            # Override workspace deve essere intoccato.
            self.assertEqual(override_path.read_text(encoding="utf-8"), "# user override")

    def test_remove_v3_deletes_store_and_manifest_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _authorize(ws)
            fake_mcp, _engine = _build_engine(ws)
            install = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )
            remove = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_remove_package"],
            )
            with (
                patch.object(RegistryClient, "list_packages", return_value=[_registry_pkg("pkg-v3")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value=_v3_pkg_manifest("pkg-v3"),
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="content"),
            ):
                asyncio.run(install("pkg-v3"))
                store_root = ws / "spark-framework-engine" / "packages" / "pkg-v3"
                self.assertTrue(store_root.is_dir())

                result = asyncio.run(remove("pkg-v3"))

            self.assertTrue(result.get("success"), msg=result)
            self.assertEqual(result.get("installation_mode"), "v3_store")
            self.assertTrue(result.get("store_removed"))
            self.assertFalse(store_root.exists())
            # Manifest entry rimossa.
            entries = ManifestManager(ws / ".github").load()
            self.assertEqual(
                [e for e in entries if e.get("package") == "pkg-v3"],
                [],
            )

    def test_remove_v3_does_not_delete_workspace_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _authorize(ws)
            fake_mcp, _engine = _build_engine(ws)
            install = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )
            remove = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_remove_package"],
            )
            with (
                patch.object(RegistryClient, "list_packages", return_value=[_registry_pkg("pkg-v3")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value=_v3_pkg_manifest("pkg-v3"),
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="content"),
            ):
                asyncio.run(install("pkg-v3"))
                # Crea override DOPO l'install (con file presente nello store).
                override_path = ws / ".github" / "overrides" / "agents" / "pkg-v3-agent.md"
                override_path.parent.mkdir(parents=True, exist_ok=True)
                override_path.write_text("# user override", encoding="utf-8")
                asyncio.run(remove("pkg-v3"))

            self.assertTrue(override_path.is_file())
            self.assertEqual(override_path.read_text(encoding="utf-8"), "# user override")

    def test_update_v3_idempotent_when_same_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _authorize(ws)
            fake_mcp, _engine = _build_engine(ws)
            install = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )
            update = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_update_package"],
            )
            with (
                patch.object(RegistryClient, "list_packages", return_value=[_registry_pkg("pkg-v3")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value=_v3_pkg_manifest("pkg-v3"),
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="content"),
            ):
                asyncio.run(install("pkg-v3"))
                result = asyncio.run(update("pkg-v3"))

            self.assertTrue(result.get("success"))
            self.assertEqual(result.get("update_mode"), "v3_store")
            self.assertTrue(result.get("already_up_to_date"))

    def test_update_v3_reports_overrides_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _authorize(ws)
            fake_mcp, _engine = _build_engine(ws)
            install = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )
            update = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_update_package"],
            )
            with (
                patch.object(RegistryClient, "list_packages", return_value=[_registry_pkg("pkg-v3", "3.2.0")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value=_v3_pkg_manifest("pkg-v3", version="3.1.0"),
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="content"),
            ):
                asyncio.run(install("pkg-v3"))

            # Crea override workspace per la risorsa agente.
            override_path = ws / ".github" / "overrides" / "agents" / "pkg-v3-agent.md"
            override_path.parent.mkdir(parents=True, exist_ok=True)
            override_path.write_text("# override", encoding="utf-8")

            with (
                patch.object(RegistryClient, "list_packages", return_value=[_registry_pkg("pkg-v3", "3.2.0")]),
                patch.object(
                    RegistryClient,
                    "fetch_package_manifest",
                    return_value=_v3_pkg_manifest("pkg-v3", version="3.2.0"),
                ),
                patch.object(RegistryClient, "fetch_raw_file", return_value="upgraded"),
            ):
                result = asyncio.run(update("pkg-v3"))

            self.assertTrue(result.get("success"), msg=result)
            self.assertEqual(result.get("update_mode"), "v3_store")
            blocked = result.get("override_blocked") or []
            self.assertIn("agents://pkg-v3-agent", blocked)

    def test_v2_packages_still_use_legacy_flow(self) -> None:
        """Pacchetti con min_engine_version<3.0.0 NON devono toccare lo store."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _authorize(ws)
            fake_mcp, _engine = _build_engine(ws)
            install = cast(
                Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
                fake_mcp.tools["scf_install_package"],
            )
            v2_manifest = {
                "package": "pkg-v2",
                "version": "2.0.0",
                "min_engine_version": "1.0.0",
                "dependencies": [],
                "conflicts": [],
                "file_ownership_policy": "error",
                "files": [".github/agents/pkg-v2-agent.md"],
            }
            with (
                patch.object(
                    RegistryClient, "list_packages",
                    return_value=[{"id": "pkg-v2", "repo_url": "https://github.com/example/pkg-v2", "latest_version": "2.0.0", "status": "active"}],
                ),
                patch.object(RegistryClient, "fetch_package_manifest", return_value=v2_manifest),
                patch.object(RegistryClient, "fetch_raw_file", return_value="legacy content"),
            ):
                result = asyncio.run(install("pkg-v2"))

            self.assertTrue(result.get("success"), msg=result)
            # v2: file scritto in workspace, NON nello store engine.
            self.assertTrue((ws / ".github" / "agents" / "pkg-v2-agent.md").is_file())
            store_root = ws / "spark-framework-engine" / "packages" / "pkg-v2"
            self.assertFalse(store_root.exists())
            # Nessuna sentinella v3_store nel manifest.
            entries = ManifestManager(ws / ".github").load()
            self.assertEqual(
                [e for e in entries if e.get("installation_mode") == "v3_store"],
                [],
            )


if __name__ == "__main__":
    unittest.main()
