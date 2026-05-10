"""Regression test: tutti i sotto-moduli ``spark.*`` devono essere importabili.

Cattura la classe di anomalie del tipo "import path errato" come quella
risolta in ANOMALIA-NEW del report
``docs/reports/SPARK-REPORT-DualUniverse-Consolidation-v1.0.md`` (R5):
``spark/boot/onboarding.py`` importava ``PackageResourceStore`` da
``spark.packages.store`` invece che da ``spark.registry.store``. L'errore
era silenziato a runtime e non veniva intercettato dalla suite perche'
nessun test importava direttamente il modulo affetto.

Questo test esegue ``importlib.import_module()`` ricorsivamente su tutti
i package Python sotto ``spark/``, fallendo immediatamente al primo
``ImportError``. Esecuzione << 1s, indipendente dall'ambiente MCP grazie
agli stub gia' presenti in ``conftest.py``.
"""
from __future__ import annotations

import importlib
import pkgutil

import pytest

import spark


def _iter_spark_modules() -> list[str]:
    """Restituisce la lista completa dei moduli importabili sotto ``spark.*``."""
    modules: list[str] = ["spark"]
    for module_info in pkgutil.walk_packages(
        path=list(spark.__path__),
        prefix="spark.",
    ):
        modules.append(module_info.name)
    return modules


@pytest.mark.parametrize("module_name", _iter_spark_modules())
def test_spark_module_is_importable(module_name: str) -> None:
    """Importa ogni modulo ``spark.*`` e fallisce su ImportError o ModuleNotFoundError."""
    try:
        importlib.import_module(module_name)
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(
            f"Modulo orfano: {module_name!r} non importabile "
            f"(probabile import path errato). Errore: {exc}"
        )
