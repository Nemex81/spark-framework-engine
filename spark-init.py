"""Initialize a VS Code workspace file for the SPARK framework engine."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


SERVER_ID = "sparkFrameworkEngine"


def _build_server_config(project_root: Path, engine_script: Path) -> dict[str, Any]:
    engine_root = engine_script.parent
    if sys.platform == "win32":
        python_cmd = engine_root / ".venv" / "Scripts" / "python.exe"
    else:
        python_cmd = engine_root / ".venv" / "bin" / "python"
    return {
        "type": "stdio",
        "command": str(python_cmd),
        "args": [str(engine_script)],
        "env": {
            "WORKSPACE_FOLDER": str(project_root),
        },
    }


def _build_workspace_template(project_root: Path, engine_script: Path) -> dict[str, Any]:
    return {
        "folders": [{"path": "."}],
        "settings": {},
        "mcp": {
            "servers": {
                SERVER_ID: _build_server_config(project_root, engine_script)
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

    settings.pop("mcp", None)

    mcp_settings = workspace_data.get("mcp")
    if mcp_settings is None:
        mcp_settings = {}
        workspace_data["mcp"] = mcp_settings
    elif not isinstance(mcp_settings, dict):
        return False, (
            f"ERRORE: la chiave 'mcp' deve essere un oggetto JSON: {workspace_path}"
        )

    servers = mcp_settings.get("servers")
    if servers is None:
        servers = {}
        mcp_settings["servers"] = servers
    elif not isinstance(servers, dict):
        return False, (
            f"ERRORE: la chiave 'mcp.servers' deve essere un oggetto JSON: "
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


def _write_vscode_mcp_json(
    project_root: Path,
    engine_script: Path,
) -> tuple[bool, str]:
    """Create or update .vscode/mcp.json with servers.sparkFrameworkEngine.

    Touches only the ``servers.sparkFrameworkEngine`` key; all other
    existing server entries are preserved.  If the file contains corrupted or
    non-object JSON the error is logged to stderr and the file is recreated
    from scratch.

    Args:
        project_root: Root directory of the target workspace.
        engine_script: Absolute path to ``spark-framework-engine.py``.

    Returns:
        A success flag and the action applied to ``.vscode/mcp.json``.
    """
    mcp_config_path = project_root / ".vscode" / "mcp.json"
    file_exists = mcp_config_path.exists()

    # Always ensure the directory exists before reading or writing.
    mcp_config_path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, Any] = {}
    if mcp_config_path.exists():
        try:
            raw = json.loads(mcp_config_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                print(
                    "[SPARK-INIT][ERROR] .vscode/mcp.json non contiene un oggetto"
                    " JSON valido; verra ricreato.",
                    file=sys.stderr,
                )
            else:
                existing = raw
        except json.JSONDecodeError as exc:
            print(
                f"[SPARK-INIT][ERROR] .vscode/mcp.json JSON corrotto ({exc});"
                " verra ricreato.",
                file=sys.stderr,
            )

    # Update only servers.sparkFrameworkEngine; leave other server entries intact.
    servers: dict[str, Any] = existing.get("servers", {})
    if not isinstance(servers, dict):
        print(
            "[SPARK-INIT][ERROR] la chiave 'servers' in .vscode/mcp.json non e un"
            " oggetto JSON; verra ricostruita.",
            file=sys.stderr,
        )
        servers = {}
    servers[SERVER_ID] = _build_server_config(project_root, engine_script)
    existing["servers"] = servers

    mcp_config_path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[SPARK-ENGINE][INFO] MCP config written to: {mcp_config_path}", file=sys.stderr)
    return True, "creato" if not file_exists else "aggiornato"


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a binary file.

    Args:
        path: File to hash.

    Returns:
        Lowercase hexadecimal SHA-256 digest string.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bootstrap_github_files(engine_root: Path, workspace_root: Path) -> list[str]:
    """Bootstrap a minimal ``.github/`` skeleton from the engine repo to the workspace.

    Copies the following assets from *engine_root/.github* to
    *workspace_root/.github*:

    - ``agents/spark-assistant.agent.md``
    - ``agents/spark-engine-maintainer.agent.md``
    - ``agents/spark-guide.agent.md``
    - ``instructions/spark-assistant-guide.instructions.md``
    - All ``prompts/scf-*.prompt.md`` files found in the engine

    Idempotency rules:

    - *Missing* destination → copy + log ``[SPARK-INIT][INFO] copiato: <name>``
    - *Identical* SHA-256 → silent skip
    - *User-modified* SHA-256 → preserve + log
      ``[SPARK-INIT][INFO] preservato (modificato dall'utente): <name>``
    - *Missing source* → log ``[SPARK-INIT][WARNING] sorgente non trovata: <path>``

    Destination subdirectories are created before every copy.

    Args:
        engine_root: Root of the ``spark-framework-engine`` repository.
        workspace_root: Root directory of the target workspace.

    Returns:
        Ordered list of formatted summary-message strings, one per file.
    """
    source_github = engine_root / ".github"
    dest_github = workspace_root / ".github"

    # Collect static files relative to .github/
    static_files = [
        "agents/spark-assistant.agent.md",
        "agents/spark-engine-maintainer.agent.md",
        "agents/spark-guide.agent.md",
        "instructions/spark-assistant-guide.instructions.md",
    ]

    # Discover all scf-*.prompt.md files in the engine prompts directory.
    prompts_source = source_github / "prompts"
    prompt_files: list[str] = []
    if prompts_source.exists():
        prompt_files = [
            f"prompts/{p.name}"
            for p in sorted(prompts_source.glob("scf-*.prompt.md"))
            if p.is_file()
        ]

    messages: list[str] = []

    for rel in static_files + prompt_files:
        src = source_github / rel
        dst = dest_github / rel
        file_name = Path(rel).name
        summary_path = f".github/{rel.replace(chr(92), '/')}"

        if not src.exists():
            print(
                f"[SPARK-INIT][WARNING] sorgente non trovata: {src}",
                file=sys.stderr,
            )
            messages.append(f"[SPARK] {summary_path} → sorgente non trovata")
            continue

        # Ensure destination directory exists before any copy attempt.
        dst.parent.mkdir(parents=True, exist_ok=True)

        if not dst.exists():
            shutil.copy2(str(src), str(dst))
            print(f"[SPARK-INIT][INFO] copiato: {file_name}", file=sys.stderr)
            messages.append(f"[SPARK] {summary_path} → copiato")
        elif _sha256_file(src) == _sha256_file(dst):
            # Content identical — silent skip; still include in summary.
            messages.append(f"[SPARK] {summary_path} → preservato")
        else:
            # User has modified the destination — preserve it.
            print(
                f"[SPARK-INIT][INFO] preservato (modificato dall'utente): {file_name}",
                file=sys.stderr,
            )
            messages.append(f"[SPARK] {summary_path} → preservato")

    return messages


def main() -> int:
    project_root = Path.cwd().resolve()
    engine_root = Path(__file__).resolve().parent
    engine_script = engine_root / "spark-framework-engine.py"

    if not engine_script.is_file():
        print(
            f"[SPARK-INIT][ERROR] server non trovato: {engine_script}",
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
        workspace_action = "aggiornato"
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
                "[SPARK-INIT][WARNING] Trovati piu file .code-workspace nella cartella"
                f" corrente. Uso: {workspace_path.name}",
                file=sys.stderr,
            )
    else:
        workspace_action = "creato"
        message = _create_workspace_file(workspace_path, project_root, engine_script)

    # Update .vscode/mcp.json with servers.sparkFrameworkEngine.
    _settings_success, settings_action = _write_vscode_mcp_json(
        project_root,
        engine_script,
    )

    # Bootstrap minimal .github/ structure from the engine repository.
    bootstrap_messages = _bootstrap_github_files(engine_root, project_root)

    # Ordered summary — the only output on stdout.
    del message
    print(f"[SPARK] .code-workspace → {workspace_action}: {workspace_path.name}")
    print(f"[SPARK] .vscode/mcp.json → {settings_action}")
    for msg in bootstrap_messages:
        print(msg)
    print()
    print("Setup completato. Il server SPARK è configurato in due modi:")
    print(f"  - Workspace : apri {workspace_path.name} in VS Code")
    print("  - Cartella  : apri direttamente la cartella, funziona lo stesso")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())