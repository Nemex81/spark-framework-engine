# Modulo assets/rendering — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""Rendering testuale per AGENTS.md, AGENTS-{plugin}.md, .clinerules, project-profile."""
from __future__ import annotations

from spark.assets.templates import (
    _AGENTS_INDEX_BEGIN,
    _AGENTS_INDEX_END,
    _CLINERULES_TEMPLATE_HEADER,
    _PROJECT_PROFILE_TEMPLATE,
)


def _agents_index_section_text(
    engine_agents: list[tuple[str, str]],
    package_agents: dict[str, list[tuple[str, str]]],
) -> str:
    """Render the SCF-managed section for AGENTS.md.

    Args:
        engine_agents: list of (name, source_package) for engine-owned agents.
        package_agents: ``{package_id: [(name, summary), ...]}`` per package.

    Returns the raw markdown text (without surrounding markers).
    """
    lines: list[str] = []
    lines.append("")
    lines.append("# AGENTS — Indice agenti SPARK")
    lines.append("")
    lines.append(
        "> Generato automaticamente da `scf_bootstrap_workspace`. "
        "NON modificare manualmente il blocco fra i marker SCF."
    )
    lines.append("")
    lines.append("## Agenti engine")
    lines.append("")
    if not engine_agents:
        lines.append("- _(nessun agente engine registrato)_")
    else:
        for name, owner in sorted(engine_agents):
            lines.append(f"- `@{name}` — owner: `{owner}`")
    lines.append("")
    lines.append("## Agenti pacchetto")
    lines.append("")
    if not package_agents:
        lines.append("- _(nessun pacchetto con agenti installato)_")
    else:
        for pkg_id in sorted(package_agents):
            lines.append(f"### {pkg_id}")
            lines.append("")
            for name, summary in sorted(package_agents[pkg_id]):
                if summary:
                    lines.append(f"- `@{name}` — {summary}")
                else:
                    lines.append(f"- `@{name}`")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_agents_md(
    engine_agents: list[tuple[str, str]],
    package_agents: dict[str, list[tuple[str, str]]],
    existing_content: str | None = None,
) -> str:
    """Render AGENTS.md with safe-merge of user content outside SCF markers.

    If ``existing_content`` contains the SCF markers, only the section between
    them is replaced. Text outside the markers is preserved verbatim. If no
    markers exist, the SCF block is appended after any existing content.
    """
    section = _agents_index_section_text(engine_agents, package_agents)
    block = f"{_AGENTS_INDEX_BEGIN}\n{section}{_AGENTS_INDEX_END}\n"

    if existing_content is None or not existing_content.strip():
        return block

    begin_idx = existing_content.find(_AGENTS_INDEX_BEGIN)
    end_idx = existing_content.find(_AGENTS_INDEX_END)
    if begin_idx != -1 and end_idx != -1 and end_idx > begin_idx:
        before = existing_content[:begin_idx]
        after_start = end_idx + len(_AGENTS_INDEX_END)
        after = existing_content[after_start:]
        # Strip leading newline of after to avoid blank gap drift across writes.
        if after.startswith("\n"):
            after = after[1:]
        return f"{before}{block}{after}"

    suffix = "" if existing_content.endswith("\n") else "\n"
    return f"{existing_content}{suffix}\n{block}"


def _render_plugin_agents_md(
    package_id: str,
    agents: list[tuple[str, str]],
) -> str:
    """Render AGENTS-{plugin}.md for a single package."""
    lines: list[str] = []
    lines.append("---")
    lines.append("spark: true")
    lines.append('scf_file_role: "agents-index"')
    lines.append(f'scf_owner: "{package_id}"')
    lines.append("---")
    lines.append("")
    lines.append(f"# Agenti del pacchetto `{package_id}`")
    lines.append("")
    lines.append(
        "> Generato automaticamente da `scf_bootstrap_workspace`. "
        "Aggiornato a ogni install/update/remove del pacchetto."
    )
    lines.append("")
    if not agents:
        lines.append("- _(pacchetto installato senza agenti dichiarati)_")
    else:
        for name, summary in sorted(agents):
            if summary:
                lines.append(f"- `@{name}` — {summary}")
            else:
                lines.append(f"- `@{name}`")
    lines.append("")
    return "\n".join(lines)


def _render_clinerules(profile_summary: str | None = None) -> str:
    """Render the default .clinerules content for a fresh workspace."""
    body = _CLINERULES_TEMPLATE_HEADER
    body += "## Project profile summary\n\n"
    if profile_summary:
        body += profile_summary.strip() + "\n"
    else:
        body += "_(project-profile.md non ancora compilato)_\n"
    body += "\n## Regole operative\n\n"
    body += "- Leggi `.github/project-profile.md` prima di proporre modifiche.\n"
    body += "- Usa `.github/AGENTS.md` come indice canonico degli agenti installati.\n"
    body += "- Per operazioni git, proponi i comandi senza eseguirli direttamente.\n"
    body += "- Mantieni output testuale navigabile e screen-reader friendly.\n"
    return body


def _render_project_profile_template() -> str:
    """Return the minimal project-profile.md template for new workspaces."""
    return _PROJECT_PROFILE_TEMPLATE


def _extract_profile_summary(profile_text: str) -> str | None:
    """Extract a brief summary from project-profile.md for .clinerules.

    Picks the first non-empty paragraph after the H1. Returns None when the
    file is empty or only contains placeholders.
    """
    if not profile_text:
        return None
    parts = profile_text.split("---")
    body = parts[2] if len(parts) >= 3 and profile_text.startswith("---") else profile_text
    summary_lines: list[str] = []
    for raw in body.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(">"):
            if summary_lines:
                break
            continue
        summary_lines.append(stripped)
        if len(summary_lines) >= 5:
            break
    if not summary_lines:
        return None
    return " ".join(summary_lines)[:480]
