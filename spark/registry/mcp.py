# Modulo registry/mcp — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""McpResourceRegistry — indice URI -> (engine_path, override_path)."""
from __future__ import annotations

from pathlib import Path
from typing import Any


class McpResourceRegistry:
    """Indice in-memory delle risorse MCP esposte dall'engine.

    Popolata al boot da :class:`FrameworkInventory` a partire da
    ``engine-manifest.json`` e dai ``package-manifest.json`` dei pacchetti
    installati (in modalità v3.0) o dei pacchetti workspace (in modalità di
    transizione v2.x).

    Risoluzione con priorità: ``override`` > ``engine``. Se non esiste
    override, :meth:`resolve` ritorna il path engine. :meth:`resolve_engine`
    ignora sempre l'override.
    """

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, Any]] = {}

    @staticmethod
    def make_uri(resource_type: str, name: str) -> str:
        return f"{resource_type}://{name}"

    def register(
        self,
        uri: str,
        engine_path: Path,
        package: str,
        resource_type: str,
    ) -> None:
        """Registra (o sovrascrive) un'entry engine-side."""
        existing = self._entries.get(uri, {})
        self._entries[uri] = {
            "engine": Path(engine_path).resolve(),
            "override": existing.get("override"),
            "package": package,
            "resource_type": resource_type,
        }

    def register_override(self, uri: str, override_path: Path) -> None:
        """Associa un workspace-override a un URI già registrato.

        Se l'URI non è ancora registrato, l'override viene comunque tracciato
        con engine_path=None (caso di override orfano post-rimozione pacchetto).
        """
        existing = self._entries.get(uri, {})
        self._entries[uri] = {
            "engine": existing.get("engine"),
            "override": Path(override_path).resolve(),
            "package": existing.get("package", "<unknown>"),
            "resource_type": existing.get("resource_type", uri.split("://", 1)[0]),
        }

    def drop_override(self, uri: str) -> bool:
        """Rimuove il riferimento all'override (non tocca il filesystem)."""
        entry = self._entries.get(uri)
        if not entry or entry.get("override") is None:
            return False
        entry["override"] = None
        return True

    def unregister(self, uri: str) -> bool:
        """Rimuove completamente l'entry (engine + override) per ``uri``.

        Usato dal lifecycle v3 quando un pacchetto viene rimosso dallo store.
        Non tocca il filesystem. Ritorna ``True`` se l'entry esisteva.
        """
        if uri in self._entries:
            del self._entries[uri]
            return True
        return False

    def unregister_package(self, package_id: str) -> list[str]:
        """Rimuove tutte le entry il cui ``package`` corrisponde a ``package_id``.

        Ritorna la lista degli URI rimossi (ordinata).
        """
        # Raccogliamo gli URI per evitare di mutare il dict durante l'iterazione.
        to_drop = sorted(
            uri
            for uri, entry in self._entries.items()
            if str(entry.get("package", "")).strip() == package_id
        )
        for uri in to_drop:
            del self._entries[uri]
        return to_drop

    def resolve(self, uri: str) -> Path | None:
        """Ritorna il path effettivo: override se presente, altrimenti engine."""
        entry = self._entries.get(uri)
        if entry is None:
            return None
        return entry.get("override") or entry.get("engine")

    def resolve_engine(self, uri: str) -> Path | None:
        """Ritorna sempre la versione canonica engine (mai l'override)."""
        entry = self._entries.get(uri)
        if entry is None:
            return None
        return entry.get("engine")

    def has_override(self, uri: str) -> bool:
        entry = self._entries.get(uri)
        return bool(entry and entry.get("override"))

    def list_by_type(self, resource_type: str) -> list[str]:
        """Elenca gli URI registrati per un tipo di risorsa."""
        return sorted(
            uri
            for uri, entry in self._entries.items()
            if entry.get("resource_type") == resource_type
        )

    def list_all(self) -> list[str]:
        return sorted(self._entries.keys())

    def get_metadata(self, uri: str) -> dict[str, Any] | None:
        entry = self._entries.get(uri)
        if entry is None:
            return None
        return {
            "uri": uri,
            "engine": str(entry["engine"]) if entry.get("engine") else None,
            "override": str(entry["override"]) if entry.get("override") else None,
            "package": entry.get("package"),
            "resource_type": entry.get("resource_type"),
        }
