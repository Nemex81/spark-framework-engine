#!/usr/bin/env python3
"""Genera un report di stato SCF per uno workspace.

Esegue:
 - legge `<workspace>/.github/.scf-manifest.json`
 - estrae pacchetti installati e conteggi file
 - invoca `run_scf_check_updates.py` per il riepilogo aggiornamenti
 - conta asset SCF (agents/skills/instructions/prompts)
 - segnala override orfani (field `overrides` del manifest)

Stampa un report testuale in italiano.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def load_manifest(manifest_path: Path) -> dict:
    with manifest_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def normalize(p: str) -> str:
    return p.replace("\\","/") if isinstance(p, str) else p


def find_engine_version(engine_root: Path) -> str:
    const_path = engine_root / "spark" / "core" / "constants.py"
    if not const_path.is_file():
        return "unknown"
    txt = const_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"ENGINE_VERSION\s*=\s*[\'\"]([0-9A-Za-z\.\-]+)[\'\"]", txt)
    return m.group(1) if m else "unknown"


def run_check_updates(venv_python: Path, script: Path, workspace: str) -> dict:
    try:
        proc = subprocess.run([str(venv_python), str(script), "--workspace", workspace], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        # try to decode any JSON in stdout even if exitcode non-zero
        out = exc.stdout or ""
        try:
            return json.loads(out)
        except Exception:
            return {"success": False, "error": f"scf_check_updates failed: {exc} | {exc.stdout} {exc.stderr}"}
    try:
        return json.loads(proc.stdout)
    except Exception:
        return {"success": False, "error": "Invalid JSON from scf_check_updates"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--workspace", default=".", help="Workspace root path")
    args = p.parse_args()

    workspace = Path(args.workspace).resolve()
    engine_root = Path(__file__).resolve().parent.parent
    manifest_path = workspace / ".github" / ".scf-manifest.json"

    if not manifest_path.is_file():
        print(f"ERRORE: manifest non trovato: {manifest_path}")
        return 2

    manifest = load_manifest(manifest_path)
    entries = manifest.get("entries", [])

    packages: dict[str, dict] = {}
    unique_files: set[str] = set()

    for e in entries:
        pkg = str(e.get("package", "")).strip()
        if not pkg:
            continue
        file_field = e.get("file", "")
        norm_file = normalize(file_field)
        if norm_file.startswith("__store__/"):
            # v3_store sentinel entry
            files_list = [normalize(f) for f in e.get("files", [])]
            packages[pkg] = {
                "package": pkg,
                "version": str(e.get("package_version", "")).strip(),
                "installation_mode": "v3_store",
                "file_count": len(files_list),
                "files": files_list,
            }
            for f in files_list:
                unique_files.add(f)
            continue

        # v2 workspace file entry
        if pkg not in packages:
            packages[pkg] = {
                "package": pkg,
                "version": str(e.get("package_version", "")).strip(),
                "installation_mode": "v2_workspace",
                "files": set(),
            }
        # ensure installation_mode stays v3_store if already set
        if packages[pkg].get("installation_mode") != "v3_store":
            packages[pkg]["installation_mode"] = "v2_workspace"
        # normalize existing files container to a set so we can add
        files_obj = packages[pkg].get("files")
        if isinstance(files_obj, list):
            packages[pkg]["files"] = set(files_obj)
        packages[pkg]["files"].add(norm_file)
        unique_files.add(norm_file)
        # prefer explicit package_version if not set
        if not packages[pkg].get("version"):
            packages[pkg]["version"] = str(e.get("package_version", "")).strip()

    # finalize v2 sets -> lists and file_count
    for pkg, info in list(packages.items()):
        if info.get("installation_mode") == "v2_workspace":
            files = sorted(list(info.get("files", set())))
            packages[pkg]["files"] = files
            packages[pkg]["file_count"] = len(files)

    # asset counts
    assets = {"agents": 0, "skills": 0, "instructions": 0, "prompts": 0}
    for f in unique_files:
        if not f.startswith(".github/") and not f.startswith(".github"):
            # some store entries may lack the leading dot; normalize if necessary
            nf = f
            if nf.startswith("github/"):
                nf = "." + nf
            else:
                nf = f
        else:
            nf = f
        if nf.startswith(".github/agents/"):
            assets["agents"] += 1
        elif nf.startswith(".github/skills/"):
            assets["skills"] += 1
        elif nf.startswith(".github/instructions/"):
            assets["instructions"] += 1
        elif nf.startswith(".github/prompts/"):
            assets["prompts"] += 1

    # run updates check via helper script
    venv_python = engine_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        venv_python = Path(sys.executable)
    check_script = engine_root / "scripts" / "run_scf_check_updates.py"
    updates_report = run_check_updates(venv_python, check_script, str(workspace))

    # project-profile initialized check
    project_profile = workspace / ".github" / "project-profile.md"
    initialized_val = "unknown"
    if project_profile.is_file():
        txt = project_profile.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"initialized\s*:\s*(true|false)", txt, flags=re.IGNORECASE)
        if m:
            initialized_val = m.group(1).lower()
        else:
            initialized_val = "not set"
    else:
        initialized_val = "missing"

    engine_version = find_engine_version(engine_root)

    # overrides
    overrides = manifest.get("overrides", []) or []

    # build textual report
    lines = []
    lines.append("**Workspace**")
    lines.append(f"- **Root:** `{str(workspace)}`")
    lines.append(f"- **Initialized:** {initialized_val}")
    lines.append(f"- **Engine version:** {engine_version}")
    lines.append("")

    lines.append("**Pacchetti installati**")
    if not packages:
        lines.append("- Nessun pacchetto SCF installato nel manifest.")
    else:
        for pkg_id, info in sorted(packages.items(), key=lambda x: x[0]):
            lines.append(f"- **package:** `{pkg_id}` | **version:** {info.get('version','n/a')} | **file_count:** {info.get('file_count',0)} | **installation_mode:** {info.get('installation_mode')}")
            if info.get("installation_mode") == "v2_workspace":
                lines.append("  - modified_by breakdown: non tracciato nel manifest (use `scf_plan_install` per preflight dettagliato)")
            else:
                # v3_store resources breakdown
                files = [normalize(x) for x in info.get("files", [])]
                agents = sum(1 for f in files if f.startswith('.github/agents/'))
                skills = sum(1 for f in files if f.startswith('.github/skills/'))
                instr = sum(1 for f in files if f.startswith('.github/instructions/'))
                prompts = sum(1 for f in files if f.startswith('.github/prompts/'))
                lines.append(f"  - risorse esposte (counts): agents={agents}, skills={skills}, instructions={instr}, prompts={prompts}")
    lines.append("")

    lines.append("**Asset SCF**")
    lines.append(f"- **agents:** {assets['agents']} | **skills:** {assets['skills']} | **instructions:** {assets['instructions']} | **prompts:** {assets['prompts']}")
    lines.append("")

    lines.append("**Aggiornamenti**")
    if isinstance(updates_report, dict) and updates_report.get("success"):
        summary = updates_report.get("summary", {})
        lines.append(f"- up_to_date: {summary.get('up_to_date', 0)}")
        lines.append(f"- update_available: {summary.get('update_available', 0)}")
        lines.append(f"- not_in_registry: {summary.get('not_in_registry', 0)}")
        lines.append(f"- blocked: {summary.get('blocked', 0)}")
    else:
        lines.append(f"- scf_check_updates non disponibile: {updates_report.get('error')}")
    lines.append("")

    lines.append("**Override orfani**")
    if overrides:
        lines.append(f"- Trovati {len(overrides)} override: ")
        for o in overrides:
            lines.append(f"  - {o}")
        lines.append("  Suggerimento: rimuovi manualmente i file elencati se non più necessari.")
    else:
        lines.append("- Nessun override orfano trovato (campo `overrides` vuoto nel manifest).")

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
