"""SCF section-merge helpers — estratti da spark-framework-engine.py durante Fase 0.

Gestione blocchi marcati ``<!-- SCF:BEGIN:... -->`` / ``<!-- SCF:END:... -->`` nei
file condivisi a strategia ``merge_sections``, con compat legacy SCF:SECTION.

NOTA Fase 0: ``_strip_package_section`` qui replicato byte-for-byte; la sua
collocazione ottimale è in ``spark/manifest/`` (anomalia segnalata).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from spark.core.utils import parse_markdown_frontmatter
from spark.merge.validators import _normalize_merge_text

_log: logging.Logger = logging.getLogger("spark-framework-engine")


def _section_markers_for_package(package_id: str) -> tuple[str, str]:
    """Return begin/end markers for one package-owned shared section."""
    return (
        f"<!-- SCF:SECTION:{package_id}:BEGIN -->",
        f"<!-- SCF:SECTION:{package_id}:END -->",
    )


_SCF_SECTION_HEADER: str = (
    "<!-- SCF:HEADER — generato da SPARK Framework Engine -->\n"
    "<!-- NON modificare i marker SCF. Il contenuto tra i marker è gestito dal sistema. -->\n"
    "<!-- Il testo fuori dai marker è tuo: SPARK non lo tocca mai in nessuna modalità. -->\n\n"
    "# Copilot Instructions — Workspace\n\n"
    "<!-- Le tue istruzioni custom personali vanno QUI, sopra i blocchi SCF -->\n"
)


def _scf_section_markers(package_id: str, version: str) -> tuple[str, str]:
    """Return canonical SCF:BEGIN/END markers for one package section."""
    return (
        f"<!-- SCF:BEGIN:{package_id}@{version} -->",
        f"<!-- SCF:END:{package_id} -->",
    )


def _scf_split_frontmatter(text: str) -> tuple[str, str]:
    """Split a markdown document into front matter and body using raw text boundaries."""
    normalized_text = _normalize_merge_text(text)
    if not normalized_text.startswith("---\n"):
        return "", normalized_text

    closing_match = re.search(r"^---\s*$", normalized_text[4:], re.MULTILINE)
    if closing_match is None:
        return "", normalized_text

    closing_start = 4 + closing_match.start()
    closing_end = 4 + closing_match.end()
    frontmatter = normalized_text[:closing_end]
    body = normalized_text[closing_end:]
    if body.startswith("\n"):
        body = body[1:]
    return frontmatter, body


def _scf_extract_merge_priority(section_text: str) -> int:
    """Extract scf_merge_priority from a section body, defaulting high when absent."""
    metadata = parse_markdown_frontmatter(section_text)
    raw_priority = metadata.get("scf_merge_priority", 999)
    try:
        return int(raw_priority)
    except (TypeError, ValueError):
        return 999


def _scf_iter_section_blocks(text: str) -> list[dict[str, Any]]:
    """Return canonical and legacy SCF section blocks in source order."""
    normalized_text = _normalize_merge_text(text)
    canonical_pattern = re.compile(
        r"<!-- SCF:BEGIN:(?P<package>[^@\s>]+)@(?P<version>[^\s>]+) -->\n?"
        r"(?P<body>.*?)"
        r"<!-- SCF:END:(?P=package) -->\n?",
        re.DOTALL,
    )
    legacy_pattern = re.compile(
        r"<!-- SCF:SECTION:(?P<package>[^:\s>]+):BEGIN -->\n?"
        r"(?P<body>.*?)"
        r"<!-- SCF:SECTION:(?P=package):END -->\n?",
        re.DOTALL,
    )

    sections: list[dict[str, Any]] = []
    for match in canonical_pattern.finditer(normalized_text):
        body = match.group("body")
        sections.append(
            {
                "package": match.group("package"),
                "version": match.group("version"),
                "body": body,
                "start": match.start(),
                "end": match.end(),
                "priority": _scf_extract_merge_priority(body),
                "marker_style": "canonical",
            }
        )

    for match in legacy_pattern.finditer(normalized_text):
        if any(match.start() >= section["start"] and match.end() <= section["end"] for section in sections):
            continue
        body = match.group("body")
        sections.append(
            {
                "package": match.group("package"),
                "version": "",
                "body": body,
                "start": match.start(),
                "end": match.end(),
                "priority": _scf_extract_merge_priority(body),
                "marker_style": "legacy",
            }
        )

    return sorted(sections, key=lambda item: int(item["start"]))


def _scf_render_section(package_id: str, version: str, source_content: str) -> str:
    """Render one canonical SCF section block."""
    begin_marker, end_marker = _scf_section_markers(package_id, version)
    normalized_content = _normalize_merge_text(source_content).rstrip("\n")
    return f"{begin_marker}\n{normalized_content}\n{end_marker}\n"


def _classify_copilot_instructions_format(content: str) -> str:
    """Classify the current copilot-instructions.md shape for migration decisions."""
    normalized_content = _normalize_merge_text(content)
    if not normalized_content.strip():
        return "plain"

    has_sections = bool(_scf_iter_section_blocks(normalized_content))
    has_header = normalized_content.startswith(_SCF_SECTION_HEADER)
    if has_sections and has_header:
        return "scf_markers"
    if has_sections:
        return "scf_markers_partial"
    return "plain"


def _prepare_copilot_instructions_migration(existing_text: str) -> str:
    """Normalize a legacy copilot-instructions.md into the marker-ready workspace shape."""
    normalized_existing = _normalize_merge_text(existing_text).strip("\n")
    current_format = _classify_copilot_instructions_format(normalized_existing)
    if current_format == "scf_markers":
        return normalized_existing.rstrip("\n") + "\n"

    if not normalized_existing:
        return _SCF_SECTION_HEADER.rstrip("\n") + "\n"

    return f"{_SCF_SECTION_HEADER}\n{normalized_existing}\n"


def _scf_section_merge_text(
    source_content: str,
    existing_text: str,
    strategy: str,
    package_id: str,
    version: str,
) -> str:
    """Return the final content for a section-aware file update from in-memory text."""
    normalized_source = _normalize_merge_text(source_content)
    normalized_existing = _normalize_merge_text(existing_text)

    if strategy == "replace":
        existing_frontmatter, _ = _scf_split_frontmatter(normalized_existing)
        _, source_body = _scf_split_frontmatter(normalized_source)
        if existing_frontmatter:
            body = source_body.rstrip("\n")
            if body:
                return f"{existing_frontmatter}\n{body}\n"
            return f"{existing_frontmatter}\n"
        return normalized_source

    if strategy == "user_protected":
        return normalized_existing

    if strategy != "merge_sections":
        raise ValueError(f"Unsupported section merge strategy '{strategy}'.")

    rendered_section = _scf_render_section(package_id, version, normalized_source)
    sections = _scf_iter_section_blocks(normalized_existing)
    source_priority = _scf_extract_merge_priority(normalized_source)

    existing_section = next(
        (section for section in sections if str(section["package"]) == package_id),
        None,
    )
    if existing_section is not None:
        return (
            f"{normalized_existing[: existing_section['start']]}"
            f"{rendered_section}"
            f"{normalized_existing[existing_section['end'] :]}"
        )

    if not normalized_existing.strip():
        return f"{_SCF_SECTION_HEADER}\n{rendered_section}".rstrip("\n") + "\n"

    if not sections:
        stripped_existing = normalized_existing.rstrip("\n")
        return f"{stripped_existing}\n\n{rendered_section}"

    insert_before = next(
        (section for section in sections if source_priority < int(section["priority"])),
        None,
    )
    if insert_before is not None:
        return (
            f"{normalized_existing[: insert_before['start']]}"
            f"{rendered_section}"
            f"{normalized_existing[insert_before['start'] :]}"
        )

    last_section = sections[-1]
    insertion_point = int(last_section["end"])
    trailing = normalized_existing[insertion_point:]
    separator = "" if trailing.startswith("\n") or not trailing else "\n"
    return (
        f"{normalized_existing[:insertion_point]}"
        f"{separator}{rendered_section}"
        f"{trailing}"
    )


def _scf_strip_section(content: str, package_id: str) -> str:
    """Remove a canonical or legacy SCF section for one package, preserving all else."""
    normalized_content = _normalize_merge_text(content)
    sections = _scf_iter_section_blocks(normalized_content)
    for section in sections:
        if str(section["package"]) != package_id:
            continue
        stripped = (
            f"{normalized_content[: section['start']]}"
            f"{normalized_content[section['end'] :]}"
        )
        stripped = re.sub(r"\n{3,}", "\n\n", stripped)
        return stripped.lstrip("\n")
    return normalized_content


def _scf_section_merge(
    source_content: str,
    target_path: Path,
    strategy: str,
    package_id: str,
    version: str,
) -> str:
    """Return the final content for a section-aware file update without writing to disk."""
    existing_text = target_path.read_text(encoding="utf-8") if target_path.is_file() else ""
    merged_text = _scf_section_merge_text(
        source_content,
        existing_text,
        strategy,
        package_id,
        version,
    )
    if strategy == "user_protected":
        normalized_existing = _normalize_merge_text(existing_text)
        normalized_source = _normalize_merge_text(source_content)
        if normalized_existing and normalized_existing != normalized_source:
            _log.info(
                "Section merge skipped for user_protected file %s (%s)",
                target_path,
                package_id,
            )
    return merged_text


def _strip_package_section(text: str, package_id: str) -> str:
    """Remove one package-owned marked section from a shared file, when present."""
    return _scf_strip_section(text, package_id)
