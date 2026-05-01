"""Public re-exports for the ``spark.boot`` package.

Extracted during Phase 0 modular refactoring.
"""
from __future__ import annotations

from spark.boot.engine import SparkFrameworkEngine
from spark.boot.sequence import _build_app
from spark.boot.validation import resolve_runtime_dir

__all__ = [
    "SparkFrameworkEngine",
    "_build_app",
    "resolve_runtime_dir",
]
