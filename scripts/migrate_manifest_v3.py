"""Migra package-manifest.json da schema v2.1 -> v3.0.

Regole:
- schema_version -> "3.0"
- aggiunge workspace_files (file caricati automaticamente dal client)
- aggiunge mcp_resources con agents/prompts/skills/instructions
- mantiene files, files_metadata, engine_provided_skills (fallback v2.x)
- bump version come da CLI
- preserva tutti i campi non noti

Workspace files = {copilot-instructions.md, project-profile.md,
                   instructions/*.instructions.md, AGENTS.md}.
AGENTS.md NON va in workspace_files in v3.0 (rigenerato dall'engine);
ma resta in files[] come fallback per engine v2.x.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _resource_name_from_path(p: str, kind: str) -> str | None:
    """Estrae il nome canonico (senza estensione) per una risorsa MCP."""
    name = p.rsplit("/", 1)[-1]
    if kind == "agents":
        # Agent-Foo.md o spark-foo.agent.md
        if name.endswith(".agent.md"):
            return name[: -len(".agent.md")]
        if name.endswith(".md"):
            return name[: -len(".md")]
        return None
    if kind == "skills":
        # *.skill.md oppure */SKILL.md
        if name == "SKILL.md":
            # path: .github/skills/<dirname>/SKILL.md
            parts = p.split("/")
            try:
                idx = parts.index("skills")
                return parts[idx + 1]
            except (ValueError, IndexError):
                return None
        if name.endswith(".skill.md"):
            return name[: -len(".skill.md")]
        return None
    if kind == "prompts":
        if name == "README.md":
            return None
        if name.endswith(".prompt.md"):
            return name[: -len(".prompt.md")]
        return None
    if kind == "instructions":
        if name.endswith(".instructions.md"):
            return name[: -len(".instructions.md")]
        return None
    return None


def _classify_file(p: str) -> tuple[str, str | None]:
    """Restituisce (bucket, name) dove bucket in
    {workspace, agents, skills, prompts, instructions, internal}."""
    if p == ".github/copilot-instructions.md":
        return ("workspace", None)
    if p == ".github/project-profile.md":
        return ("workspace", None)
    if p == ".github/AGENTS.md":
        # NON in workspace_files: rigenerato dall'engine in v3
        return ("internal", None)
    if p.startswith(".github/instructions/"):
        # tutte le instruction di pacchetto sono caricate via glob applyTo
        # quindi vanno in workspace_files
        name = _resource_name_from_path(p, "instructions")
        return ("workspace", name)
    if p.startswith(".github/agents/"):
        name = _resource_name_from_path(p, "agents")
        return ("agents", name)
    if p.startswith(".github/skills/"):
        name = _resource_name_from_path(p, "skills")
        return ("skills", name)
    if p.startswith(".github/prompts/"):
        name = _resource_name_from_path(p, "prompts")
        return ("prompts", name)
    if p.startswith(".github/changelogs/"):
        return ("internal", None)
    return ("internal", None)


def derive_v3_fields(manifest: dict) -> dict:
    files = manifest.get("files", [])
    workspace_files: list[str] = []
    seen_ws: set[str] = set()
    agents: list[str] = []
    skills: list[str] = []
    prompts: list[str] = []
    instructions: list[str] = []

    for fp in files:
        bucket, name = _classify_file(fp)
        if bucket == "workspace":
            if fp not in seen_ws:
                workspace_files.append(fp)
                seen_ws.add(fp)
            if name and name not in instructions and fp.startswith(
                ".github/instructions/"
            ):
                instructions.append(name)
        elif bucket == "agents" and name and name not in agents:
            agents.append(name)
        elif bucket == "skills" and name and name not in skills:
            skills.append(name)
        elif bucket == "prompts" and name and name not in prompts:
            prompts.append(name)

    # Mantieni l'ordine originale ma deduplicato
    return {
        "workspace_files": workspace_files,
        "mcp_resources": {
            "agents": sorted(agents),
            "prompts": sorted(prompts),
            "skills": sorted(skills),
            "instructions": sorted(instructions),
        },
    }


def migrate(manifest_path: Path, new_version: str) -> None:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    if data.get("schema_version") == "3.0":
        print(f"  SKIP: {manifest_path} già a schema 3.0")
        return

    derived = derive_v3_fields(data)

    # Costruisce nuovo dict preservando ordine logico
    new_data: dict = {}
    new_data["schema_version"] = "3.0"
    for key in (
        "package",
        "version",
        "display_name",
        "description",
        "author",
        "min_engine_version",
        "dependencies",
        "conflicts",
        "file_ownership_policy",
        "changelog_path",
    ):
        if key in data:
            new_data[key] = data[key]

    new_data["version"] = new_version
    new_data["workspace_files"] = derived["workspace_files"]
    new_data["mcp_resources"] = derived["mcp_resources"]

    # Mantieni campi v2.1 come fallback
    for key in ("files", "files_metadata", "engine_provided_skills"):
        if key in data:
            new_data[key] = data[key]

    # Eventuali altri campi non gestiti
    for key, value in data.items():
        if key not in new_data:
            new_data[key] = value

    manifest_path.write_text(
        json.dumps(new_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"  OK: {manifest_path} -> v3.0, version={new_version}")


def main() -> int:
    targets = [
        (Path(sys.argv[1]) if len(sys.argv) > 1 else None),
    ]
    if targets[0] is None:
        print("Usage: migrate_manifest_v3.py <manifest.json> <new_version>")
        return 2
    new_version = sys.argv[2]
    migrate(targets[0], new_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
