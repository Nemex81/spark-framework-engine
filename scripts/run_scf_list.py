"""Lista i pacchetti disponibili nel registry SCF.

Uso: python scripts/run_scf_list.py

Istanzia RegistryClient direttamente senza passare per il server MCP.
Richiede connessione internet per contattare il registry pubblico.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import traceback
from pathlib import Path
from types import ModuleType


def _load_engine_module() -> ModuleType:
    """Load the engine module from the repository root."""
    engine_path = Path(__file__).resolve().parent.parent / "spark-framework-engine.py"
    spec = importlib.util.spec_from_file_location("spark_engine", engine_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load engine module from {engine_path}")
    engine_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = engine_module
    spec.loader.exec_module(engine_module)
    return engine_module


def main() -> int:
    """Print the registry package list as JSON and return a process exit code."""
    try:
        engine_module = _load_engine_module()
        registry_client = engine_module.RegistryClient

        with tempfile.TemporaryDirectory() as tmp_dir:
            client = registry_client(github_root=Path(tmp_dir))
            packages = client.list_packages()

        if not packages:
            print(
                json.dumps({"ok": True, "count": 0, "packages": []}, ensure_ascii=False),
                flush=True,
            )
            return 0

        result = [
            {
                "id": package.get("id"),
                "description": package.get("description", ""),
                "latest_version": package.get("latest_version", ""),
                "status": package.get("status", "unknown"),
            }
            for package in packages
        ]
        print(
            json.dumps(
                {"ok": True, "count": len(result), "packages": result},
                indent=2,
                ensure_ascii=False,
            ),
            flush=True,
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {"ok": False, "error": str(exc), "traceback": traceback.format_exc()},
                ensure_ascii=False,
            ),
            flush=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
