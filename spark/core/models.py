"""Data models — estratto da spark-framework-engine.py durante Fase 0.

Dataclasses immutabili e costanti di stato usate trasversalmente.
Nessuna logica, nessuna dipendenza fuori da pathlib/typing/dataclasses.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict


@dataclass(frozen=True)
class WorkspaceContext:
    """Resolve and expose the active workspace and all SCF-relevant roots."""

    workspace_root: Path
    github_root: Path
    engine_root: Path


@dataclass(frozen=True)
class FrameworkFile:
    """Describe a discovered SCF file and the metadata extracted from it."""

    name: str
    path: Path
    category: str
    summary: str
    metadata: dict[str, Any]


MERGE_STATUS_IDENTICAL: str = "identical"
MERGE_STATUS_CLEAN: str = "clean"
MERGE_STATUS_CONFLICT: str = "conflict"


@dataclass(frozen=True)
class MergeConflict:
    """Describe a single unresolved block produced by a 3-way merge."""

    start_line: int
    end_line: int
    base_text: str
    ours_text: str
    theirs_text: str


@dataclass(frozen=True)
class MergeResult:
    """Describe the outcome of a 3-way merge attempt."""

    status: str
    merged_text: str
    conflicts: tuple[MergeConflict, ...] = ()
    sections: tuple[str | MergeConflict, ...] = ()


class SparkToolResult(TypedDict, total=False):
    """Envelope standard per i payload restituiti dai tool MCP SPARK.

    Tutti i campi sono opzionali (total=False) per retrocompatibilità
    con i tool esistenti. I nuovi tool devono popolare almeno:
    success, status, message.

    I tool esistenti migrano gradualmente verso questo schema nelle
    release successive.
    """

    success: bool
    status: str
    message: str
    data: dict
    warnings: list
    actions_required: list
    metadata: dict
