"""Initialize a VS Code workspace file for the SPARK framework engine."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


SERVER_ID = "sparkFrameworkEngine"


def _build_server_config(project_root: Path, engine_script: Path) -> dict[str, Any]:
    return {
        "type": "stdio",
        "command": sys.executable,
        "args": [str(engine_script)],
        "env": {
            "WORKSPACE_FOLDER": str(project_root),
        },
    }


def _build_workspace_template(project_root: Path, engine_script: Path) -> dict[str, Any]:
    return {
        "folders": [{"path": "."}],
        "settings": {
            "mcp": {
                "servers": {
                    SERVER_ID: _build_server_config(project_root, engine_script)
                }
            }
        },
    }


def _workspace_candidates(project_root: Path) -> list[Path]:
    return sorted(path for path in project_root.glob("*.code-workspace") if path.is_file())


def _update_existing_workspace(
    workspace_path: Path,
    project_root: Path,
    engine_script: Path,
) -> tuple[bool, str]:
    try:
        workspace_data = json.loads(workspace_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, (
            f"ERRORE: il file workspace non contiene JSON valido: {workspace_path}\n"
            f"Dettaglio: {exc}"
        )

    if not isinstance(workspace_data, dict):
        return False, (
            f"ERRORE: il file workspace deve contenere un oggetto JSON in root: "
            f"{workspace_path}"
        )

    settings = workspace_data.get("settings")
    if settings is None:
        settings = {}
        workspace_data["settings"] = settings
    elif not isinstance(settings, dict):
        return False, (
            f"ERRORE: la chiave 'settings' deve essere un oggetto JSON: {workspace_path}"
        )

    mcp_settings = settings.get("mcp")
    if mcp_settings is None:
        mcp_settings = {}
        settings["mcp"] = mcp_settings
    elif not isinstance(mcp_settings, dict):
        return False, (
            f"ERRORE: la chiave 'settings.mcp' deve essere un oggetto JSON: {workspace_path}"
        )

    servers = mcp_settings.get("servers")
    if servers is None:
        servers = {}
        mcp_settings["servers"] = servers
    elif not isinstance(servers, dict):
        return False, (
            f"ERRORE: la chiave 'settings.mcp.servers' deve essere un oggetto JSON: "
            f"{workspace_path}"
        )

    servers[SERVER_ID] = _build_server_config(project_root, engine_script)
    workspace_path.write_text(
        json.dumps(workspace_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return True, f"File salvato: {workspace_path}"


def _create_workspace_file(
    workspace_path: Path,
    project_root: Path,
    engine_script: Path,
) -> str:
    workspace_data = _build_workspace_template(project_root, engine_script)
    workspace_path.write_text(
        json.dumps(workspace_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return f"File salvato: {workspace_path}"


def main() -> int:
    project_root = Path.cwd().resolve()
    engine_root = Path(__file__).resolve().parent
    engine_script = engine_root / "spark-framework-engine.py"

    if not engine_script.is_file():
        print(
            f"ERRORE: server non trovato: {engine_script}",
            file=sys.stderr,
        )
        return 1

    workspace_candidates = _workspace_candidates(project_root)
    workspace_path = (
        workspace_candidates[0]
        if workspace_candidates
        else project_root / f"{project_root.name}.code-workspace"
    )

    if workspace_candidates:
        success, message = _update_existing_workspace(
            workspace_path,
            project_root,
            engine_script,
        )
        if not success:
            print(message, file=sys.stderr)
            return 1
        if len(workspace_candidates) > 1:
            print(
                "Trovati piu file .code-workspace nella cartella corrente. "
                f"Uso: {workspace_path.name}"
            )
    else:
        message = _create_workspace_file(workspace_path, project_root, engine_script)

    print(message)
    print(
        "Prossimo passo: apri VS Code e usa File > Apri area di lavoro dal file > "
        f"{workspace_path.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())