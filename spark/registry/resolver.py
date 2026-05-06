"""ResourceResolver — risoluzione unificata risorse SPARK con cascata priorità.

Cascata: override workspace > workspace fisico > engine store.
Nessuna dipendenza da FrameworkInventory per evitare import circolare.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spark.registry.mcp import McpResourceRegistry
    from spark.registry.store import PackageResourceStore

_log = logging.getLogger("spark-framework-engine")

# Mappa resource_type → suffisso file per ricerca nel workspace fisico.
_WORKSPACE_SUFFIXES: dict[str, list[str]] = {
    "agents": [".agent.md", ".md"],
    "skills": [".skill.md"],
    "instructions": [".instructions.md"],
    "prompts": [".prompt.md"],
}

# Mappa resource_type → nome file per format subdirectory (skills).
_SUBDIR_INDEX: dict[str, str] = {
    "skills": "SKILL.md",
}


class ResourceResolver:
    """Risolve risorse SPARK con cascata: override > workspace > store.

    Args:
        registry: McpResourceRegistry popolato con risorse engine e pacchetti.
        store: PackageResourceStore per accesso allo store centralizzato.
        workspace_github_root: Path assoluto di workspace/.github/.
    """

    def __init__(
        self,
        registry: "McpResourceRegistry",
        store: "PackageResourceStore",
        workspace_github_root: Path,
    ) -> None:
        self._registry = registry
        self._store = store
        self._ws_root = workspace_github_root

    def resolve(self, resource_type: str, name: str) -> Path | None:
        """Risolve il path di una risorsa con cascata priorità.

        Cascata:
        1. Override workspace (.github/overrides/{type}/)
        2. Workspace fisico (.github/{type}/)
        3. Engine store (engine_root/packages/<pkg>/.github/{type}/)

        Args:
            resource_type: tipo risorsa (agents, skills, instructions, prompts).
            name: nome risorsa senza estensione.

        Returns:
            Path assoluto del file risolto, o None se non trovato.
        """
        from spark.registry.mcp import McpResourceRegistry  # noqa: PLC0415

        uri = McpResourceRegistry.make_uri(resource_type, name)

        # 1. Override workspace.
        if self._registry.has_override(uri):
            path = self._registry.resolve(uri)
            if path is not None and path.is_file():
                return path

        # 2. Workspace fisico.
        ws_path = self._resolve_workspace_physical(resource_type, name)
        if ws_path is not None:
            return ws_path

        # 3. Engine store via registry.
        path = self._registry.resolve(uri)
        if path is not None and path.is_file():
            return path

        return None

    def enumerate_merged(
        self, resource_type: str
    ) -> list[tuple[str, Path, str]]:
        """Enumera tutte le risorse disponibili con deduplicazione per nome.

        Mergia workspace fisico e store, applicando la stessa cascata di
        priorità di resolve(). La sorgente con priorità maggiore vince sul
        nome in caso di duplicato.

        Args:
            resource_type: tipo risorsa (agents, skills, instructions, prompts).

        Returns:
            Lista di tuple (name, resolved_path, source) dove source è
            "override", "workspace" o "store". Ordinata per name.
        """
        seen: dict[str, tuple[Path, str]] = {}

        # Store: priorità minore — carica prima.
        for uri, path in self._registry.list_resolved(resource_type):
            name = self._name_from_uri(uri)
            if name and path.is_file() and name not in seen:
                seen[name] = (path, "store")

        # Workspace fisico: sovrascrive store se stesso nome.
        for name, path in self._iter_workspace_physical(resource_type):
            seen[name] = (path, "workspace")

        # Override: sovrascrive tutto se stesso nome.
        for uri, path in self._registry.list_overrides(resource_type):
            name = self._name_from_uri(uri)
            if name and path.is_file():
                seen[name] = (path, "override")

        return sorted(
            [(name, path, source) for name, (path, source) in seen.items()],
            key=lambda t: t[0],
        )

    # ------------------------------------------------------------------ #
    # Metodi privati                                                       #
    # ------------------------------------------------------------------ #

    def _resolve_workspace_physical(
        self, resource_type: str, name: str
    ) -> Path | None:
        """Cerca il file nel workspace fisico con i suffissi noti."""
        base = self._ws_root / resource_type

        # Format subdirectory (es. skills/name/SKILL.md).
        if resource_type in _SUBDIR_INDEX:
            subdir_file = base / name / _SUBDIR_INDEX[resource_type]
            if subdir_file.is_file():
                return subdir_file.resolve()

        # Format flat con suffissi.
        for suffix in _WORKSPACE_SUFFIXES.get(resource_type, [".md"]):
            candidate = base / f"{name}{suffix}"
            if candidate.is_file():
                return candidate.resolve()

        return None

    def _iter_workspace_physical(
        self, resource_type: str
    ) -> list[tuple[str, Path]]:
        """Itera i file del workspace fisico per tipo, senza duplicati di nome."""
        base = self._ws_root / resource_type
        if not base.is_dir():
            return []

        results: dict[str, Path] = {}

        # Format subdirectory.
        if resource_type in _SUBDIR_INDEX:
            index_name = _SUBDIR_INDEX[resource_type]
            for child in base.iterdir():
                if child.is_dir() and (child / index_name).is_file():
                    results[child.name] = (child / index_name).resolve()

        # Format flat con suffissi.
        for suffix in _WORKSPACE_SUFFIXES.get(resource_type, [".md"]):
            for fpath in base.glob(f"*{suffix}"):
                name = fpath.name[: -len(suffix)]
                if name not in results:
                    results[name] = fpath.resolve()

        return list(results.items())

    @staticmethod
    def _name_from_uri(uri: str) -> str | None:
        """Estrae il nome dalla URI (es. agents://spark-assistant → spark-assistant)."""
        if "://" not in uri:
            return None
        return uri.split("://", 1)[1].strip() or None
