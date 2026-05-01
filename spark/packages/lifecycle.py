# Modulo packages/lifecycle — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""v3 package lifecycle helpers — install / update / remove store-based."""
from __future__ import annotations

import json
import logging
import shutil
import urllib.error
from pathlib import Path
from typing import Any, Callable, Mapping

from spark.core.constants import _RESOURCE_TYPES
from spark.registry.mcp import McpResourceRegistry
from spark.registry.store import PackageResourceStore
from spark.registry.v3_store import _build_package_raw_url_base

_log: logging.Logger = logging.getLogger("spark-framework-engine")


def _install_package_v3_into_store(
    engine_root: Path,
    package_id: str,
    pkg: Mapping[str, Any],
    pkg_manifest: Mapping[str, Any],
    fetch_raw_file: Callable[[str], str],
) -> dict[str, Any]:
    """Scarica i file del pacchetto v3 dentro ``engine_dir/packages/{pkg_id}/``.

    Args:
        engine_root: directory di base dell'engine.
        package_id: ID del pacchetto.
        pkg: entry del registry (deve contenere ``repo_url``).
        pkg_manifest: package-manifest.json scaricato.
        fetch_raw_file: callable che accetta un URL raw e ritorna il contenuto.

    Returns:
        ``{"success": bool, "store_path": str, "files": [...], "errors": [...]}``.
        Se ``success`` è False non viene scritto alcun file (cleanup automatico).
    """
    store = PackageResourceStore(engine_root)
    package_root = (store.packages_root / package_id).resolve()
    github_root = package_root / ".github"
    files: list[str] = list(pkg_manifest.get("files", []) or [])
    if not files:
        return {
            "success": False,
            "store_path": str(package_root),
            "files": [],
            "errors": [f"package '{package_id}' declares no files"],
        }
    try:
        base_raw_url = _build_package_raw_url_base(str(pkg["repo_url"]))
    except ValueError as exc:
        return {
            "success": False,
            "store_path": str(package_root),
            "files": [],
            "errors": [str(exc)],
        }

    written: list[tuple[Path, str]] = []
    errors: list[str] = []
    for file_path in files:
        rel = file_path.removeprefix(".github/")
        # Rifiutiamo path con risalita per evitare scritture fuori dallo store.
        if ".." in Path(rel).parts:
            errors.append(f"unsafe path: {file_path}")
            continue
        try:
            content = fetch_raw_file(base_raw_url + file_path)
        except (urllib.error.URLError, OSError) as exc:
            errors.append(f"{file_path}: {exc}")
            continue
        written.append((github_root / rel, content))

    if errors:
        return {
            "success": False,
            "store_path": str(package_root),
            "files": [],
            "errors": errors,
        }

    # Scrittura atomica della directory: prima creiamo, poi popoliamo.
    package_root.mkdir(parents=True, exist_ok=True)
    github_root.mkdir(parents=True, exist_ok=True)
    persisted: list[str] = []
    try:
        for dest, content in written:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            persisted.append(str(dest.relative_to(package_root)))
        manifest_path = package_root / "package-manifest.json"
        manifest_path.write_text(
            json.dumps(dict(pkg_manifest), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        return {
            "success": False,
            "store_path": str(package_root),
            "files": persisted,
            "errors": [f"write failure: {exc}"],
        }
    return {
        "success": True,
        "store_path": str(package_root),
        "files": sorted(persisted),
        "errors": [],
    }


def _remove_package_v3_from_store(engine_root: Path, package_id: str) -> dict[str, Any]:
    """Rimuove l'intera directory ``engine_dir/packages/{pkg_id}/`` dallo store."""
    store = PackageResourceStore(engine_root)
    package_root = (store.packages_root / package_id).resolve()
    if not package_root.is_dir():
        return {"removed": False, "store_path": str(package_root)}
    # Verifica difensiva che il path sia effettivamente sotto packages_root.
    try:
        package_root.relative_to(store.packages_root.resolve())
    except ValueError:
        return {
            "removed": False,
            "store_path": str(package_root),
            "error": "store path escapes packages root",
        }
    try:
        shutil.rmtree(package_root)
    except OSError as exc:
        return {
            "removed": False,
            "store_path": str(package_root),
            "error": str(exc),
        }
    return {"removed": True, "store_path": str(package_root)}


def _list_orphan_overrides_for_package(
    registry: "McpResourceRegistry",
    package_id: str,
) -> list[dict[str, Any]]:
    """Lista override workspace appartenenti al pacchetto ``package_id``.

    Usato come warning quando un pacchetto v3 viene rimosso ma l'utente
    ha override personalizzati per quelle stesse risorse.
    """
    orphans: list[dict[str, Any]] = []
    for uri in registry.list_all():
        meta = registry.get_metadata(uri) or {}
        if str(meta.get("package", "")).strip() != package_id:
            continue
        if meta.get("override") is None:
            continue
        orphans.append(
            {
                "uri": uri,
                "type": meta.get("resource_type"),
                "path": meta.get("override"),
            }
        )
    return orphans


def _v3_overrides_blocking_update(
    registry: "McpResourceRegistry",
    package_id: str,
    pkg_manifest: Mapping[str, Any],
) -> list[str]:
    """Lista URI del pacchetto con override workspace attivo (skip su update)."""
    blocked: list[str] = []
    resources = pkg_manifest.get("mcp_resources") or {}
    if not isinstance(resources, Mapping):
        return blocked
    for resource_type in _RESOURCE_TYPES:
        names = resources.get(resource_type) or []
        if not isinstance(names, list):
            continue
        for name in names:
            uri = McpResourceRegistry.make_uri(resource_type, str(name))
            if registry.has_override(uri):
                blocked.append(uri)
    return sorted(blocked)
