"""Boot validation helpers — SPARK Framework Engine.

Creato in Fase 2 (boot deterministico). Espone funzioni ``validate_*()``
che restituiscono ``(manifest, reason, ok)`` per i componenti di boot.

Tutti i messaggi di log usano ``sys.stderr`` tramite il logger standard
(transport stdio: mai scrivere su stdout fuori dal canale JSON-RPC).

Feature flag: impostare la variabile d'ambiente ``SPARK_STRICT_BOOT=1``
per attivare il comportamento fatale su errori di boot degrado.
Default: ``0`` (off) in Fase 2 — ``1`` sarà il default in Fase 3.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from spark.inventory import EngineInventory

_log: logging.Logger = logging.getLogger("spark-framework-engine")

_STRICT_BOOT_ENV: str = "SPARK_STRICT_BOOT"


def validate_engine_manifest(
    engine_root: Path,
) -> tuple[dict[str, Any], str, bool]:
    """Carica e valida l'engine manifest.

    Args:
        engine_root: Radice del repository engine.

    Returns:
        Tripla ``(engine_manifest, reason, ok)`` dove:
        - ``engine_manifest``: dict caricato, o ``{}`` se fallisce.
        - ``reason``: ``"ok"`` oppure stringa di errore.
        - ``ok``: ``True`` se caricato correttamente.

    Raises:
        SystemExit: Se ``SPARK_STRICT_BOOT=1`` e il caricamento fallisce.
    """
    strict: bool = os.environ.get(_STRICT_BOOT_ENV, "0").strip() == "1"
    try:
        engine_inv = EngineInventory(engine_root=engine_root)
        engine_manifest: dict[str, Any] = engine_inv.engine_manifest
        return engine_manifest, "ok", True
    except Exception as exc:
        reason = f"Caricamento engine-manifest fallito: {exc}"
        if strict:
            _log.error(
                "[SPARK-ENGINE][ERROR] %s — boot abortito (SPARK_STRICT_BOOT=1)",
                reason,
            )
            raise SystemExit(1) from exc
        _log.warning(
            "[SPARK-ENGINE][WARNING] %s — proseguo con manifest vuoto",
            reason,
        )
        return {}, reason, False
