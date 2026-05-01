# Modulo registry/store — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""PackageResourceStore — deposito centralizzato file di pacchetto."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, ClassVar, Mapping

from spark.core.constants import _RESOURCE_TYPES


def _resource_filename_candidates(resource_type: str, name: str) -> tuple[str, ...]:
    """Convenzioni di naming accettate per ciascun tipo risorsa."""
    if resource_type == "agents":
        return (f"{name}.agent.md", f"{name}.md")
    if resource_type == "prompts":
        return (f"{name}.prompt.md",)
    if resource_type == "instructions":
        return (f"{name}.instructions.md",)
    if resource_type == "skills":
        # Skill con file flat (.skill.md) oppure cartella con SKILL.md
        return (f"{name}.skill.md", f"{name}/SKILL.md")
    return (f"{name}.md",)


class PackageResourceStore:
    """Gestisce il deposito centralizzato dei file di pacchetto nell'engine.

    Path base: ``engine_dir / "packages" / {package_id} / ".github" / {type}``.

    Lo store è una classe puramente filesystem: non parla con MCP, non legge
    manifest. È pensata per essere consultata da
    :class:`McpResourceRegistry` e dai tool ``scf_read_resource`` /
    ``scf_override_resource`` introdotti in Fase 3.

    Durante la transizione v2.x → v3.0 il deposito può non essere popolato:
    in tal caso :meth:`resolve` ritorna ``None`` e :meth:`list_resources`
    ritorna lista vuota senza sollevare eccezioni.
    """

    PACKAGES_DIRNAME: ClassVar[str] = "packages"
    OVERRIDE_DIRNAME: ClassVar[str] = "overrides"

    def __init__(self, engine_dir: Path) -> None:
        self._engine_dir: Path = Path(engine_dir).resolve()
        self._packages_root: Path = self._engine_dir / self.PACKAGES_DIRNAME

    @property
    def engine_dir(self) -> Path:
        return self._engine_dir

    @property
    def packages_root(self) -> Path:
        return self._packages_root

    def package_dir(self, package_id: str) -> Path:
        """Ritorna la directory di base del pacchetto nello store."""
        return self._packages_root / package_id / ".github"

    def resolve(self, package_id: str, resource_type: str, name: str) -> Path | None:
        """Risolve ``(package_id, type, name)`` al path fisico se presente."""
        if resource_type not in _RESOURCE_TYPES:
            return None
        base = self.package_dir(package_id) / resource_type
        if not base.is_dir():
            return None
        for candidate in _resource_filename_candidates(resource_type, name):
            candidate_path = base / candidate
            if candidate_path.is_file():
                return candidate_path.resolve()
        return None

    def list_resources(self, package_id: str, resource_type: str) -> list[str]:
        """Elenca i nomi (senza estensione) delle risorse di un pacchetto."""
        if resource_type not in _RESOURCE_TYPES:
            return []
        base = self.package_dir(package_id) / resource_type
        if not base.is_dir():
            return []
        names: set[str] = set()
        if resource_type == "agents":
            for child in base.iterdir():
                if child.is_file() and child.name.endswith(".agent.md"):
                    names.add(child.name[: -len(".agent.md")])
                elif child.is_file() and child.name.endswith(".md"):
                    names.add(child.name[: -len(".md")])
        elif resource_type == "prompts":
            for child in base.iterdir():
                if child.is_file() and child.name.endswith(".prompt.md"):
                    names.add(child.name[: -len(".prompt.md")])
        elif resource_type == "instructions":
            for child in base.iterdir():
                if child.is_file() and child.name.endswith(".instructions.md"):
                    names.add(child.name[: -len(".instructions.md")])
        elif resource_type == "skills":
            for child in base.iterdir():
                if child.is_file() and child.name.endswith(".skill.md"):
                    names.add(child.name[: -len(".skill.md")])
                elif child.is_dir() and (child / "SKILL.md").is_file():
                    names.add(child.name)
        return sorted(names)

    def verify_integrity(self, package_id: str) -> dict[str, Any]:
        """Verifica integrità SHA-256 dei file del pacchetto.

        Confronta l'hash effettivo dei file sul filesystem con quello
        registrato nel ``package-manifest.json`` del pacchetto (se presente).
        Ritorna ``{"package": ..., "ok": bool, "mismatches": [...]}``.
        """
        manifest_path = self.package_dir(package_id) / ".." / "package-manifest.json"
        manifest_path = manifest_path.resolve()
        if not manifest_path.is_file():
            return {"package": package_id, "ok": False, "error": "manifest not found"}
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return {"package": package_id, "ok": False, "error": str(exc)}
        files_metadata = manifest.get("files_metadata") or []
        mismatches: list[dict[str, Any]] = []
        pkg_root = self.package_dir(package_id).parent
        for entry in files_metadata:
            rel = entry.get("path") if isinstance(entry, Mapping) else None
            expected = entry.get("sha256") if isinstance(entry, Mapping) else None
            if not rel or not expected:
                continue
            target = pkg_root / rel
            if not target.is_file():
                mismatches.append({"path": rel, "reason": "missing"})
                continue
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual != expected:
                mismatches.append(
                    {"path": rel, "expected": expected, "actual": actual}
                )
        return {
            "package": package_id,
            "ok": not mismatches,
            "mismatches": mismatches,
        }

    def has_workspace_override(
        self,
        workspace_github_root: Path,
        resource_type: str,
        name: str,
    ) -> bool:
        """True se esiste un override per ``(type, name)`` nel workspace."""
        if resource_type not in _RESOURCE_TYPES:
            return False
        override_dir = (
            Path(workspace_github_root).resolve()
            / self.OVERRIDE_DIRNAME
            / resource_type
        )
        if not override_dir.is_dir():
            return False
        for candidate in _resource_filename_candidates(resource_type, name):
            if (override_dir / candidate).is_file():
                return True
        return False
