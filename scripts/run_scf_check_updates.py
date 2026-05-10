#!/usr/bin/env python3
"""Simula `scf_check_updates()` localmente per uno workspace dato.

Questo script carica il modulo engine dal repo, legge il manifest in
`<workspace>/.github/.scf-manifest.json`, interroga il registry e costruisce
un piano di update simile a `scf_check_updates`.

Uso:
    python scripts/run_scf_check_updates.py --workspace "C:/path/to/workspace"

Output: JSON stampato su stdout con il report e il piano di update.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _load_engine_module() -> Any:
    engine_path = Path(__file__).resolve().parent.parent / "spark-framework-engine.py"
    # Ensure the engine package dir is on sys.path so imports like `import spark.*` work
    engine_root = engine_path.parent
    if str(engine_root) not in sys.path:
        sys.path.insert(0, str(engine_root))
    spec = importlib.util.spec_from_file_location("spark_engine", engine_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load engine module from {engine_path}")
    engine_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = engine_module
    spec.loader.exec_module(engine_module)
    return engine_module


def _parse_semver(v: str) -> Tuple[int, int, int]:
    try:
        parts = [int(p) for p in v.split(".") if p and p.isdigit()]
    except Exception:
        return (0, 0, 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def _semver_cmp(a: str, b: str) -> int:
    pa = _parse_semver(a)
    pb = _parse_semver(b)
    return (pa > pb) - (pa < pb)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--workspace", default=".", help="Workspace root path")
    args = p.parse_args()
    workspace = Path(args.workspace).resolve()
    if not workspace.is_dir():
        print(json.dumps({"success": False, "error": f"Workspace not found: {workspace}"}, ensure_ascii=False))
        return 2

    engine = _load_engine_module()

    # Read manifest
    manifest_path = workspace / ".github" / ".scf-manifest.json"
    if not manifest_path.is_file():
        print(json.dumps({"success": False, "error": f"Manifest not found: {manifest_path}"}, ensure_ascii=False))
        return 3
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"Cannot read manifest: {exc}"}, ensure_ascii=False))
        return 4

    entries = manifest.get("entries", [])
    installed_versions: Dict[str, str] = {}
    for e in entries:
        pkg = str(e.get("package", "")).strip()
        if not pkg:
            continue
        ver = str(e.get("package_version", "")).strip()
        if not ver:
            continue
        if pkg not in installed_versions:
            installed_versions[pkg] = ver
        else:
            # keep the highest (semver) found
            try:
                if _semver_cmp(ver, installed_versions[pkg]) > 0:
                    installed_versions[pkg] = ver
            except Exception:
                installed_versions[pkg] = ver

    # Build registry client
    RegistryClient = getattr(engine, "RegistryClient")
    client = RegistryClient(github_root=Path(engine.__file__).resolve().parent)

    try:
        reg_data = client.fetch()
    except Exception as exc:
        # fallback to cache via list_packages
        try:
            reg_packages = client.list_packages()
            reg_data = {"packages": reg_packages}
        except Exception as exc2:
            print(json.dumps({"success": False, "error": f"Registry unavailable: {exc} | {exc2}"}, ensure_ascii=False))
            return 5

    reg_packages = list(reg_data.get("packages", []))
    reg_index = {str(p.get("id", "")).strip(): p for p in reg_packages if isinstance(p, dict)}

    updates: List[Dict[str, Any]] = []
    dependency_map: Dict[str, List[str]] = {}
    candidate_ids = set()
    blocked: List[Dict[str, Any]] = []

    for pkg_id in sorted(installed_versions.keys()):
        installed_ver = installed_versions[pkg_id]
        reg_entry = reg_index.get(pkg_id)
        update_entry: Dict[str, Any] = {
            "package": pkg_id,
            "installed": installed_ver,
            "registry_status": reg_entry.get("status", "unknown") if reg_entry else "unknown",
        }
        if reg_entry is None:
            update_entry["status"] = "not_in_registry"
            updates.append(update_entry)
            continue

        registry_latest_ver = str(reg_entry.get("latest_version", "")).strip()
        pkg_manifest = None
        manifest_error = None
        try:
            pkg_manifest = client.fetch_package_manifest(reg_entry["repo_url"])
        except Exception as exc:
            manifest_error = str(exc)

        latest_ver = ""
        if pkg_manifest is not None:
            latest_ver = str(pkg_manifest.get("version", "")).strip()
        if not latest_ver:
            latest_ver = registry_latest_ver

        update_entry["latest"] = latest_ver

        status = "up_to_date" if installed_ver == latest_ver else "update_available"
        update_entry["status"] = status

        if pkg_manifest is not None:
            deps = pkg_manifest.get("dependencies", []) or []
            deps = [str(d).strip() if isinstance(d, str) else str(d.get("id", "")).strip() for d in deps]
            dependency_map[pkg_id] = deps
            missing_dependencies = [d for d in deps if d and d not in installed_versions]
            min_engine_version = str(pkg_manifest.get("min_engine_version", reg_entry.get("min_engine_version", ""))).strip()
            engine_version = str(getattr(engine, "ENGINE_VERSION", "0.0.0"))
            engine_compatible = True
            if min_engine_version:
                try:
                    engine_compatible = _semver_cmp(engine_version, min_engine_version) >= 0
                except Exception:
                    engine_compatible = True

            update_entry["dependencies"] = deps
            update_entry["missing_dependencies"] = missing_dependencies
            update_entry["min_engine_version"] = min_engine_version
            update_entry["engine_compatible"] = engine_compatible

            if status == "update_available":
                if missing_dependencies:
                    update_entry["status"] = "blocked_missing_dependencies"
                    blocked.append({"package": pkg_id, "reason": "missing_dependencies", "missing_dependencies": missing_dependencies})
                elif not engine_compatible:
                    update_entry["status"] = "blocked_engine_version"
                    blocked.append({"package": pkg_id, "reason": "engine_version", "required_engine_version": min_engine_version, "engine_version": engine_version})
                else:
                    candidate_ids.add(pkg_id)
        else:
            update_entry["status"] = "metadata_unavailable"
            update_entry["error"] = manifest_error
            blocked.append({"package": pkg_id, "reason": "metadata_unavailable", "error": manifest_error})

        updates.append(update_entry)

    # Resolve dependency update order for candidate_ids
    # Simple topological sort on candidate_ids using dependency_map restricted to candidate_ids
    order: List[str] = []
    if candidate_ids:
        # build indegree
        indeg: Dict[str, int] = {pkg: 0 for pkg in candidate_ids}
        adj: Dict[str, List[str]] = {pkg: [] for pkg in candidate_ids}
        for pkg in candidate_ids:
            for dep in dependency_map.get(pkg, []):
                if dep in candidate_ids:
                    adj[dep].append(pkg)
                    indeg[pkg] += 1
        # Kahn's algorithm
        queue = [pkg for pkg, d in indeg.items() if d == 0]
        while queue:
            n = queue.pop(0)
            order.append(n)
            for m in adj.get(n, []):
                indeg[m] -= 1
                if indeg[m] == 0:
                    queue.append(m)
        cycles = [pkg for pkg, d in indeg.items() if d > 0]
        if cycles:
            for c in cycles:
                blocked.append({"package": c, "reason": "dependency_cycle"})

    plan_order = []
    for pkg_id in order:
        u = next((it for it in updates if it.get("package") == pkg_id), None)
        if u is None:
            continue
        plan_order.append({
            "package": pkg_id,
            "installed": u.get("installed", ""),
            "target": u.get("latest", ""),
            "dependencies": [d for d in dependency_map.get(pkg_id, []) if d in order],
        })

    summary = {
        "up_to_date": len([u for u in updates if u.get("status") == "up_to_date"]),
        "update_available": len([u for u in updates if u.get("status") == "update_available"]),
        "not_in_registry": len([u for u in updates if u.get("status") == "not_in_registry"]),
        "blocked": len(blocked),
    }

    out = {
        "success": True,
        "total": len(updates),
        "summary": summary,
        "updates": updates,
        "plan": {"can_apply": len(plan_order) > 0 and len(blocked) == 0, "order": plan_order, "blocked": blocked},
    }

    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
