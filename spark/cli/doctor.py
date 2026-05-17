"""spark.cli.doctor — Diagnostica avanzata SPARK (scf doctor).

Esegue un insieme di verifiche strutturate sul workspace e sul motore SPARK.
Modalità disponibili:
  - diagnostica base: stampa risultati leggibili
  - ``--fix``: tenta riparazione automatica dei problemi rilevabili
  - ``--report``: emette il report in formato JSON su stdout (silenzioso altrove)

Accessibile NVDA: nessun unicode decorativo, output leggibile riga per riga.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spark.core.constants import ENGINE_VERSION

_log: logging.Logger = logging.getLogger("spark-framework-engine")

__all__ = ["run_doctor"]

# Nomi delle verifiche standard
_CHECK_GITHUB_ROOT = "github_root"
_CHECK_MANIFEST = "manifest"
_CHECK_ENGINE_VERSION = "engine_version"
_CHECK_UPDATE_POLICY = "update_policy"
_CHECK_LOCKFILE = "lockfile"
_CHECK_SPARK_DIR = "spark_dir"


def run_doctor(
    github_root: Path,
    engine_root: Path,
    *,
    fix: bool = False,
    report: bool = False,
) -> dict[str, Any]:
    """Esegue la diagnostica SPARK completa.

    Args:
        github_root: Root ``.github/`` del workspace.
        engine_root: Root del motore SPARK.
        fix: Se ``True``, tenta la riparazione automatica dei problemi rilevabili.
        report: Se ``True``, il chiamante gestisce l'output (solo JSON).

    Returns:
        dict con i campi:
          success (bool): True se nessun errore critico.
          status (str): ``"ok"``, ``"warning"`` o ``"error"``.
          checks (list[dict]): Lista di verifiche con name, status, message.
          errors (list[str]): Messaggi di errore critico.
          warnings (list[str]): Messaggi di avviso non critico.
          fixed (list[str]): Riparazioni effettuate (solo con fix=True).
          engine_version (str): Versione motore verificata.
          timestamp (str): ISO timestamp dell'esecuzione.
    """
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    fixed: list[str] = []

    workspace_root = github_root.parent if github_root.name == ".github" else github_root.parent

    # ── Verifica 1: github_root ─────────────────────────────────────────── #
    if github_root.is_dir():
        checks.append({
            "name": _CHECK_GITHUB_ROOT,
            "status": "ok",
            "message": f".github/ presente: {github_root}",
        })
    else:
        if fix:
            try:
                github_root.mkdir(parents=True, exist_ok=True)
                fixed.append(f"Creata directory {github_root}")
                checks.append({
                    "name": _CHECK_GITHUB_ROOT,
                    "status": "ok",
                    "message": f".github/ creata automaticamente: {github_root}",
                })
            except OSError as exc:
                checks.append({
                    "name": _CHECK_GITHUB_ROOT,
                    "status": "error",
                    "message": f".github/ assente e creazione fallita: {exc}",
                })
                errors.append(f".github/ non disponibile: {exc}")
        else:
            checks.append({
                "name": _CHECK_GITHUB_ROOT,
                "status": "error",
                "message": f".github/ non trovata: {github_root}",
            })
            errors.append(f".github/ non trovata: {github_root}")

    # ── Verifica 2: manifest ────────────────────────────────────────────── #
    try:
        from spark.manifest.manifest import ManifestManager  # noqa: PLC0415

        mgr = ManifestManager(github_root)
        entries = mgr.load()
        installed = mgr.get_installed_versions()
        checks.append({
            "name": _CHECK_MANIFEST,
            "status": "ok",
            "message": f"Manifest OK — {len(installed)} pacchetti installati.",
            "packages": list(installed.keys()),
        })
    except Exception as exc:  # noqa: BLE001
        checks.append({
            "name": _CHECK_MANIFEST,
            "status": "error",
            "message": f"Errore lettura manifest: {exc}",
        })
        errors.append(f"Manifest non leggibile: {exc}")
        installed = {}
        entries = []

    # ── Verifica 3: engine_version ──────────────────────────────────────── #
    checks.append({
        "name": _CHECK_ENGINE_VERSION,
        "status": "ok",
        "message": f"ENGINE_VERSION: {ENGINE_VERSION}",
        "version": ENGINE_VERSION,
    })

    # ── Verifica 4: update_policy ───────────────────────────────────────── #
    policy_file = github_root / "runtime" / "update_policy.json"
    if policy_file.is_file():
        try:
            policy_data = json.loads(policy_file.read_text(encoding="utf-8"))
            checks.append({
                "name": _CHECK_UPDATE_POLICY,
                "status": "ok",
                "message": (
                    f"update_policy OK — auto_update={policy_data.get('auto_update')}, "
                    f"default_mode={policy_data.get('default_mode')}"
                ),
            })
        except (json.JSONDecodeError, OSError) as exc:
            checks.append({
                "name": _CHECK_UPDATE_POLICY,
                "status": "warning",
                "message": f"update_policy.json non leggibile: {exc}",
            })
            warnings.append(f"update_policy.json malformato: {exc}")
    else:
        checks.append({
            "name": _CHECK_UPDATE_POLICY,
            "status": "warning",
            "message": "update_policy.json assente (usato default engine).",
        })
        warnings.append("update_policy.json assente")

    # ── Verifica 5: .spark/ directory ──────────────────────────────────── #
    spark_dir = workspace_root / ".spark"
    if spark_dir.is_dir():
        checks.append({
            "name": _CHECK_SPARK_DIR,
            "status": "ok",
            "message": f".spark/ presente: {spark_dir}",
        })
    else:
        if fix:
            try:
                spark_dir.mkdir(parents=True, exist_ok=True)
                fixed.append(f"Creata directory {spark_dir}")
                checks.append({
                    "name": _CHECK_SPARK_DIR,
                    "status": "ok",
                    "message": f".spark/ creata automaticamente: {spark_dir}",
                })
            except OSError as exc:
                checks.append({
                    "name": _CHECK_SPARK_DIR,
                    "status": "warning",
                    "message": f".spark/ assente e creazione fallita: {exc}",
                })
                warnings.append(f".spark/ non disponibile: {exc}")
        else:
            checks.append({
                "name": _CHECK_SPARK_DIR,
                "status": "warning",
                "message": f".spark/ non trovata in {workspace_root} (nessun lockfile generato).",
            })
            warnings.append(".spark/ assente — lockfile non ancora generato")

    # ── Verifica 6: lockfile sync con manifest ──────────────────────────── #
    try:
        from spark.manifest.lockfile import LockfileManager  # noqa: PLC0415

        lock_mgr = LockfileManager(workspace_root)
        lock_data = lock_mgr.load()
        lock_entries = lock_data.get("entries", {})
        manifest_ids = set(installed.keys())
        lock_ids = set(lock_entries.keys())

        missing_in_lock = manifest_ids - lock_ids
        stale_in_lock = lock_ids - manifest_ids

        if not missing_in_lock and not stale_in_lock:
            checks.append({
                "name": _CHECK_LOCKFILE,
                "status": "ok",
                "message": f"Lockfile sincronizzato — {len(lock_entries)} entry.",
            })
        else:
            detail_parts = []
            if missing_in_lock:
                detail_parts.append(f"mancanti nel lock: {sorted(missing_in_lock)}")
            if stale_in_lock:
                detail_parts.append(f"stale nel lock: {sorted(stale_in_lock)}")
            detail = "; ".join(detail_parts)

            if fix:
                # Rimuovi entry stale
                for pkg_id in stale_in_lock:
                    lock_mgr.remove(pkg_id)
                    fixed.append(f"Rimossa entry stale dal lockfile: {pkg_id}")
                # Aggiungi entry mancanti (senza file hash)
                for pkg_id in missing_in_lock:
                    version = installed.get(pkg_id, "unknown")
                    lock_mgr.upsert(
                        package_id=pkg_id,
                        version=version,
                        source="U2",
                        dependencies=[],
                    )
                    fixed.append(f"Aggiunta entry mancante al lockfile: {pkg_id} {version}")
                checks.append({
                    "name": _CHECK_LOCKFILE,
                    "status": "ok",
                    "message": f"Lockfile riparato automaticamente: {detail}",
                })
            else:
                checks.append({
                    "name": _CHECK_LOCKFILE,
                    "status": "warning",
                    "message": f"Lockfile non sincronizzato: {detail}",
                })
                warnings.append(f"Lockfile out-of-sync: {detail}")
    except Exception as exc:  # noqa: BLE001
        checks.append({
            "name": _CHECK_LOCKFILE,
            "status": "warning",
            "message": f"Errore verifica lockfile: {exc}",
        })
        warnings.append(f"Lockfile non verificabile: {exc}")

    # ── Calcola stato globale ───────────────────────────────────────────── #
    if errors:
        overall_status = "error"
    elif warnings:
        overall_status = "warning"
    else:
        overall_status = "ok"

    result: dict[str, Any] = {
        "success": len(errors) == 0,
        "status": overall_status,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "engine_version": ENGINE_VERSION,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
    if fixed:
        result["fixed"] = fixed

    # ── Output ──────────────────────────────────────────────────────────── #
    if report:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_doctor_report(result)

    return result


def _print_doctor_report(result: dict[str, Any]) -> None:
    """Stampa il report diagnostico in formato testuale leggibile."""
    status_label = result.get("status", "?").upper()
    print(f"\nSCF Doctor — stato: {status_label}")
    print(f"ENGINE_VERSION: {result.get('engine_version', '?')}")
    print(f"Timestamp: {result.get('timestamp', '?')}\n")

    for check in result.get("checks", []):
        icon = {"ok": "[OK]", "warning": "[WARN]", "error": "[ERR]"}.get(
            check.get("status", "?"), "[?]"
        )
        print(f"  {icon} {check.get('name', '?')}: {check.get('message', '')}")

    fixed = result.get("fixed", [])
    if fixed:
        print("\nRiparazioni applicate:")
        for item in fixed:
            print(f"  [FIX] {item}")

    errors = result.get("errors", [])
    if errors:
        print("\nERRORE:")
        for msg in errors:
            print(f"  {msg}")

    warnings = result.get("warnings", [])
    if warnings:
        print("\nAvvisi:")
        for msg in warnings:
            print(f"  {msg}")
