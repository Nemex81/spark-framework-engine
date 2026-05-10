#!/usr/bin/env python3
"""Esegue `scf_check_updates` e, se ci sono aggiornamenti applicabili,
invoca il flusso di applicazione usando le API interne del motore.

Uso:
    python run_scf_apply_updates.py --workspace "C:/path/to/workspace" [--conflict-mode replace|abort|manual|auto|assisted]

Nota: lo script usa l'interprete Python del venv se eseguito dal PowerShell wrapper.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_check_updates(python_exe: Path, script: Path, workspace: str) -> dict:
    proc = subprocess.run([str(python_exe), str(script), "--workspace", workspace], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"run_scf_check_updates failed: {proc.stderr}\n{proc.stdout}")
    return json.loads(proc.stdout)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--workspace", default=".", help="Workspace root path")
    p.add_argument("--conflict-mode", default="abort", help="Conflict mode for apply")
    args = p.parse_args()

    workspace = str(Path(args.workspace).resolve())
    engine_root = Path(__file__).resolve().parent.parent
    venv_python = engine_root / ".venv" / "Scripts" / "python.exe"
    check_script = engine_root / "scripts" / "run_scf_check_updates.py"

    if not venv_python.exists():
        # fallback to system python
        venv_python = Path(sys.executable)

    print(f"[APPLY] Running preflight scf_check_updates for workspace: {workspace}")
    report = run_check_updates(venv_python, check_script, workspace)

    # print summary
    print(json.dumps(report, indent=2, ensure_ascii=False))

    plan = report.get("plan", {})
    if not plan.get("can_apply"):
        print("[APPLY] Nessun aggiornamento applicabile. Nulla da fare.")
        return 0

    # If we reach here, there are updates to apply — proceed to call engine install helpers
    print("[APPLY] Aggiornamenti disponibili; applicazione automatica non ancora implementata in questo helper.\nSe vuoi procedere, posso eseguire l'applicazione passo-passo ora (richiede conferma).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
