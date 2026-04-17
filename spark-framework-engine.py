"""SPARK Framework Engine: expose the SPARK Code Framework as MCP Resources and Tools.

Transport: stdio only.
Logging: stderr or file — never stdout (would corrupt the JSON-RPC stream).
Python: 3.10+ required (MCP SDK baseline).

Domain boundary:
- Slash commands (/scf-*): handled by VS Code natively from .github/prompts/
- Tools and Resources: handled by this server — dynamic, on-demand, Agent mode only
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
_log: logging.Logger = logging.getLogger("spark-framework-engine")

# ---------------------------------------------------------------------------
# Engine version
# ---------------------------------------------------------------------------

ENGINE_VERSION: str = "2.1.2"


# ---------------------------------------------------------------------------
# Changelogs directory
# ---------------------------------------------------------------------------
_CHANGELOGS_SUBDIR: str = "changelogs"
_SNAPSHOTS_SUBDIR: str = "runtime/snapshots"
_MERGE_SESSIONS_SUBDIR: str = "runtime/merge-sessions"

# ---------------------------------------------------------------------------
# FastMCP import guard
# ---------------------------------------------------------------------------
try:
    from mcp.server.fastmcp import FastMCP
except ImportError as _import_exc:
    _log.critical(
        "mcp library not installed. Run: pip install mcp  (Python 3.10+ required)"
    )
    raise SystemExit(1) from _import_exc

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


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


class MergeEngine:
    """Compute a normalized 3-way merge without filesystem or MCP dependencies."""

    OURS_MARKER: str = "<<<<<<< YOURS"
    SEPARATOR_MARKER: str = "======="
    THEIRS_MARKER: str = ">>>>>>> OFFICIAL"

    def diff3_merge(self, base: str, ours: str, theirs: str) -> MergeResult:
        """Merge three text versions using explicit clean-path rules first."""
        normalized_base = self._normalize_newlines(base)
        normalized_ours = self._normalize_newlines(ours)
        normalized_theirs = self._normalize_newlines(theirs)

        if normalized_base == normalized_ours == normalized_theirs:
            return MergeResult(
                status=MERGE_STATUS_IDENTICAL,
                merged_text=normalized_base,
                sections=(normalized_base,),
            )

        if normalized_ours == normalized_theirs:
            return MergeResult(
                status=MERGE_STATUS_CLEAN,
                merged_text=normalized_ours,
                sections=(normalized_ours,),
            )

        if normalized_base == normalized_ours:
            return MergeResult(
                status=MERGE_STATUS_CLEAN,
                merged_text=normalized_theirs,
                sections=(normalized_theirs,),
            )

        if normalized_base == normalized_theirs:
            return MergeResult(
                status=MERGE_STATUS_CLEAN,
                merged_text=normalized_ours,
                sections=(normalized_ours,),
            )

        return self._build_conflict_result(
            base=normalized_base,
            ours=normalized_ours,
            theirs=normalized_theirs,
        )

    def render_with_markers(self, result: MergeResult) -> str:
        """Render a merge result, adding conflict markers when needed."""
        if not result.conflicts:
            return result.merged_text

        rendered_sections: list[str] = []
        for section in result.sections:
            if isinstance(section, MergeConflict):
                rendered_sections.append(self._render_conflict(section))
            else:
                rendered_sections.append(section)
        return "".join(rendered_sections)

    def has_conflict_markers(self, text: str) -> bool:
        """Return True when a text already contains merge markers."""
        normalized_text = self._normalize_newlines(text)
        marker_pattern = re.compile(
            rf"(?m)^({re.escape(self.OURS_MARKER)}|"
            rf"{re.escape(self.SEPARATOR_MARKER)}|{re.escape(self.THEIRS_MARKER)})$"
        )
        return bool(marker_pattern.search(normalized_text))

    def _build_conflict_result(self, base: str, ours: str, theirs: str) -> MergeResult:
        ours_lines = self._split_lines(ours)
        theirs_lines = self._split_lines(theirs)
        base_lines = self._split_lines(base)

        prefix_len = self._shared_prefix_len(ours_lines, theirs_lines)
        suffix_len = self._shared_suffix_len(ours_lines, theirs_lines, prefix_len)
        ours_end = len(ours_lines) - suffix_len if suffix_len else len(ours_lines)
        theirs_end = len(theirs_lines) - suffix_len if suffix_len else len(theirs_lines)

        prefix_text = "".join(ours_lines[:prefix_len])
        suffix_text = "".join(ours_lines[len(ours_lines) - suffix_len :]) if suffix_len else ""

        base_start = min(prefix_len, len(base_lines))
        base_end = len(base_lines) - suffix_len if suffix_len else len(base_lines)
        if base_end < base_start:
            base_end = base_start

        conflict = MergeConflict(
            start_line=base_start + 1,
            end_line=max(base_start + 1, base_end),
            base_text="".join(base_lines[base_start:base_end]),
            ours_text="".join(ours_lines[prefix_len:ours_end]),
            theirs_text="".join(theirs_lines[prefix_len:theirs_end]),
        )
        return MergeResult(
            status=MERGE_STATUS_CONFLICT,
            merged_text="",
            conflicts=(conflict,),
            sections=(prefix_text, conflict, suffix_text),
        )

    def _render_conflict(self, conflict: MergeConflict) -> str:
        ours_text = self._ensure_conflict_body_newline(conflict.ours_text)
        theirs_text = self._ensure_conflict_body_newline(conflict.theirs_text)
        return (
            f"{self.OURS_MARKER}\n"
            f"{ours_text}"
            f"{self.SEPARATOR_MARKER}\n"
            f"{theirs_text}"
            f"{self.THEIRS_MARKER}\n"
        )

    @staticmethod
    def _ensure_conflict_body_newline(text: str) -> str:
        if not text or text.endswith("\n"):
            return text
        return f"{text}\n"

    @staticmethod
    def _normalize_newlines(text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n")

    @staticmethod
    def _split_lines(text: str) -> list[str]:
        return text.splitlines(keepends=True)

    @staticmethod
    def _shared_prefix_len(left: list[str], right: list[str]) -> int:
        limit = min(len(left), len(right))
        index = 0
        while index < limit and left[index] == right[index]:
            index += 1
        return index

    @staticmethod
    def _shared_suffix_len(left: list[str], right: list[str], prefix_len: int) -> int:
        max_suffix = min(len(left), len(right)) - prefix_len
        index = 0
        while index < max_suffix and left[-(index + 1)] == right[-(index + 1)]:
            index += 1
        return index


def _utc_now() -> datetime:
    """Return the current UTC timestamp as an aware datetime."""
    return datetime.now(timezone.utc)


def _format_utc_timestamp(value: datetime) -> str:
    """Serialize an aware UTC datetime to the engine timestamp format."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc_timestamp(value: str) -> datetime | None:
    """Parse a stored UTC timestamp, returning None for invalid values."""
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _sha256_text(text: str) -> str:
    """Return the SHA-256 of a UTF-8 text payload."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# WorkspaceLocator
# ---------------------------------------------------------------------------


class WorkspaceLocator:
    """Resolve the active workspace using env, local config and SCF markers."""

    _SCF_MARKER_FILES: tuple[str, ...] = (
        "project-profile.md",
        "copilot-instructions.md",
        "AGENTS.md",
        ".scf-manifest.json",
    )
    _SCF_MARKER_DIRS: tuple[str, ...] = (
        "agents",
        "instructions",
        "prompts",
        "skills",
    )

    def _is_user_home(self, candidate: Path) -> bool:
        try:
            return candidate == Path.home().resolve()
        except RuntimeError:
            return False

    def _has_local_workspace_config(self, candidate: Path) -> bool:
        if any(path.is_file() for path in candidate.glob("*.code-workspace")):
            return True

        vscode_dir = candidate / ".vscode"
        return any(
            (vscode_dir / file_name).is_file()
            for file_name in ("settings.json", "mcp.json")
        )

    def _has_scf_markers(self, candidate: Path) -> bool:
        github_root = candidate / ".github"
        if not github_root.is_dir():
            return False

        if any((github_root / file_name).is_file() for file_name in self._SCF_MARKER_FILES):
            return True

        return any((github_root / dir_name).is_dir() for dir_name in self._SCF_MARKER_DIRS)

    def _discover_from_cwd(self, cwd: Path) -> Path | None:
        for candidate in (cwd, *cwd.parents):
            if self._is_user_home(candidate):
                continue

            if self._has_local_workspace_config(candidate):
                _log.info("Workspace resolved via local workspace config: %s", candidate)
                return candidate

            if self._has_scf_markers(candidate):
                _log.info("Workspace resolved via SCF .github discovery: %s", candidate)
                return candidate

        return None

    def resolve(self) -> WorkspaceContext:
        workspace_root_str: str | None = os.environ.get("WORKSPACE_FOLDER")
        workspace_root: Path | None = None

        if workspace_root_str:
            candidate = Path(workspace_root_str).expanduser().resolve()
            if not candidate.is_dir():
                _log.warning(
                    "Ignoring WORKSPACE_FOLDER because it is not a directory: %s",
                    candidate,
                )
            elif self._is_user_home(candidate) and not (
                self._has_local_workspace_config(candidate)
                or self._has_scf_markers(candidate)
            ):
                _log.warning(
                    "Ignoring WORKSPACE_FOLDER because it points to the user home without"
                    " local workspace markers: %s",
                    candidate,
                )
            else:
                workspace_root = candidate
                _log.info("Workspace resolved via WORKSPACE_FOLDER: %s", workspace_root)

        if workspace_root is None:
            cwd = Path.cwd().resolve()
            workspace_root = self._discover_from_cwd(cwd)
            if workspace_root is None:
                workspace_root = cwd
                _log.warning(
                    "WORKSPACE_FOLDER env var not set or invalid and no local workspace"
                    " markers were found."
                )
                _log.warning("Falling back to cwd: %s", workspace_root)
                _log.warning(
                    "This is likely wrong. Run spark-init.py in your project folder"
                )
                _log.warning(
                    "or open the project via File > Open Workspace from File."
                )

        if not workspace_root.is_dir():
            raise RuntimeError(
                f"Workspace root does not exist or is not a directory: {workspace_root}"
            )

        github_root = workspace_root / ".github"
        engine_root = workspace_root / "spark-framework-engine"

        if not github_root.is_dir():
            _log.warning(".github/ not found in workspace: %s", github_root)

        return WorkspaceContext(
            workspace_root=workspace_root,
            github_root=github_root,
            engine_root=engine_root,
        )


# ---------------------------------------------------------------------------
# Standalone parsers
# ---------------------------------------------------------------------------

# Pre-compiled patterns for YAML list detection in frontmatter.
_FM_INLINE_LIST_RE: re.Pattern[str] = re.compile(r"^\[(.+)\]$")
_FM_BLOCK_ITEM_RE: re.Pattern[str] = re.compile(r"^(\s+)-\s+(.*)")
_SEMVER_RE: re.Pattern[str] = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


def parse_markdown_frontmatter(content: str) -> dict[str, Any]:
    """Parse optional YAML-style frontmatter from markdown content.

    Supports scalar values (string, boolean, integer), inline lists
    ``key: [a, b, c]`` and block lists (key followed by ``  - value`` lines).
    """
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    result: dict[str, Any] = {}
    current_list_key: str | None = None
    for raw_line in parts[1].strip().splitlines():
        # Block list item (indented dash) — checked before stripping whitespace.
        block_m = _FM_BLOCK_ITEM_RE.match(raw_line)
        if block_m and current_list_key is not None:
            item = block_m.group(2).strip().strip('"').strip("'")
            if item:
                result[current_list_key].append(item)
            continue
        # Any non-item line closes the open block list.
        current_list_key = None
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, raw_value = line.partition(":")
        key = key.strip()
        value_str = raw_value.strip()
        # Inline list: key: [a, b]
        inline_m = _FM_INLINE_LIST_RE.match(value_str)
        if inline_m:
            items = [s.strip().strip('"').strip("'") for s in inline_m.group(1).split(",")]
            result[key] = [i for i in items if i]
            continue
        # Block list start: key: <empty>
        if not value_str:
            current_list_key = key
            result[key] = []
            continue
        # Scalar value.
        value_str = value_str.strip('"').strip("'")
        if value_str.lower() in ("true", "yes"):
            result[key] = True
        elif value_str.lower() in ("false", "no"):
            result[key] = False
        elif value_str.isdigit():
            result[key] = int(value_str)
        else:
            result[key] = value_str
    return result


def _extract_version_from_changelog(changelog_path: Path) -> str:
    """Extract the latest version string from a changelog markdown file."""
    if not changelog_path.is_file():
        _log.warning("Changelog not found: %s", changelog_path)
        return "unknown"
    try:
        text = changelog_path.read_text(encoding="utf-8")
    except OSError as exc:
        _log.error("Cannot read changelog %s: %s", changelog_path, exc)
        return "unknown"
    pattern = re.compile(
        r"^\s*#{1,3}\s+\[?(v?[\d]+\.[\d]+\.[\d]+[^\]\s]*)\]?",
        re.MULTILINE,
    )
    match = pattern.search(text)
    return match.group(1) if match else "unknown"


def _normalize_string_list(value: Any) -> list[str]:
    """Return a normalized list of non-empty strings."""
    if not isinstance(value, list):
        return []
    items = [str(item).strip() for item in value]
    return [item for item in items if item]


def _parse_semver_triplet(version: str) -> tuple[int, int, int] | None:
    """Parse the numeric core of a semantic version string."""
    match = _SEMVER_RE.match(version.strip())
    if match is None:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return (major, minor, patch)


def _is_engine_version_compatible(current_version: str, minimum_version: str) -> bool:
    """Return True when the current engine version satisfies the minimum version."""
    if not minimum_version.strip():
        return True
    current = _parse_semver_triplet(current_version)
    minimum = _parse_semver_triplet(minimum_version)
    if current is None or minimum is None:
        return False
    return current >= minimum


def _resolve_dependency_update_order(
    target_ids: list[str],
    package_dependencies: dict[str, list[str]],
) -> dict[str, Any]:
    """Build a deterministic dependency-aware update order for selected packages."""
    unique_targets = sorted({pkg_id for pkg_id in target_ids if pkg_id})
    dependency_graph: dict[str, set[str]] = {pkg_id: set() for pkg_id in unique_targets}
    reverse_graph: dict[str, set[str]] = {pkg_id: set() for pkg_id in unique_targets}
    for pkg_id in unique_targets:
        for dependency in package_dependencies.get(pkg_id, []):
            if dependency in dependency_graph:
                dependency_graph[pkg_id].add(dependency)
                reverse_graph[dependency].add(pkg_id)

    ready = sorted([pkg_id for pkg_id, deps in dependency_graph.items() if not deps])
    ordered: list[str] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for dependent in sorted(reverse_graph[current]):
            dependency_graph[dependent].discard(current)
            if not dependency_graph[dependent] and dependent not in ordered and dependent not in ready:
                ready.append(dependent)
        ready.sort()

    cycles = sorted([pkg_id for pkg_id, deps in dependency_graph.items() if deps])
    return {
        "order": ordered,
        "cycles": cycles,
    }


_SUPPORTED_CONFLICT_MODES: set[str] = {"abort", "replace", "manual", "auto", "assisted"}
_MARKDOWN_HEADING_RE: re.Pattern[str] = re.compile(r"(?m)^(#{1,2})\s+(.+?)\s*$")


def _normalize_merge_text(text: str) -> str:
    """Normalize line endings for merge-related comparisons."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _extract_frontmatter_block(text: str) -> str | None:
    """Return the raw frontmatter block when present and closed correctly."""
    normalized = _normalize_merge_text(text)
    if not normalized.startswith("---\n") and normalized != "---":
        return None

    lines = normalized.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "".join(lines[: index + 1])
    return None


def _extract_markdown_headings(text: str) -> list[str]:
    """Extract normalized H1/H2 headings from markdown text."""
    normalized = _normalize_merge_text(text)
    return [match.group(2).strip() for match in _MARKDOWN_HEADING_RE.finditer(normalized)]


def validate_structural(merged_text: str, base_text: str) -> tuple[bool, str, str]:
    """Validate conflict markers, frontmatter delimiters and basic markdown structure."""
    normalized_merged = _normalize_merge_text(merged_text)
    normalized_base = _normalize_merge_text(base_text)
    merge_engine = MergeEngine()

    if merge_engine.has_conflict_markers(normalized_merged):
        return (False, "conflict_markers_present", "")

    base_frontmatter = _extract_frontmatter_block(normalized_base)
    merged_frontmatter = _extract_frontmatter_block(normalized_merged)
    if base_frontmatter is not None and merged_frontmatter is None:
        return (False, "frontmatter_missing_or_unbalanced", "")
    if normalized_merged.startswith("---") and merged_frontmatter is None:
        return (False, "frontmatter_missing_or_unbalanced", "")

    if _extract_markdown_headings(normalized_base) and not _extract_markdown_headings(normalized_merged):
        return (False, "base_headings_removed", "")

    return (True, "", "")


def validate_completeness(merged_text: str, ours_text: str) -> tuple[bool, str, str]:
    """Validate that H1/H2 headings from OURS survive in the merged content."""
    ours_headings = _extract_markdown_headings(ours_text)
    if not ours_headings:
        return (True, "no_h1_h2_headings_in_ours", "")

    merged_headings = {heading.casefold() for heading in _extract_markdown_headings(merged_text)}
    missing = [heading for heading in ours_headings if heading.casefold() not in merged_headings]
    if missing:
        return (False, f"missing_headings: {', '.join(missing)}", "")
    return (True, "", "")


def validate_tool_coherence(merged_text: str, ours_text: str) -> tuple[bool, str, str]:
    """Validate that tools declared in OURS frontmatter remain present after merge."""
    ours_tools = _normalize_string_list(parse_markdown_frontmatter(ours_text).get("tools", []))
    if not ours_tools:
        return (True, "tools_block_not_applicable", "")

    merged_tools = _normalize_string_list(parse_markdown_frontmatter(merged_text).get("tools", []))
    if not merged_tools:
        return (False, "merged_tools_block_missing", "")

    missing = [tool for tool in ours_tools if tool not in merged_tools]
    if missing:
        return (False, f"missing_tools: {', '.join(missing)}", "")

    duplicates = sorted({tool for tool in merged_tools if merged_tools.count(tool) > 1})
    if duplicates:
        return (True, "", f"duplicate_tools: {', '.join(duplicates)}")
    return (True, "", "")


def run_post_merge_validators(
    merged_text: str,
    base_text: str,
    ours_text: str,
    file_rel: str,
) -> dict[str, Any]:
    """Run all post-merge validators and return a structured result."""
    results: list[dict[str, Any]] = []

    structural_ok, structural_msg, structural_warning = validate_structural(merged_text, base_text)
    results.append(
        {
            "check": "structural",
            "passed": structural_ok,
            "message": structural_msg,
            "warning": structural_warning,
        }
    )

    completeness_ok, completeness_msg, completeness_warning = validate_completeness(merged_text, ours_text)
    results.append(
        {
            "check": "completeness",
            "passed": completeness_ok,
            "message": completeness_msg,
            "warning": completeness_warning,
        }
    )

    if file_rel.endswith(".agent.md"):
        tool_ok, tool_msg, tool_warning = validate_tool_coherence(merged_text, ours_text)
        results.append(
            {
                "check": "tool_coherence",
                "passed": tool_ok,
                "message": tool_msg,
                "warning": tool_warning,
            }
        )

    warnings = [item["warning"] for item in results if item.get("warning")]
    return {
        "passed": all(bool(item.get("passed")) for item in results),
        "results": results,
        "warnings": warnings,
    }


def _resolve_disjoint_line_additions(base_text: str, ours_text: str, theirs_text: str) -> str | None:
    """Combine simple prefix/suffix additions around the unchanged BASE text."""
    normalized_base = _normalize_merge_text(base_text)
    normalized_ours = _normalize_merge_text(ours_text)
    normalized_theirs = _normalize_merge_text(theirs_text)

    if not normalized_base:
        return None

    ours_index = normalized_ours.find(normalized_base)
    theirs_index = normalized_theirs.find(normalized_base)
    if ours_index < 0 or theirs_index < 0:
        return None

    ours_prefix = normalized_ours[:ours_index]
    ours_suffix = normalized_ours[ours_index + len(normalized_base) :]
    theirs_prefix = normalized_theirs[:theirs_index]
    theirs_suffix = normalized_theirs[theirs_index + len(normalized_base) :]

    if ours_prefix and theirs_prefix and ours_prefix != theirs_prefix:
        return None
    if ours_suffix and theirs_suffix and ours_suffix != theirs_suffix:
        return None
    if ours_prefix == theirs_prefix and ours_suffix == theirs_suffix:
        return None

    merged_prefix = ours_prefix or theirs_prefix
    merged_suffix = ours_suffix or theirs_suffix
    return f"{merged_prefix}{normalized_base}{merged_suffix}"


def _section_markers_for_package(package_id: str) -> tuple[str, str]:
    """Return begin/end markers for one package-owned shared section."""
    return (
        f"<!-- SCF:SECTION:{package_id}:BEGIN -->",
        f"<!-- SCF:SECTION:{package_id}:END -->",
    )


def _strip_package_section(text: str, package_id: str) -> str:
    """Remove one package-owned marked section from a shared file, when present."""
    normalized_text = _normalize_merge_text(text)
    begin_marker, end_marker = _section_markers_for_package(package_id)
    begin_index = normalized_text.find(begin_marker)
    if begin_index < 0:
        return normalized_text

    end_index = normalized_text.find(end_marker, begin_index + len(begin_marker))
    if end_index < 0:
        return normalized_text

    section_end = end_index + len(end_marker)
    if section_end < len(normalized_text) and normalized_text[section_end] == "\n":
        section_end += 1

    stripped = f"{normalized_text[:begin_index]}{normalized_text[section_end:]}"
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped.lstrip("\n")


# ---------------------------------------------------------------------------
# FrameworkInventory
# ---------------------------------------------------------------------------


class FrameworkInventory:
    """Discover framework files under .github/ and scripts/ dynamically."""

    def __init__(self, context: WorkspaceContext) -> None:
        self._ctx = context

    def _build_framework_file(self, path: Path, category: str) -> FrameworkFile:
        name = path.stem
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            _log.warning("Cannot read %s: %s", path, exc)
            content = ""
        metadata = parse_markdown_frontmatter(content)
        summary = ""
        for raw in content.splitlines():
            stripped = raw.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                summary = stripped[:160]
                break
        return FrameworkFile(
            name=name, path=path, category=category, summary=summary, metadata=metadata
        )

    def _list_by_pattern(self, directory: Path, glob_pattern: str, category: str) -> list[FrameworkFile]:
        if not directory.is_dir():
            return []
        return sorted(
            [self._build_framework_file(p, category) for p in directory.glob(glob_pattern)],
            key=lambda ff: ff.name,
        )

    def list_agents(self) -> list[FrameworkFile]:
        return self._list_by_pattern(self._ctx.github_root / "agents", "*.md", "agent")

    def list_skills(self) -> list[FrameworkFile]:
        """Discover SCF skills in both supported formats.

        Format 1 (legacy): .github/skills/*.skill.md
        Format 2 (standard): .github/skills/skill-name/SKILL.md

        On name collisions, the legacy flat format takes precedence.
        """
        skills_root = self._ctx.github_root / "skills"

        # Pass 1: legacy flat format.
        flat = self._list_by_pattern(skills_root, "*.skill.md", "skill")
        seen: set[str] = {ff.name.removesuffix(".skill") for ff in flat}

        # Pass 2: standard Agent Skills format in subdirectories.
        standard: list[FrameworkFile] = []
        if skills_root.is_dir():
            for skill_dir in sorted(skills_root.iterdir()):
                skill_file = skill_dir / "SKILL.md"
                if skill_dir.is_dir() and skill_file.is_file():
                    ff = self._build_framework_file(skill_file, "skill")
                    named_ff = FrameworkFile(
                        name=skill_dir.name,
                        path=ff.path,
                        category=ff.category,
                        summary=ff.summary,
                        metadata=ff.metadata,
                    )
                    key = named_ff.name.removesuffix(".skill")
                    if key not in seen:
                        standard.append(named_ff)
                        seen.add(key)

        combined = flat + standard
        return sorted(combined, key=lambda ff: ff.name)

    def list_instructions(self) -> list[FrameworkFile]:
        return self._list_by_pattern(self._ctx.github_root / "instructions", "*.instructions.md", "instruction")

    def list_prompts(self) -> list[FrameworkFile]:
        """Return prompt files as read-only inventory. NOT registered as MCP Prompts.

        VS Code already exposes .github/prompts/*.prompt.md as native slash commands.
        Registering them as MCP Prompts would cause duplicate entries in the / picker.
        This behaviour is correct for VS Code. Alternative MCP clients (Claude Desktop,
        other IDEs) will see prompts only as generic text resources via prompts://list
        and prompts://{name}, not as native MCP Prompt artefacts. Known portability
        constraint of the v1 design.
        """
        return self._list_by_pattern(self._ctx.github_root / "prompts", "*.prompt.md", "prompt")

    def get_project_profile(self) -> FrameworkFile | None:
        path = self._ctx.github_root / "project-profile.md"
        return self._build_framework_file(path, "config") if path.is_file() else None

    def get_global_instructions(self) -> FrameworkFile | None:
        path = self._ctx.github_root / "copilot-instructions.md"
        return self._build_framework_file(path, "config") if path.is_file() else None

    def get_model_policy(self) -> FrameworkFile | None:
        path = self._ctx.github_root / "instructions" / "model-policy.instructions.md"
        return self._build_framework_file(path, "instruction") if path.is_file() else None

    def get_agents_index(self) -> FrameworkFile | None:
        path = self._ctx.github_root / "AGENTS.md"
        return self._build_framework_file(path, "index") if path.is_file() else None

    def get_package_changelog(self, package_id: str) -> str | None:
        """Return the changelog text for a package."""
        changelog_path = self._ctx.github_root / _CHANGELOGS_SUBDIR / f"{package_id}.md"
        try:
            if changelog_path.is_file():
                return changelog_path.read_text(encoding="utf-8")
        except OSError as exc:
            _log.warning("Cannot read package changelog %s: %s", changelog_path, exc)
        return None

    def list_agents_indexes(self) -> list[FrameworkFile]:
        """Return every AGENTS*.md index file found in the .github root."""
        if not self._ctx.github_root.is_dir():
            return []
        return sorted(
            [
                self._build_framework_file(path, "index")
                for path in self._ctx.github_root.glob("AGENTS*.md")
                if path.is_file()
            ],
            key=lambda framework_file: framework_file.name,
        )

    def get_orchestrator_state(self) -> dict[str, Any]:
        """Return orchestrator runtime state from .github/runtime/orchestrator-state.json."""
        state_path = self._ctx.github_root / "runtime" / "orchestrator-state.json"
        if not state_path.is_file():
            return {
                "current_phase": "",
                "current_agent": "",
                "retry_count": 0,
                "confidence": 1.0,
                "execution_mode": "autonomous",
                "last_updated": "",
                "phase_history": [],
                "active_task_id": "",
            }
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _log.warning("orchestrator-state.json unreadable: %s", exc)
            return {}

    def set_orchestrator_state(self, patch: dict[str, Any]) -> dict[str, Any]:
        """Update orchestrator runtime state with a partial merge and UTC timestamp."""
        state_path = self._ctx.github_root / "runtime" / "orchestrator-state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        current = self.get_orchestrator_state()
        current.update(patch)
        current["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        state_path.write_text(
            json.dumps(current, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return current


# ---------------------------------------------------------------------------
# workspace-info builder
# ---------------------------------------------------------------------------


def build_workspace_info(context: WorkspaceContext, inventory: FrameworkInventory) -> dict[str, Any]:
    profile = inventory.get_project_profile()
    initialized: bool = bool(profile.metadata.get("initialized", False)) if profile else False
    manifest = ManifestManager(context.github_root)
    return {
        "workspace_root": str(context.workspace_root),
        "github_root": str(context.github_root),
        "initialized": initialized,
        "engine_version": ENGINE_VERSION,
        "installed_packages": manifest.get_installed_versions(),
        "agent_count": len(inventory.list_agents()),
        "skill_count": len(inventory.list_skills()),
        "instruction_count": len(inventory.list_instructions()),
        "prompt_count": len(inventory.list_prompts()),
    }


# ---------------------------------------------------------------------------
# ManifestManager (A3 — installation manifest)
# ---------------------------------------------------------------------------

_MANIFEST_SCHEMA_VERSION: str = "1.0"
_SUPPORTED_MANIFEST_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0", "2.0"})
_MANIFEST_FILENAME: str = ".scf-manifest.json"
_BOOTSTRAP_PACKAGE_ID: str = "scf-engine-bootstrap"


def _resolve_package_version(manifest_version: Any, registry_version: Any) -> str:
    """Prefer the package manifest version and fall back to the registry hint."""
    manifest_value = str(manifest_version or "").strip()
    if manifest_value:
        return manifest_value
    registry_value = str(registry_version or "").strip()
    if registry_value:
        return registry_value
    return "unknown"


class ManifestManager:
    """Read, write and query the SCF installation manifest (.github/.scf-manifest.json).

    ``user_modified`` is computed on-demand by comparing the stored SHA-256 against
    the current file content on disk. It is never persisted to the manifest file.
    """

    def __init__(self, github_root: Path) -> None:
        self._github_root = github_root
        self._path = github_root / _MANIFEST_FILENAME

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> list[dict[str, Any]]:
        """Return the entries array. Returns [] if absent or unreadable."""
        if not self._path.is_file():
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            schema_version = str(raw.get("schema_version", "")).strip()
            if schema_version and schema_version not in _SUPPORTED_MANIFEST_SCHEMA_VERSIONS:
                _log.warning(
                    "Manifest schema '%s' unsupported, returning empty.", schema_version
                )
                return []
            entries = raw.get("entries", [])
            if not isinstance(entries, list):
                _log.warning("Manifest entries invalid, returning empty.")
                return []
            return list(entries)
        except (OSError, json.JSONDecodeError) as exc:
            _log.warning("Manifest unreadable, returning empty: %s", exc)
            return []

    def save(self, entries: list[dict[str, Any]]) -> None:
        """Persist entries to disk."""
        payload: dict[str, Any] = {
            "schema_version": _MANIFEST_SCHEMA_VERSION,
            "entries": entries,
        }
        try:
            self._path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            _log.error("Cannot write manifest: %s", exc)
            raise

    def upsert(self, file_rel: str, package: str, package_version: str, file_abs: Path) -> None:
        """Add or update the manifest entry for a single installed file."""
        entries = self.load()
        sha = self._sha256(file_abs)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_entry: dict[str, Any] = {
            "file": file_rel,
            "package": package,
            "package_version": package_version,
            "installed_at": now,
            "sha256": sha,
        }
        entries = [
            e
            for e in entries
            if not (e.get("file") == file_rel and e.get("package") == package)
        ]
        entries.append(new_entry)
        self.save(entries)

    def remove_package(self, package: str) -> list[str]:
        """Remove a package's entries and delete unmodified files on disk.

        Returns the list of relative paths preserved because the user modified them.
        """
        entries = self.load()
        preserved: list[str] = []
        remaining: list[dict[str, Any]] = []
        for entry in entries:
            if entry.get("package") != package:
                remaining.append(entry)
                continue
            file_path = self._github_root / entry["file"]
            shared_with_other_packages = any(
                other_entry.get("package") != package and other_entry.get("file") == entry.get("file")
                for other_entry in entries
            )
            user_modified = self._is_user_modified(entry, file_path)
            if shared_with_other_packages:
                if file_path.is_file():
                    try:
                        current_text = file_path.read_text(encoding="utf-8")
                        updated_text = _strip_package_section(current_text, str(entry.get("package", "")).strip())
                        if updated_text != current_text:
                            if user_modified:
                                structural_ok, _, _ = validate_structural(updated_text, current_text)
                                if not structural_ok:
                                    _log.warning(
                                        "[SPARK-ENGINE][WARNING] Structural validation failed for user-modified shared file after strip; preserving: %s",
                                        file_path,
                                    )
                                    preserved.append(entry["file"])
                                else:
                                    file_path.write_text(updated_text, encoding="utf-8")
                                    _log.info(
                                        "[SPARK-ENGINE][INFO] Removed package section for user-modified shared file: %s",
                                        file_path,
                                    )
                            else:
                                file_path.write_text(updated_text, encoding="utf-8")
                                _log.info("Removed package section for shared file: %s", file_path)
                        else:
                            if user_modified:
                                _log.info(
                                    "[SPARK-ENGINE][INFO] Strip no-op on user-modified shared file; leaving unchanged: %s",
                                    file_path,
                                )
                            else:
                                _log.info("Preserved shared file owned by other packages: %s", file_path)
                    except (OSError, UnicodeDecodeError) as exc:
                        _log.warning("Cannot update shared file %s during package removal: %s", file_path, exc)
                        preserved.append(entry["file"])
            elif user_modified:
                _log.warning("Preserving user-modified file: %s", file_path)
                preserved.append(entry["file"])
            else:
                if file_path.is_file():
                    try:
                        file_path.unlink()
                        _log.info("Removed file: %s", file_path)
                    except OSError as exc:
                        _log.warning("Cannot remove %s: %s", file_path, exc)
        self.save(remaining)
        return preserved

    def is_user_modified(self, file_rel: str) -> bool | None:
        """On-demand check: True if user modified the file since install, None if untracked."""
        for entry in self.load():
            if entry.get("file") == file_rel:
                return self._is_user_modified(entry, self._github_root / file_rel)
        return None

    def get_installed_versions(self) -> dict[str, str]:
        """Return installed package versions keyed by package id."""
        versions: dict[str, str] = {}
        for entry in self.load():
            package_id = str(entry.get("package", "")).strip()
            package_version = str(entry.get("package_version", "")).strip()
            if package_id and package_version:
                versions[package_id] = package_version
        return dict(sorted(versions.items()))

    def get_file_owners(self, file_rel: str) -> list[str]:
        """Return sorted package owners for a tracked file path."""
        owners = {
            str(entry.get("package", "")).strip()
            for entry in self.load()
            if str(entry.get("file", "")).strip() == file_rel
            and str(entry.get("package", "")).strip()
        }
        return sorted(owners)

    def upsert_many(
        self,
        package: str,
        package_version: str,
        files: list[tuple[str, Path]],
    ) -> None:
        """Add or update manifest entries for many installed files in one save."""
        entries = self.load()
        replacements = {file_rel for file_rel, _ in files}
        entries = [
            entry
            for entry in entries
            if not (
                str(entry.get("file", "")).strip() in replacements
                and str(entry.get("package", "")).strip() == package
            )
        ]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for file_rel, file_abs in files:
            entries.append(
                {
                    "file": file_rel,
                    "package": package,
                    "package_version": package_version,
                    "installed_at": now,
                    "sha256": self._sha256(file_abs),
                }
            )
        self.save(entries)

    def remove_owner_entries(self, package: str, files: list[str]) -> None:
        """Remove manifest ownership entries for one package on selected files."""
        targets = {file_rel for file_rel in files if file_rel}
        if not targets:
            return
        entries = [
            entry
            for entry in self.load()
            if not (
                str(entry.get("package", "")).strip() == package
                and str(entry.get("file", "")).strip() in targets
            )
        ]
        self.save(entries)

    def verify_integrity(self) -> dict[str, Any]:
        """Verify manifest integrity against files currently present under .github/."""
        entries = self.load()
        tracked_files: set[str] = set()
        missing: list[str] = []
        modified: list[str] = []
        ok: list[str] = []
        duplicate_owners_map: dict[str, set[str]] = {}

        for entry in entries:
            file_rel = str(entry.get("file", "")).strip()
            package_id = str(entry.get("package", "")).strip()
            if not file_rel:
                continue
            tracked_files.add(file_rel)
            owners = duplicate_owners_map.setdefault(file_rel, set())
            if package_id:
                owners.add(package_id)

            file_path = self._github_root / file_rel
            if not file_path.is_file():
                missing.append(file_rel)
            elif self._is_user_modified(entry, file_path):
                modified.append(file_rel)
            else:
                ok.append(file_rel)

        duplicate_owners = [
            {
                "file": file_rel,
                "owners": sorted(owners),
                "entry_count": sum(1 for entry in entries if str(entry.get("file", "")).strip() == file_rel),
            }
            for file_rel, owners in sorted(duplicate_owners_map.items())
            if len(owners) > 1
        ]

        ignored_runtime_files = {_MANIFEST_FILENAME, _REGISTRY_CACHE_FILENAME}
        user_files: list[str] = []
        untagged_spark_files: list[str] = []
        orphan_candidates: list[str] = []  # retrocompatibilità: = untagged_spark_files

        if self._github_root.is_dir():
            for path in sorted(
                candidate for candidate in self._github_root.rglob("*") if candidate.is_file()
            ):
                rel_path = path.relative_to(self._github_root).as_posix()
                if rel_path in ignored_runtime_files:
                    continue
                if rel_path in tracked_files:
                    continue

                is_spark = False
                if path.suffix == ".md":
                    try:
                        file_content = path.read_text(encoding="utf-8", errors="replace")
                        fm = parse_markdown_frontmatter(file_content)
                        is_spark = bool(fm.get("spark", False))
                    except OSError:
                        pass

                if is_spark:
                    untagged_spark_files.append(rel_path)
                    orphan_candidates.append(rel_path)
                else:
                    user_files.append(rel_path)

        missing.sort()
        modified.sort()
        ok.sort()
        summary: dict[str, Any] = {
            "tracked_entries": len(entries),
            "ok_count": len(ok),
            "issue_count": len(missing) + len(modified) + len(duplicate_owners),
            "orphan_candidate_count": len(orphan_candidates),
            "user_file_count": len(user_files),
            "untagged_spark_count": len(untagged_spark_files),
        }
        return {
            "missing": missing,
            "modified": modified,
            "ok": ok,
            "duplicate_owners": duplicate_owners,
            "orphan_candidates": orphan_candidates,
            "user_files": user_files,
            "untagged_spark_files": untagged_spark_files,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sha256(path: Path) -> str:
        if not path.is_file():
            return ""
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _is_user_modified(self, entry: dict[str, Any], file_path: Path) -> bool:
        stored = entry.get("sha256", "")
        if not stored:
            return False
        return self._sha256(file_path) != stored


class SnapshotManager:
    """Manage UTF-8 BASE snapshots stored under .github/runtime/snapshots/."""

    def __init__(self, snapshots_root: Path) -> None:
        self._snapshots_root = snapshots_root

    def save_snapshot(self, package_id: str, file_rel: str, file_abs: Path) -> bool:
        """Persist a UTF-8 snapshot for one package-managed file."""
        snapshot_path = self._snapshot_path(package_id, file_rel)
        if snapshot_path is None:
            return False

        try:
            content = file_abs.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _log.warning("Snapshot skipped for %s (%s): %s", file_rel, package_id, exc)
            return False

        try:
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(content, encoding="utf-8")
        except OSError as exc:
            _log.warning("Cannot write snapshot for %s (%s): %s", file_rel, package_id, exc)
            return False
        return True

    def load_snapshot(self, package_id: str, file_rel: str) -> str | None:
        """Return the stored UTF-8 snapshot content, if available and decodable."""
        snapshot_path = self._snapshot_path(package_id, file_rel)
        if snapshot_path is None or not snapshot_path.is_file():
            return None
        try:
            return snapshot_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _log.warning("Cannot read snapshot for %s (%s): %s", file_rel, package_id, exc)
            return None

    def delete_package_snapshots(self, package_id: str) -> list[str]:
        """Delete all snapshots for one package and return removed relative paths."""
        package_root = self._package_root(package_id)
        if package_root is None or not package_root.exists():
            return []

        all_files = sorted(
            (path for path in package_root.rglob("*") if path.is_file()),
            key=lambda path: len(path.parts),
            reverse=True,
        )
        deleted_files: list[str] = []
        for file_path in all_files:
            try:
                rel = file_path.relative_to(package_root).as_posix()
                file_path.unlink()
                deleted_files.append(rel)
            except OSError as exc:
                _log.warning(
                    "[SPARK-ENGINE][WARNING] delete_package_snapshots partial failure for %s: "
                    "deleted %d file(s), blocked at %s: %s",
                    package_id,
                    len(deleted_files),
                    file_path,
                    exc,
                )
                return sorted(deleted_files)

        for dir_path in sorted(
            (path for path in package_root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            try:
                dir_path.rmdir()
            except OSError:
                pass
        try:
            package_root.rmdir()
        except OSError:
            pass

        return sorted(deleted_files)

    def snapshot_exists(self, package_id: str, file_rel: str) -> bool:
        """Return True when a snapshot file exists for the given package/file pair."""
        snapshot_path = self._snapshot_path(package_id, file_rel)
        return snapshot_path is not None and snapshot_path.is_file()

    def list_package_snapshots(self, package_id: str) -> list[str]:
        """Return sorted snapshot paths relative to the package snapshot root."""
        package_root = self._package_root(package_id)
        if package_root is None or not package_root.is_dir():
            return []
        return sorted(
            path.relative_to(package_root).as_posix()
            for path in package_root.rglob("*")
            if path.is_file()
        )

    def _package_root(self, package_id: str) -> Path | None:
        normalized_package = self._validate_relative_path(package_id)
        if normalized_package is None or "/" in normalized_package:
            return None
        return self._snapshots_root / normalized_package

    def _snapshot_path(self, package_id: str, file_rel: str) -> Path | None:
        package_root = self._package_root(package_id)
        normalized_rel = self._validate_relative_path(file_rel)
        if package_root is None or normalized_rel is None:
            return None
        return package_root / PurePosixPath(normalized_rel)

    def _validate_relative_path(self, path_value: str) -> str | None:
        normalized = path_value.replace("\\", "/").strip()
        if not normalized:
            return None
        if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
            return None

        candidate = PurePosixPath(normalized)
        parts = candidate.parts
        if not parts or any(part in {"", ".", ".."} for part in parts):
            return None
        return candidate.as_posix()


class MergeSessionManager:
    """Manage manual merge sessions persisted under .github/runtime/merge-sessions/."""

    SESSION_TTL_HOURS: int = 24

    def __init__(self, sessions_root: Path) -> None:
        self._sessions_root = sessions_root

    def create_session(
        self,
        package_id: str,
        package_version: str,
        files: list[dict[str, Any]],
        conflict_mode: str = "manual",
    ) -> dict[str, Any]:
        """Create and persist a new active manual merge session."""
        created_at = _utc_now()
        expires_at = created_at + timedelta(hours=self.SESSION_TTL_HOURS)
        payload: dict[str, Any] = {
            "session_id": str(uuid.uuid4()),
            "package": package_id,
            "package_version": package_version,
            "conflict_mode": conflict_mode,
            "status": "active",
            "created_at": _format_utc_timestamp(created_at),
            "expires_at": _format_utc_timestamp(expires_at),
            "files": [self._normalize_session_file_entry(file_entry) for file_entry in files],
        }
        self._write_session(payload)
        return payload

    def load_session(self, session_id: str) -> dict[str, Any] | None:
        """Return a persisted session payload or None when unavailable."""
        session_path = self._session_path(session_id)
        if session_path is None or not session_path.is_file():
            return None
        try:
            raw = json.loads(session_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _log.warning("Cannot read merge session %s: %s", session_id, exc)
            return None
        return self._normalize_session_payload(raw) if isinstance(raw, dict) else None

    def load_active_session(self, session_id: str) -> dict[str, Any] | None:
        """Return an active session, expiring it automatically when overdue."""
        session = self.load_session(session_id)
        if session is None:
            return None
        if str(session.get("status", "")).strip() != "active":
            return session

        expires_at = _parse_utc_timestamp(str(session.get("expires_at", "")).strip())
        if expires_at is not None and expires_at <= _utc_now():
            expired_session = dict(session)
            expired_session["status"] = "expired"
            self._write_session(expired_session)
            return expired_session
        return session

    def mark_finalized(self, session_id: str) -> dict[str, Any] | None:
        """Mark a session as finalized and persist the updated payload."""
        return self.mark_status(session_id, "finalized")

    def mark_status(
        self,
        session_id: str,
        status: str,
        session: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Update the persisted status for a merge session."""
        current = self.load_session(session_id) if session is None else self._normalize_session_payload(session)
        if current is None:
            return None
        current["status"] = status
        self._write_session(current)
        return current

    def save_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist a normalized session payload and return the stored result."""
        normalized = self._normalize_session_payload(payload)
        self._write_session(normalized)
        return normalized

    def cleanup_expired_sessions(self) -> list[str]:
        """Mark overdue active sessions as expired and return their ids."""
        if not self._sessions_root.is_dir():
            return []

        expired: list[str] = []
        for session_file in sorted(self._sessions_root.glob("*.json")):
            session_id = session_file.stem
            session = self.load_session(session_id)
            if session is None:
                continue
            if str(session.get("status", "")).strip() != "active":
                continue
            expires_at = _parse_utc_timestamp(str(session.get("expires_at", "")).strip())
            if expires_at is None or expires_at > _utc_now():
                continue
            updated = dict(session)
            updated["status"] = "expired"
            self._write_session(updated)
            expired.append(session_id)
        return expired

    @staticmethod
    def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
        """Persist JSON atomically using a .tmp file in the target directory."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, path)
        except OSError:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise

    def _write_session(self, payload: dict[str, Any]) -> None:
        session_id = str(payload.get("session_id", "")).strip()
        session_path = self._session_path(session_id)
        if session_path is None:
            raise ValueError(f"Invalid merge session id: {session_id!r}")
        self._atomic_write_json(session_path, self._normalize_session_payload(payload))

    def _session_path(self, session_id: str) -> Path | None:
        normalized = session_id.strip()
        if not re.fullmatch(r"[A-Za-z0-9-]+", normalized):
            return None
        return self._sessions_root / f"{normalized}.json"

    def _normalize_session_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        normalized["conflict_mode"] = str(payload.get("conflict_mode", "manual")).strip() or "manual"
        normalized["status"] = str(payload.get("status", "active")).strip() or "active"
        files = payload.get("files", [])
        if isinstance(files, list):
            normalized["files"] = [
                self._normalize_session_file_entry(file_entry)
                for file_entry in files
                if isinstance(file_entry, dict)
            ]
        else:
            normalized["files"] = []
        return normalized

    @staticmethod
    def _normalize_session_file_entry(entry: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(entry)
        manifest_rel = str(entry.get("manifest_rel", "")).strip()
        public_file = str(entry.get("file", "")).strip()
        workspace_path = str(entry.get("workspace_path", public_file)).strip()

        if not public_file and manifest_rel:
            public_file = f".github/{manifest_rel}"
        if not workspace_path:
            workspace_path = public_file
        if not manifest_rel and public_file.startswith(".github/"):
            manifest_rel = public_file.removeprefix(".github/")

        proposed_text = entry.get("proposed_text")
        validator_results = entry.get("validator_results")
        marker_text = entry.get("marker_text")

        normalized.update(
            {
                "file": public_file,
                "workspace_path": workspace_path,
                "manifest_rel": manifest_rel,
                "conflict_id": str(entry.get("conflict_id", manifest_rel or public_file)).strip()
                or manifest_rel
                or public_file,
                "base_text": str(entry.get("base_text", "") or ""),
                "ours_text": str(entry.get("ours_text", "") or ""),
                "theirs_text": str(entry.get("theirs_text", "") or ""),
                "proposed_text": proposed_text if isinstance(proposed_text, str) else None,
                "resolution_status": str(entry.get("resolution_status", "pending")).strip()
                or "pending",
                "validator_results": validator_results if isinstance(validator_results, dict) else None,
                "marker_text": marker_text if isinstance(marker_text, str) else None,
            }
        )
        return normalized


# ---------------------------------------------------------------------------
# RegistryClient (A4 — package registry)
# ---------------------------------------------------------------------------

_REGISTRY_URL: str = (
    "https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json"
)
_REGISTRY_CACHE_FILENAME: str = ".scf-registry-cache.json"
_REGISTRY_TIMEOUT_SECONDS: int = 5


class RegistryClient:
    """Fetch and cache the SCF registry index from GitHub.

    V1 supports public packages only (public raw.githubusercontent.com URLs).
    Any non-standard or private URL produces an explicit ValueError —
    no silent attempt is ever made on private raw URLs.
    """

    def __init__(self, github_root: Path, registry_url: str = _REGISTRY_URL) -> None:
        self._github_root = github_root
        self._registry_url = registry_url
        self._cache_path = github_root / _REGISTRY_CACHE_FILENAME

    def fetch(self) -> dict[str, Any]:
        """Return registry data, falling back to cache on network failure.

        Raises ValueError for non-public URLs.
        Raises RuntimeError if both network and cache are unavailable.
        """
        if not self._registry_url.startswith("https://raw.githubusercontent.com/"):
            raise ValueError(
                "Private or non-standard registry URLs are not supported in v1. "
                "Only public raw.githubusercontent.com URLs are accepted."
            )
        try:
            data = self._fetch_remote()
            self._save_cache(data)
            return data
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            _log.warning("Registry fetch failed (%s), falling back to cache", exc)
            return self._load_cache()

    def list_packages(self) -> list[dict[str, Any]]:
        """Return the packages array. Returns [] when registry is unavailable."""
        try:
            return list(self.fetch().get("packages", []))
        except RuntimeError:
            return []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_remote(self) -> dict[str, Any]:
        req = urllib.request.Request(
            self._registry_url,
            headers={"User-Agent": f"spark-framework-engine/{ENGINE_VERSION}"},
        )
        with urllib.request.urlopen(req, timeout=_REGISTRY_TIMEOUT_SECONDS) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
        return json.loads(raw)  # type: ignore[no-any-return]

    def _save_cache(self, data: dict[str, Any]) -> None:
        try:
            self._cache_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            _log.warning("Cannot write registry cache: %s", exc)

    def _load_cache(self) -> dict[str, Any]:
        if not self._cache_path.is_file():
            raise RuntimeError(
                "Registry unavailable and no local cache found at "
                f"{self._cache_path}. Connect to the internet and retry."
            )
        try:
            return json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Registry cache corrupted: {exc}") from exc

    def fetch_package_manifest(self, repo_url: str) -> dict[str, Any]:
        """Fetch the package-manifest.json from a package repo.

        Constructs the raw URL from repo_url. No caching — always fetched fresh
        to guarantee consistency with the published package version.
        Raises ValueError for non-github.com repo URLs.
        Raises RuntimeError on network or parse failure.
        """
        if not repo_url.startswith("https://github.com/"):
            raise ValueError(
                f"Unsupported repo URL: {repo_url!r}. "
                "Only https://github.com/ URLs are supported."
            )
        raw_url = (
            repo_url.replace("https://github.com/", "https://raw.githubusercontent.com/")
            + "/main/package-manifest.json"
        )
        try:
            raw = self.fetch_raw_file(raw_url)
            return json.loads(raw)  # type: ignore[no-any-return]
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Cannot fetch package manifest from {raw_url}: {exc}"
            ) from exc

    def fetch_raw_file(self, raw_url: str) -> str:
        """Fetch a single raw text file from a URL. No caching."""
        req = urllib.request.Request(
            raw_url,
            headers={"User-Agent": f"spark-framework-engine/{ENGINE_VERSION}"},
        )
        with urllib.request.urlopen(req, timeout=_REGISTRY_TIMEOUT_SECONDS) as resp:  # noqa: S310
            return resp.read().decode("utf-8")


# ---------------------------------------------------------------------------
# SparkFrameworkEngine — Resources (15) and Tools (33)
# ---------------------------------------------------------------------------


class SparkFrameworkEngine:
    """Register MCP resources and tools over FastMCP via workspace discovery.

    MCP Prompts are intentionally NOT registered here.
    VS Code already exposes .github/prompts/*.prompt.md as native slash commands.
    Registering them again via MCP would create duplicate entries in the / picker.
    Prompt files remain accessible as Resources (prompts://list, prompts://{name})
    and via scf_list_prompts / scf_get_prompt tools for Agent mode consumption.
    """

    def __init__(self, mcp: FastMCP, context: WorkspaceContext, inventory: FrameworkInventory) -> None:
        self._mcp = mcp
        self._ctx = context
        self._inventory = inventory

    def register_resources(self) -> None:
        """Register all 14 MCP resources.

        Portability note: MCP Prompts are intentionally not registered here.
        VS Code handles .github/prompts/ natively as slash commands; alternative
        MCP clients will see prompts only as text resources, not as native MCP
        Prompt artefacts. Known v1 constraint, correct by design.
        """
        inventory = self._inventory
        ctx = self._ctx
        manifest = ManifestManager(ctx.github_root)

        def _fmt_list(items: list[FrameworkFile], title: str) -> str:
            if not items:
                return f"# {title}\n\nNone found."
            lines = [f"# {title} ({len(items)} total)\n"]
            for ff in items:
                desc = str(ff.summary)[:120] if ff.summary else "(no description)"
                lines.append(f"- {ff.name}: {desc}")
            return "\n".join(lines)

        def _fmt_workspace_info(info: dict[str, Any]) -> str:
            lines = ["# SPARK Framework Engine — Workspace Info\n"]
            for key, val in info.items():
                lines.append(f"{key}: {val}")
            return "\n".join(lines)

        @self._mcp.resource("agents://list")
        async def resource_agents_list() -> str:
            return _fmt_list(inventory.list_agents(), "SCF Agents")

        @self._mcp.resource("agents://{name}")
        async def resource_agent_by_name(name: str) -> str:
            for ff in inventory.list_agents():
                if ff.name.lower() == name.lower():
                    return ff.path.read_text(encoding="utf-8", errors="replace")
            return f"Agent '{name}' not found. Use agents://list to see available agents."

        @self._mcp.resource("skills://list")
        async def resource_skills_list() -> str:
            return _fmt_list(inventory.list_skills(), "SCF Skills")

        @self._mcp.resource("skills://{name}")
        async def resource_skill_by_name(name: str) -> str:
            query = name.lower().removesuffix(".skill")
            for ff in inventory.list_skills():
                if ff.name.lower().removesuffix(".skill") == query:
                    return ff.path.read_text(encoding="utf-8", errors="replace")
            return f"Skill '{name}' not found. Use skills://list to see available skills."

        @self._mcp.resource("instructions://list")
        async def resource_instructions_list() -> str:
            return _fmt_list(inventory.list_instructions(), "SCF Instructions")

        @self._mcp.resource("instructions://{name}")
        async def resource_instruction_by_name(name: str) -> str:
            query = name.lower().removesuffix(".instructions")
            for ff in inventory.list_instructions():
                if ff.name.lower().removesuffix(".instructions") == query:
                    return ff.path.read_text(encoding="utf-8", errors="replace")
            return f"Instruction '{name}' not found. Use instructions://list."

        @self._mcp.resource("prompts://list")
        async def resource_prompts_list() -> str:
            return _fmt_list(inventory.list_prompts(), "SCF Prompts")

        @self._mcp.resource("prompts://{name}")
        async def resource_prompt_by_name(name: str) -> str:
            query = name.lower().removesuffix(".prompt")
            for ff in inventory.list_prompts():
                if ff.name.lower().removesuffix(".prompt") == query:
                    return ff.path.read_text(encoding="utf-8", errors="replace")
            return f"Prompt '{name}' not found. Use prompts://list."

        @self._mcp.resource("scf://global-instructions")
        async def resource_global_instructions() -> str:
            ff = inventory.get_global_instructions()
            return ff.path.read_text(encoding="utf-8", errors="replace") if ff else "copilot-instructions.md not found."

        @self._mcp.resource("scf://project-profile")
        async def resource_project_profile() -> str:
            ff = inventory.get_project_profile()
            if ff is None:
                return "project-profile.md not found in .github/."
            content = ff.path.read_text(encoding="utf-8", errors="replace")
            if not ff.metadata.get("initialized", False):
                return "# WARNING: project not initialized (initialized: false)\nRun #project-setup to configure this workspace.\n\n" + content
            return content

        @self._mcp.resource("scf://model-policy")
        async def resource_model_policy() -> str:
            ff = inventory.get_model_policy()
            return ff.path.read_text(encoding="utf-8", errors="replace") if ff else "model-policy.instructions.md not found."

        @self._mcp.resource("scf://agents-index")
        async def resource_agents_index() -> str:
            indexes = inventory.list_agents_indexes()
            if not indexes:
                return "AGENTS.md not found."
            return "\n\n---\n\n".join(
                ff.path.read_text(encoding="utf-8", errors="replace")
                for ff in indexes
            )

        @self._mcp.resource("scf://framework-version")
        async def resource_framework_version() -> str:
            installed_versions = manifest.get_installed_versions()
            lines = [
                f"SPARK Framework Engine version: {ENGINE_VERSION}",
                "",
                "Installed SCF packages:",
            ]
            if installed_versions:
                for package_id, package_version in installed_versions.items():
                    lines.append(f"- {package_id}: {package_version}")
            else:
                lines.append("- none")
            return "\n".join(lines)

        @self._mcp.resource("scf://workspace-info")
        async def resource_workspace_info_res() -> str:
            info = build_workspace_info(ctx, inventory)
            return _fmt_workspace_info(info)

        @self._mcp.resource("scf://runtime-state")
        async def resource_runtime_state() -> str:
            """Stato runtime orchestratore come JSON formattato."""
            state = inventory.get_orchestrator_state()
            return json.dumps(state, indent=2, ensure_ascii=False)

        _log.info("Resources registered: 4 list + 4 template + 7 scf:// singletons (15 total)")

    def register_tools(self) -> None:  # noqa: C901
        """Register all 33 MCP tools."""
        inventory = self._inventory

        def _ff_to_dict(ff: FrameworkFile) -> dict[str, Any]:
            return {"name": ff.name, "path": str(ff.path), "category": ff.category, "summary": ff.summary, "metadata": ff.metadata}

        @self._mcp.tool()
        async def scf_list_agents() -> dict[str, Any]:
            """Return all discovered SCF agents with name, path and summary."""
            items = inventory.list_agents()
            return {"count": len(items), "agents": [_ff_to_dict(ff) for ff in items]}

        @self._mcp.tool()
        async def scf_get_agent(name: str) -> dict[str, Any]:
            """Return full content and metadata for a single SCF agent by name."""
            for ff in inventory.list_agents():
                if ff.name.lower() == name.lower():
                    result = _ff_to_dict(ff)
                    result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
                    return result
            return {"error": f"Agent '{name}' not found.", "available": [ff.name for ff in inventory.list_agents()]}

        @self._mcp.tool()
        async def scf_list_skills() -> dict[str, Any]:
            """Return all discovered SCF skills with name, path and summary."""
            items = inventory.list_skills()
            return {"count": len(items), "skills": [_ff_to_dict(ff) for ff in items]}

        @self._mcp.tool()
        async def scf_get_skill(name: str) -> dict[str, Any]:
            """Return full content and metadata for a single SCF skill by name."""
            query = name.lower().removesuffix(".skill")
            for ff in inventory.list_skills():
                if ff.name.lower().removesuffix(".skill") == query:
                    result = _ff_to_dict(ff)
                    result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
                    return result
            return {"error": f"Skill '{name}' not found.", "available": [ff.name for ff in inventory.list_skills()]}

        @self._mcp.tool()
        async def scf_list_instructions() -> dict[str, Any]:
            """Return all discovered SCF instruction files with name, path and summary."""
            items = inventory.list_instructions()
            return {"count": len(items), "instructions": [_ff_to_dict(ff) for ff in items]}

        @self._mcp.tool()
        async def scf_get_instruction(name: str) -> dict[str, Any]:
            """Return full content and metadata for a single SCF instruction by name."""
            query = name.lower().removesuffix(".instructions")
            for ff in inventory.list_instructions():
                if ff.name.lower().removesuffix(".instructions") == query:
                    result = _ff_to_dict(ff)
                    result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
                    return result
            return {"error": f"Instruction '{name}' not found.", "available": [ff.name for ff in inventory.list_instructions()]}

        @self._mcp.tool()
        async def scf_list_prompts() -> dict[str, Any]:
            """Return all SCF prompt files. Read-only — slash commands are handled natively by VS Code."""
            items = inventory.list_prompts()
            return {"count": len(items), "prompts": [_ff_to_dict(ff) for ff in items]}

        @self._mcp.tool()
        async def scf_get_prompt(name: str) -> dict[str, Any]:
            """Return full content of a SCF prompt file by stem name."""
            query = name.lower().removesuffix(".prompt")
            for ff in inventory.list_prompts():
                if ff.name.lower().removesuffix(".prompt") == query:
                    result = _ff_to_dict(ff)
                    result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
                    return result
            return {"error": f"Prompt '{name}' not found.", "available": [ff.name for ff in inventory.list_prompts()]}

        @self._mcp.tool()
        async def scf_get_project_profile() -> dict[str, Any]:
            """Return project-profile.md content, metadata and initialized state."""
            ff = inventory.get_project_profile()
            if ff is None:
                return {"error": "project-profile.md not found in .github/."}
            result = _ff_to_dict(ff)
            result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
            result["initialized"] = bool(ff.metadata.get("initialized", False))
            if not result["initialized"]:
                result["warning"] = "Project not initialized. Run #project-setup to configure this workspace."
            return result

        @self._mcp.tool()
        async def scf_get_global_instructions() -> dict[str, Any]:
            """Return copilot-instructions.md content and metadata."""
            ff = inventory.get_global_instructions()
            if ff is None:
                return {"error": "copilot-instructions.md not found in .github/."}
            result = _ff_to_dict(ff)
            result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
            return result

        @self._mcp.tool()
        async def scf_get_model_policy() -> dict[str, Any]:
            """Return model-policy.instructions.md content and metadata."""
            ff = inventory.get_model_policy()
            if ff is None:
                return {"error": "model-policy.instructions.md not found in .github/instructions/."}
            result = _ff_to_dict(ff)
            result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
            return result

        @self._mcp.tool()
        async def scf_get_framework_version() -> dict[str, Any]:
            """Return the engine version and installed SCF package versions."""
            return {
                "engine_version": ENGINE_VERSION,
                "packages": manifest.get_installed_versions(),
            }

        @self._mcp.tool()
        async def scf_get_workspace_info() -> dict[str, Any]:
            """Return workspace paths, initialization state and SCF asset counts."""
            return build_workspace_info(self._ctx, inventory)

        manifest = ManifestManager(self._ctx.github_root)
        registry = RegistryClient(self._ctx.github_root)
        merge_engine = MergeEngine()
        snapshots = SnapshotManager(self._ctx.github_root / _SNAPSHOTS_SUBDIR)
        sessions = MergeSessionManager(self._ctx.github_root / _MERGE_SESSIONS_SUBDIR)
        sessions.cleanup_expired_sessions()

        def _save_snapshots(package_id: str, files: list[tuple[str, Path]]) -> dict[str, list[str]]:
            """Persist BASE snapshots for written files without blocking the main operation."""
            written: list[str] = []
            skipped: list[str] = []
            for file_rel, file_abs in files:
                public_path = f".github/{file_rel}"
                if snapshots.save_snapshot(package_id, file_rel, file_abs):
                    written.append(public_path)
                else:
                    skipped.append(public_path)
            return {"written": written, "skipped": skipped}

        def _read_text_if_possible(path: Path) -> str | None:
            """Read a UTF-8 workspace file, returning None for undecodable content."""
            try:
                return path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                _log.warning("Cannot read text file %s: %s", path, exc)
                return None

        def _supports_stateful_merge(conflict_mode: str) -> bool:
            """Return True for conflict modes that use a persistent merge session."""
            return conflict_mode in {"manual", "auto", "assisted"}

        def _render_marker_text(file_entry: dict[str, Any]) -> str:
            """Render or reuse the persisted marker text for one conflicting file."""
            existing = file_entry.get("marker_text")
            if isinstance(existing, str) and existing:
                return existing
            merge_result = merge_engine.diff3_merge(
                str(file_entry.get("base_text", "") or ""),
                str(file_entry.get("ours_text", "") or ""),
                str(file_entry.get("theirs_text", "") or ""),
            )
            return merge_engine.render_with_markers(merge_result)

        def _build_session_entry(
            file_path: str,
            rel: str,
            base_text: str,
            ours_text: str,
            theirs_text: str,
            marker_text: str,
        ) -> dict[str, Any]:
            """Build the persisted session payload for one conflicting file."""
            return {
                "file": file_path,
                "workspace_path": file_path,
                "manifest_rel": rel,
                "conflict_id": rel,
                "base_text": base_text,
                "ours_text": ours_text,
                "theirs_text": theirs_text,
                "proposed_text": None,
                "resolution_status": "pending",
                "validator_results": None,
                "marker_text": marker_text,
                "original_sha_at_session_open": _sha256_text(ours_text),
            }

        def _replace_session_entry(
            session: dict[str, Any],
            index: int,
            file_entry: dict[str, Any],
        ) -> None:
            """Replace one normalized file entry inside an in-memory session payload."""
            files = list(session.get("files", []))
            files[index] = MergeSessionManager._normalize_session_file_entry(file_entry)
            session["files"] = files

        def _find_session_entry(
            session: dict[str, Any],
            conflict_id: str,
        ) -> tuple[int, dict[str, Any]] | None:
            """Find one conflict entry in a session by its stable conflict id."""
            for index, file_entry in enumerate(list(session.get("files", []))):
                if str(file_entry.get("conflict_id", "")).strip() == conflict_id:
                    return (index, dict(file_entry))
            return None

        def _count_remaining_conflicts(session: dict[str, Any]) -> int:
            """Count session entries that still need approval or manual resolution."""
            return sum(
                1
                for file_entry in list(session.get("files", []))
                if str(file_entry.get("resolution_status", "pending")).strip() != "approved"
            )

        def _resolve_conflict_automatically(file_entry: dict[str, Any]) -> str | None:
            """Return a safe automatic merge proposal only for clearly unambiguous cases."""
            base_text = _normalize_merge_text(str(file_entry.get("base_text", "") or ""))
            ours_text = _normalize_merge_text(str(file_entry.get("ours_text", "") or ""))
            theirs_text = _normalize_merge_text(str(file_entry.get("theirs_text", "") or ""))

            frontmatter_blocks = {
                frontmatter
                for frontmatter in (
                    _extract_frontmatter_block(base_text),
                    _extract_frontmatter_block(ours_text),
                    _extract_frontmatter_block(theirs_text),
                )
                if frontmatter is not None
            }
            if len(frontmatter_blocks) > 1:
                return None

            if ours_text == theirs_text:
                return ours_text
            if base_text == ours_text:
                return theirs_text
            if base_text == theirs_text:
                return ours_text
            if ours_text and ours_text in theirs_text:
                return theirs_text
            if theirs_text and theirs_text in ours_text:
                return ours_text
            return _resolve_disjoint_line_additions(base_text, ours_text, theirs_text)

        def _propose_conflict_resolution(
            session: dict[str, Any],
            conflict_id: str,
            persist: bool = True,
        ) -> dict[str, Any]:
            """Populate proposed_text and validator results for one conflict when safe."""
            found = _find_session_entry(session, conflict_id)
            if found is None:
                return {
                    "success": False,
                    "error": "conflict_not_found",
                    "conflict_id": conflict_id,
                }

            index, file_entry = found
            proposed_text = _resolve_conflict_automatically(file_entry)
            if proposed_text is None:
                file_entry["proposed_text"] = None
                file_entry["validator_results"] = None
                file_entry["resolution_status"] = "manual"
                _replace_session_entry(session, index, file_entry)
                if persist:
                    sessions.save_session(session)
                return {
                    "success": False,
                    "conflict_id": conflict_id,
                    "fallback": "manual",
                    "reason": "best_effort_auto_resolution_not_safe",
                    "validator_results": None,
                }

            validator_results = run_post_merge_validators(
                proposed_text,
                str(file_entry.get("base_text", "") or ""),
                str(file_entry.get("ours_text", "") or ""),
                str(file_entry.get("file", file_entry.get("workspace_path", "")) or ""),
            )
            file_entry["validator_results"] = validator_results
            if not validator_results.get("passed", False):
                file_entry["proposed_text"] = None
                file_entry["resolution_status"] = "manual"
                _replace_session_entry(session, index, file_entry)
                if persist:
                    sessions.save_session(session)
                return {
                    "success": False,
                    "conflict_id": conflict_id,
                    "fallback": "manual",
                    "reason": "post_merge_validation_failed",
                    "validator_results": validator_results,
                }

            file_entry["proposed_text"] = proposed_text
            file_entry["resolution_status"] = "auto_resolved"
            _replace_session_entry(session, index, file_entry)
            if persist:
                sessions.save_session(session)
            return {
                "success": True,
                "conflict_id": conflict_id,
                "proposed_text": proposed_text,
                "validator_results": validator_results,
                "resolution_status": "auto_resolved",
            }

        @self._mcp.tool()
        async def scf_list_available_packages() -> dict[str, Any]:
            """List all packages currently available in the public SCF registry."""
            try:
                packages = registry.list_packages()
            except Exception as exc:  # noqa: BLE001
                return {"success": False, "error": f"Registry unavailable: {exc}"}
            return {
                "success": True,
                "count": len(packages),
                "packages": [
                    {
                        "id": p.get("id"),
                        "description": p.get("description", ""),
                        "latest_version": p.get("latest_version", ""),
                        "status": p.get("status", "unknown"),
                        "repo_url": p.get("repo_url", ""),
                    }
                    for p in packages
                ],
            }

        @self._mcp.tool()
        async def scf_get_package_info(package_id: str) -> dict[str, Any]:
            """Return detailed information for a package, including file manifest stats."""
            try:
                packages = registry.list_packages()
            except Exception as exc:  # noqa: BLE001
                return {"success": False, "error": f"Registry unavailable: {exc}"}
            pkg = next((p for p in packages if p.get("id") == package_id), None)
            if pkg is None:
                return {
                    "success": False,
                    "error": f"Package '{package_id}' not found in registry.",
                    "available": [p.get("id") for p in packages],
                }
            try:
                pkg_manifest = registry.fetch_package_manifest(pkg["repo_url"])
            except Exception as exc:  # noqa: BLE001
                return {
                    "success": False,
                    "error": f"Cannot fetch package manifest: {exc}",
                    "package": pkg,
                }
            files: list[str] = pkg_manifest.get("files", [])
            installed_versions = manifest.get_installed_versions()
            dependencies = _normalize_string_list(pkg_manifest.get("dependencies", []))
            conflicts = _normalize_string_list(pkg_manifest.get("conflicts", []))
            min_engine_version = str(
                pkg_manifest.get("min_engine_version", pkg.get("engine_min_version", ""))
            ).strip()
            categories = {
                "root": 0,
                "agents": 0,
                "skills": 0,
                "instructions": 0,
                "prompts": 0,
                "other": 0,
            }
            for fp in files:
                if fp.startswith(".github/agents/"):
                    categories["agents"] += 1
                elif fp.startswith(".github/skills/"):
                    categories["skills"] += 1
                elif fp.startswith(".github/instructions/"):
                    categories["instructions"] += 1
                elif fp.startswith(".github/prompts/"):
                    categories["prompts"] += 1
                elif fp.startswith(".github/") and fp.count("/") == 1:
                    categories["root"] += 1
                else:
                    categories["other"] += 1
            return {
                "success": True,
                "package": {
                    "id": pkg.get("id"),
                    "description": pkg.get("description", ""),
                    "repo_url": pkg.get("repo_url", ""),
                    "latest_version": pkg.get("latest_version", ""),
                    "status": pkg.get("status", "unknown"),
                    "engine_min_version": pkg.get("engine_min_version", ""),
                    "tags": pkg.get("tags", []),
                },
                "manifest": {
                    "schema_version": str(pkg_manifest.get("schema_version", "1.0")),
                    "package": pkg_manifest.get("package", package_id),
                    "version": _resolve_package_version(
                        pkg_manifest.get("version", ""),
                        pkg.get("latest_version", ""),
                    ),
                    "display_name": pkg_manifest.get("display_name", ""),
                    "description": pkg_manifest.get("description", pkg.get("description", "")),
                    "author": pkg_manifest.get("author", ""),
                    "min_engine_version": min_engine_version,
                    "dependencies": dependencies,
                    "conflicts": conflicts,
                    "file_ownership_policy": str(
                        pkg_manifest.get("file_ownership_policy", "error")
                    ).strip()
                    or "error",
                    "file_policies": _normalize_file_policies(
                        pkg_manifest.get("file_policies", {})
                    ),
                    "changelog_path": str(pkg_manifest.get("changelog_path", "")).strip(),
                    "file_count": len(files),
                    "categories": categories,
                    "files": files,
                },
                "compatibility": {
                    "engine_version": ENGINE_VERSION,
                    "engine_compatible": _is_engine_version_compatible(
                        ENGINE_VERSION,
                        min_engine_version,
                    ),
                    "installed_packages": installed_versions,
                    "missing_dependencies": [
                        dependency
                        for dependency in dependencies
                        if dependency not in installed_versions
                    ],
                    "present_conflicts": [
                        conflict
                        for conflict in conflicts
                        if conflict in installed_versions
                    ],
                },
            }

        def _build_install_result(success: bool, error: str | None = None, **extras: Any) -> dict[str, Any]:
            """Build a stable install/update payload with conflict metadata."""
            result: dict[str, Any] = {
                "success": success,
                "installed": [],
                "extended_files": [],
                "delegated_files": [],
                "preserved": [],
                "removed_obsolete_files": [],
                "preserved_obsolete_files": [],
                "conflicts_detected": [],
                "blocked_files": [],
                "replaced_files": [],
                "merged_files": [],
                "merge_clean": [],
                "merge_conflict": [],
                "session_id": None,
                "session_status": None,
                "session_expires_at": None,
                "snapshot_written": [],
                "snapshot_skipped": [],
                "requires_user_resolution": False,
                "resolution_applied": "none",
            }
            if error is not None:
                result["error"] = error
            result.update(extras)
            return result

        def _normalize_file_policies(raw_policies: Any) -> dict[str, str]:
            """Normalize manifest file policies declared as {'.github/path': 'extend|delegate|error'}."""
            if not isinstance(raw_policies, dict):
                return {}

            normalized: dict[str, str] = {}
            for raw_path, raw_policy in raw_policies.items():
                if not isinstance(raw_path, str) or not isinstance(raw_policy, str):
                    continue
                path = raw_path.replace("\\", "/").strip()
                policy = raw_policy.strip().lower()
                if not path.startswith(".github/") or policy not in {"error", "extend", "delegate"}:
                    continue
                normalized[path] = policy
            return normalized

        def _validate_extend_policy_target(file_path: str) -> None:
            """Reject extend on file types that cannot safely host SCF section markers."""
            if file_path.endswith(".agent.md"):
                raise ValueError(
                    f"Policy 'extend' is not supported for files ending with '.agent.md': {file_path}"
                )

        def _section_markers(package_id: str) -> tuple[str, str]:
            """Return begin/end markers for the package-owned section inside a shared file."""
            return (
                f"<!-- SCF:SECTION:{package_id}:BEGIN -->",
                f"<!-- SCF:SECTION:{package_id}:END -->",
            )

        def _parse_section_markers(text: str, package_id: str) -> tuple[int, int] | None:
            """Return the normalized content slice between package section markers, if present."""
            normalized_text = _normalize_merge_text(text)
            begin_marker, end_marker = _section_markers(package_id)
            begin_index = normalized_text.find(begin_marker)
            if begin_index < 0:
                return None

            content_start = begin_index + len(begin_marker)
            if content_start < len(normalized_text) and normalized_text[content_start] == "\n":
                content_start += 1

            end_index = normalized_text.find(end_marker, content_start)
            if end_index < 0:
                return None

            content_end = end_index
            if content_end > content_start and normalized_text[content_end - 1] == "\n":
                content_end -= 1
            return (content_start, content_end)

        def _render_package_section(package_id: str, content: str) -> str:
            """Render one package-owned section bounded by SCF HTML comment markers."""
            begin_marker, end_marker = _section_markers(package_id)
            normalized_content = _normalize_merge_text(content)
            if normalized_content and not normalized_content.endswith("\n"):
                normalized_content = f"{normalized_content}\n"
            return f"{begin_marker}\n{normalized_content}{end_marker}\n"

        def _create_file_with_section(file_path: str, package_id: str, content: str) -> str:
            """Create a new shared file that initially contains only the current package section."""
            _validate_extend_policy_target(file_path)
            return _render_package_section(package_id, content)

        def _update_package_section(existing_text: str, package_id: str, content: str) -> str:
            """Insert or replace only the current package section while preserving outer content."""
            normalized_existing = _normalize_merge_text(existing_text)
            parsed_section = _parse_section_markers(normalized_existing, package_id)
            rendered_section = _render_package_section(package_id, content)
            if parsed_section is None:
                stripped_existing = normalized_existing.rstrip("\n")
                if not stripped_existing:
                    return rendered_section
                return f"{stripped_existing}\n\n{rendered_section}"

            begin_marker, end_marker = _section_markers(package_id)
            begin_index = normalized_existing.find(begin_marker)
            end_index = normalized_existing.find(end_marker, parsed_section[1])
            if begin_index < 0 or end_index < 0:
                return rendered_section
            section_end = end_index + len(end_marker)
            if section_end < len(normalized_existing) and normalized_existing[section_end] == "\n":
                section_end += 1
            return f"{normalized_existing[:begin_index]}{rendered_section}{normalized_existing[section_end:]}"

        def _get_package_install_context(package_id: str) -> dict[str, Any]:
            """Return package installation context or a structured failure result."""
            try:
                packages = registry.list_packages()
            except Exception as exc:  # noqa: BLE001
                return _build_install_result(False, error=f"Registry unavailable: {exc}")

            pkg = next((p for p in packages if p.get("id") == package_id), None)
            if pkg is None:
                return _build_install_result(
                    False,
                    error=f"Package '{package_id}' not found in registry.",
                    available=[p.get("id") for p in packages],
                )
            if pkg.get("status") == "deprecated":
                return _build_install_result(
                    False,
                    error=(
                        f"Package '{package_id}' is deprecated. "
                        "Check the registry for its successor."
                    ),
                )

            try:
                pkg_manifest = registry.fetch_package_manifest(pkg["repo_url"])
            except Exception as exc:  # noqa: BLE001
                return _build_install_result(
                    False,
                    error=f"Cannot fetch package manifest: {exc}",
                )

            files: list[str] = pkg_manifest.get("files", [])
            if not files:
                return _build_install_result(
                    False,
                    error=f"Package '{package_id}' has no files in its manifest.",
                )

            pkg_version = _resolve_package_version(
                pkg_manifest.get("version", ""),
                pkg.get("latest_version", "unknown"),
            )
            min_engine_version = str(
                pkg_manifest.get("min_engine_version", pkg.get("engine_min_version", ""))
            ).strip()
            dependencies = _normalize_string_list(pkg_manifest.get("dependencies", []))
            declared_conflicts = _normalize_string_list(pkg_manifest.get("conflicts", []))
            file_ownership_policy = (
                str(pkg_manifest.get("file_ownership_policy", "error")).strip() or "error"
            )
            file_policies = _normalize_file_policies(pkg_manifest.get("file_policies", {}))
            installed_versions = manifest.get_installed_versions()
            missing_dependencies = [
                dependency for dependency in dependencies if dependency not in installed_versions
            ]
            present_conflicts = [
                conflict for conflict in declared_conflicts if conflict in installed_versions
            ]

            return {
                "success": True,
                "pkg": pkg,
                "pkg_manifest": pkg_manifest,
                "files": files,
                "pkg_version": pkg_version,
                "min_engine_version": min_engine_version,
                "dependencies": dependencies,
                "declared_conflicts": declared_conflicts,
                "file_ownership_policy": file_ownership_policy,
                "file_policies": file_policies,
                "installed_versions": installed_versions,
                "missing_dependencies": missing_dependencies,
                "present_conflicts": present_conflicts,
                "engine_compatible": _is_engine_version_compatible(
                    ENGINE_VERSION,
                    min_engine_version,
                ),
            }

        def _classify_install_files(
            package_id: str,
            files: list[str],
            file_policies: dict[str, str] | None = None,
        ) -> dict[str, Any]:
            """Classify package targets before any install or update writes.

            ``file_policies`` uses the simple manifest shape
            {".github/path.md": "extend|delegate|error"}.
            """
            records: list[dict[str, Any]] = []
            write_plan: list[dict[str, Any]] = []
            extend_plan: list[dict[str, Any]] = []
            delegate_plan: list[dict[str, Any]] = []
            preserve_plan: list[dict[str, Any]] = []
            conflict_plan: list[dict[str, Any]] = []
            merge_plan: list[dict[str, Any]] = []
            ownership_issues: list[dict[str, Any]] = []
            normalized_file_policies = file_policies or {}

            for file_path in files:
                rel = file_path.removeprefix(".github/")
                dest = self._ctx.workspace_root / file_path
                owners = [owner for owner in manifest.get_file_owners(rel) if owner != package_id]
                bootstrap_adoption = package_id == "spark-base" and owners == [_BOOTSTRAP_PACKAGE_ID]
                per_file_policy = normalized_file_policies.get(file_path, "error")
                if owners and not bootstrap_adoption:
                    if per_file_policy == "extend":
                        _validate_extend_policy_target(file_path)
                        item = {
                            "file": file_path,
                            "classification": "extend_section",
                            "owners": owners,
                            "policy": "extend",
                            "file_exists": dest.exists(),
                        }
                        records.append(item)
                        extend_plan.append(item)
                        continue
                    if per_file_policy == "delegate":
                        item = {
                            "file": file_path,
                            "classification": "delegate_skip",
                            "owners": owners,
                            "policy": "delegate",
                        }
                        records.append(item)
                        delegate_plan.append(item)
                        continue
                    item = {
                        "file": file_path,
                        "classification": "conflict_cross_owner",
                        "owners": owners,
                    }
                    records.append(item)
                    conflict_plan.append(item)
                    ownership_issues.append({"file": file_path, "owners": owners})
                    continue

                tracked_state = manifest.is_user_modified(rel)
                if not dest.exists():
                    item = {"file": file_path, "classification": "create_new"}
                    records.append(item)
                    write_plan.append(item)
                    continue
                if tracked_state is True:
                    if snapshots.snapshot_exists(package_id, rel):
                        item = {
                            "file": file_path,
                            "classification": "merge_candidate",
                        }
                        records.append(item)
                        merge_plan.append(item)
                        continue
                    item = {
                        "file": file_path,
                        "classification": "preserve_tracked_modified",
                        "base_unavailable": True,
                    }
                    records.append(item)
                    preserve_plan.append(item)
                    continue
                if tracked_state is False:
                    item = {
                        "file": file_path,
                        "classification": "update_tracked_clean",
                    }
                    if bootstrap_adoption:
                        item["adopt_bootstrap_owner"] = True
                    records.append(item)
                    write_plan.append(item)
                    continue

                item = {
                    "file": file_path,
                    "classification": "conflict_untracked_existing",
                }
                records.append(item)
                conflict_plan.append(item)

            return {
                "records": records,
                "write_plan": write_plan,
                "extend_plan": extend_plan,
                "delegate_plan": delegate_plan,
                "preserve_plan": preserve_plan,
                "conflict_plan": conflict_plan,
                "merge_plan": merge_plan,
                "ownership_issues": ownership_issues,
                "conflict_mode_required": len(conflict_plan) > 0,
                "can_install_with_replace": len(ownership_issues) == 0,
            }

        @self._mcp.tool()
        async def scf_list_installed_packages() -> dict[str, Any]:
            """List packages currently installed in the active workspace."""
            entries = manifest.load()
            if not entries:
                return {"count": 0, "packages": []}
            grouped: dict[str, dict[str, Any]] = {}
            for entry in entries:
                pkg_id = entry.get("package", "")
                if not pkg_id:
                    continue
                node = grouped.setdefault(
                    pkg_id,
                    {
                        "package": pkg_id,
                        "version": entry.get("package_version", ""),
                        "file_count": 0,
                        "files": [],
                    },
                )
                node["file_count"] += 1
                node["files"].append(entry.get("file", ""))
            packages = sorted(grouped.values(), key=lambda x: str(x["package"]))
            return {"count": len(packages), "packages": packages}

        @self._mcp.tool()
        async def scf_install_package(
            package_id: str,
            conflict_mode: str = "abort",
        ) -> dict[str, Any]:
            """Install an SCF package from the public registry into the active workspace .github/."""
            if conflict_mode not in _SUPPORTED_CONFLICT_MODES:
                return _build_install_result(
                    False,
                    error=(
                        f"Unsupported conflict_mode '{conflict_mode}'. "
                        "Supported modes: abort, replace, manual, auto, assisted."
                    ),
                    package=package_id,
                    conflict_mode=conflict_mode,
                )

            install_context = _get_package_install_context(package_id)
            if install_context.get("success") is False:
                return install_context

            pkg = install_context["pkg"]
            files = install_context["files"]
            pkg_version = install_context["pkg_version"]
            min_engine_version = install_context["min_engine_version"]
            file_ownership_policy = install_context["file_ownership_policy"]
            file_policies = install_context["file_policies"]
            installed_versions = install_context["installed_versions"]
            missing_dependencies = install_context["missing_dependencies"]
            present_conflicts = install_context["present_conflicts"]
            engine_compatible = install_context["engine_compatible"]

            if not engine_compatible:
                return _build_install_result(
                    False,
                    error=(
                        f"Package '{package_id}' requires engine version >= {min_engine_version}."
                    ),
                    package=package_id,
                    required_engine_version=min_engine_version,
                    engine_version=ENGINE_VERSION,
                )
            if missing_dependencies:
                return _build_install_result(
                    False,
                    error=(
                        f"Package '{package_id}' requires missing dependencies: "
                        f"{', '.join(missing_dependencies)}"
                    ),
                    package=package_id,
                    missing_dependencies=missing_dependencies,
                    installed_packages=installed_versions,
                )
            if present_conflicts:
                return _build_install_result(
                    False,
                    error=(
                        f"Package '{package_id}' conflicts with installed packages: "
                        f"{', '.join(present_conflicts)}"
                    ),
                    package=package_id,
                    present_conflicts=present_conflicts,
                    installed_packages=installed_versions,
                )

            try:
                classification_report = _classify_install_files(
                    package_id,
                    files,
                    file_policies=file_policies,
                )
            except ValueError as exc:
                return _build_install_result(
                    False,
                    error=str(exc),
                    package=package_id,
                    version=pkg_version,
                    file_ownership_policy=file_ownership_policy,
                )
            ownership_conflicts = list(classification_report["ownership_issues"])
            if ownership_conflicts:
                return _build_install_result(
                    False,
                    error=(
                        f"Package '{package_id}' conflicts with files already owned by another package."
                    ),
                    package=package_id,
                    version=pkg_version,
                    file_ownership_policy=file_ownership_policy,
                    effective_file_ownership_policy="error",
                    conflicts=ownership_conflicts,
                    conflicts_detected=classification_report["conflict_plan"],
                    blocked_files=[item["file"] for item in classification_report["conflict_plan"]],
                    requires_user_resolution=True,
                )

            unresolved_conflicts = [
                item
                for item in classification_report["conflict_plan"]
                if item.get("classification") == "conflict_untracked_existing"
            ]
            if unresolved_conflicts and conflict_mode == "abort":
                return _build_install_result(
                    False,
                    error=(
                        f"Package '{package_id}' would overwrite existing untracked files. "
                        "Review conflicts and retry with conflict_mode='replace'."
                    ),
                    package=package_id,
                    version=pkg_version,
                    conflicts_detected=unresolved_conflicts,
                    blocked_files=[item["file"] for item in unresolved_conflicts],
                    requires_user_resolution=True,
                    conflict_mode=conflict_mode,
                )

            preserved = [item["file"] for item in classification_report["preserve_plan"]]
            fetch_errors: list[str] = []
            staged_files: list[tuple[str, str, str, str, bool]] = []
            replaced_files: list[str] = []
            extended_files: list[str] = []
            adopted_bootstrap_files: list[str] = []
            adopted_bootstrap_rels: list[str] = []
            delegated_files = [
                str(item["file"])
                for item in classification_report["delegate_plan"]
                if item.get("classification") == "delegate_skip"
            ]
            merge_clean: list[dict[str, Any]] = []
            merge_conflict: list[dict[str, Any]] = []
            session_entries: list[dict[str, Any]] = []
            manifest_targets: list[tuple[str, Path]] = []
            snapshot_written: list[str] = []
            snapshot_skipped: list[str] = []
            merge_candidates = {
                str(item["file"])
                for item in classification_report["merge_plan"]
                if item.get("classification") == "merge_candidate"
            }
            used_manual_merge = False
            for item in classification_report["records"]:
                file_path = str(item["file"])
                item_classification = str(item["classification"])
                if item_classification == "preserve_tracked_modified":
                    continue
                if item_classification == "delegate_skip":
                    continue
                if item_classification == "merge_candidate":
                    if conflict_mode == "replace":
                        replaced_files.append(file_path)
                    elif not _supports_stateful_merge(conflict_mode):
                        preserved.append(file_path)
                        continue
                if item_classification == "conflict_cross_owner":
                    continue
                if item_classification == "conflict_untracked_existing" and conflict_mode != "replace":
                    continue
                raw_url = (
                    pkg["repo_url"].replace(
                        "https://github.com/", "https://raw.githubusercontent.com/"
                    )
                    + "/main/"
                    + file_path
                )
                rel = file_path.removeprefix(".github/")
                if item_classification == "conflict_untracked_existing":
                    replaced_files.append(file_path)
                try:
                    content = registry.fetch_raw_file(raw_url)
                except (urllib.error.URLError, OSError) as exc:
                    fetch_errors.append(f"{file_path}: {exc}")
                    continue
                staged_files.append(
                    (
                        file_path,
                        rel,
                        content,
                        item_classification,
                        bool(item.get("adopt_bootstrap_owner", False)),
                    )
                )
            if fetch_errors:
                return _build_install_result(
                    False,
                    package=package_id,
                    version=pkg_version,
                    delegated_files=delegated_files,
                    preserved=preserved,
                    replaced_files=replaced_files,
                    conflicts_detected=classification_report["conflict_plan"],
                    resolution_applied="replace" if replaced_files else "none",
                    errors=fetch_errors,
                )
            # --- Diff-based cleanup: remove files obsoleted by this update ---
            old_files: set[str] = {
                entry["file"]
                for entry in manifest.load()
                if entry.get("package") == package_id
            }
            new_files: set[str] = {f.removeprefix(".github/") for f in files if f}
            to_remove: set[str] = old_files - new_files
            removed_files: list[str] = []
            preserved_obsolete: list[str] = []
            for rel_path in sorted(to_remove):
                is_modified = manifest.is_user_modified(rel_path)
                file_abs = self._ctx.github_root / rel_path
                if is_modified:
                    preserved_obsolete.append(rel_path)
                    _log.warning("Obsolete file preserved (user-modified): %s", rel_path)
                else:
                    if file_abs.is_file():
                        try:
                            file_abs.unlink()
                            removed_files.append(rel_path)
                            _log.info("Obsolete file removed: %s", rel_path)
                        except OSError as exc:
                            _log.warning("Cannot remove obsolete file %s: %s", rel_path, exc)
            # --- End diff-based cleanup ---
            installed: list[str] = []
            backups: dict[Path, str | None] = {}
            written_paths: list[tuple[str, str, Path]] = []
            session_payload: dict[str, Any] | None = None
            auto_validator_results: dict[str, Any] = {}
            try:
                for file_path, rel, content, staged_classification, adopt_bootstrap_owner in staged_files:
                    dest = self._ctx.workspace_root / file_path
                    previous_content = _read_text_if_possible(dest) if dest.is_file() else None
                    backups[dest] = previous_content

                    if staged_classification == "extend_section":
                        if dest.exists() and previous_content is None:
                            raise OSError(f"Cannot extend non-text file: {dest}")
                        next_text = (
                            _create_file_with_section(file_path, package_id, content)
                            if previous_content is None
                            else _update_package_section(previous_content, package_id, content)
                        )
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_text(next_text, encoding="utf-8")
                        written_paths.append((file_path, rel, dest))
                        manifest_targets.append((rel, dest))
                        installed.append(file_path)
                        if adopt_bootstrap_owner:
                            adopted_bootstrap_files.append(file_path)
                            adopted_bootstrap_rels.append(rel)
                        extended_files.append(file_path)
                        continue

                    if file_path in merge_candidates and _supports_stateful_merge(conflict_mode):
                        base_text = snapshots.load_snapshot(package_id, rel)
                        ours_text = previous_content
                        if base_text is None or ours_text is None:
                            preserved.append(file_path)
                            snapshot_skipped.append(file_path)
                            continue

                        used_manual_merge = conflict_mode == "manual"
                        merge_result = merge_engine.diff3_merge(base_text, ours_text, content)
                        if merge_result.status in {MERGE_STATUS_CLEAN, MERGE_STATUS_IDENTICAL}:
                            merged_text = merge_result.merged_text
                            if merged_text != ours_text:
                                dest.parent.mkdir(parents=True, exist_ok=True)
                                dest.write_text(merged_text, encoding="utf-8")
                                written_paths.append((file_path, rel, dest))
                            merge_clean.append(
                                {
                                    "file": file_path,
                                    "status": merge_result.status,
                                }
                            )
                            manifest_targets.append((rel, dest))
                            installed.append(file_path)
                            if adopt_bootstrap_owner:
                                adopted_bootstrap_files.append(file_path)
                                adopted_bootstrap_rels.append(rel)
                            continue

                        merged_text = merge_engine.render_with_markers(merge_result)
                        if conflict_mode in {"manual", "assisted"}:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            dest.write_text(merged_text, encoding="utf-8")
                            written_paths.append((file_path, rel, dest))
                        merge_conflict.append(
                            {
                                "file": file_path,
                                "status": merge_result.status,
                                "conflict_count": len(merge_result.conflicts),
                            }
                        )
                        session_entries.append(
                            _build_session_entry(
                                file_path,
                                rel,
                                base_text,
                                ours_text,
                                content,
                                merged_text,
                            )
                        )
                        continue

                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(content, encoding="utf-8")
                    written_paths.append((file_path, rel, dest))
                    manifest_targets.append((rel, dest))
                    installed.append(file_path)
                    if adopt_bootstrap_owner:
                        adopted_bootstrap_files.append(file_path)
                        adopted_bootstrap_rels.append(rel)

                if session_entries:
                    session_payload = sessions.create_session(
                        package_id,
                        pkg_version,
                        session_entries,
                        conflict_mode=conflict_mode,
                    )

                    if conflict_mode == "auto":
                        auto_clean_entries: list[dict[str, Any]] = []
                        remaining_conflict_entries: list[dict[str, Any]] = []
                        for conflict in list(session_payload.get("files", [])):
                            conflict_id = str(conflict.get("conflict_id", "")).strip()
                            resolution = _propose_conflict_resolution(
                                session_payload,
                                conflict_id,
                                persist=False,
                            )
                            current = _find_session_entry(session_payload, conflict_id)
                            if current is None:
                                continue
                            current_index, current_entry = current
                            public_file = str(current_entry.get("file", "")).strip()
                            manifest_rel = str(current_entry.get("manifest_rel", "")).strip()
                            workspace_path = str(current_entry.get("workspace_path", public_file)).strip()
                            dest = self._ctx.workspace_root / workspace_path
                            validator_results = current_entry.get("validator_results")
                            if isinstance(validator_results, dict):
                                auto_validator_results[public_file] = validator_results

                            if resolution.get("success") is True:
                                proposed_text = str(current_entry.get("proposed_text", "") or "")
                                dest.parent.mkdir(parents=True, exist_ok=True)
                                dest.write_text(proposed_text, encoding="utf-8")
                                written_paths.append((public_file, manifest_rel, dest))
                                current_entry["resolution_status"] = "approved"
                                _replace_session_entry(session_payload, current_index, current_entry)
                                auto_clean_entries.append(
                                    {
                                        "file": public_file,
                                        "status": "auto_resolved",
                                    }
                                )
                                continue

                            marker_text = _render_marker_text(current_entry)
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            dest.write_text(marker_text, encoding="utf-8")
                            written_paths.append((public_file, manifest_rel, dest))
                            current_entry["resolution_status"] = "manual"
                            _replace_session_entry(session_payload, current_index, current_entry)
                            remaining_conflict_entries.append(
                                {
                                    "file": public_file,
                                    "status": MERGE_STATUS_CONFLICT,
                                    "conflict_count": 1,
                                }
                            )

                        merge_clean.extend(auto_clean_entries)
                        merge_conflict = remaining_conflict_entries
                        if remaining_conflict_entries:
                            sessions.save_session(session_payload)
                        else:
                            for file_entry in list(session_payload.get("files", [])):
                                manifest_rel = str(file_entry.get("manifest_rel", "")).strip()
                                workspace_path = str(file_entry.get("workspace_path", "")).strip()
                                if manifest_rel and workspace_path:
                                    manifest_targets.append(
                                        (manifest_rel, self._ctx.workspace_root / workspace_path)
                                    )
                            session_payload = sessions.mark_status(
                                str(session_payload.get("session_id", "")).strip(),
                                "auto_completed",
                                session=session_payload,
                            )

                if manifest_targets:
                    manifest.upsert_many(
                        package_id,
                        pkg_version,
                        manifest_targets,
                    )
                    if adopted_bootstrap_rels:
                        manifest.remove_owner_entries(_BOOTSTRAP_PACKAGE_ID, adopted_bootstrap_rels)
                    snapshot_report = _save_snapshots(package_id, manifest_targets)
                    snapshot_written.extend(snapshot_report["written"])
                    snapshot_skipped.extend(snapshot_report["skipped"])
            except OSError as exc:
                rollback_errors: list[str] = []
                for _, _, dest in reversed(written_paths):
                    previous_content = backups.get(dest)
                    try:
                        if previous_content is None:
                            if dest.is_file():
                                dest.unlink()
                        else:
                            dest.write_text(previous_content, encoding="utf-8")
                    except OSError as rollback_exc:
                        rollback_errors.append(f"{dest}: {rollback_exc}")
                result: dict[str, Any] = {
                    "success": False,
                    "package": package_id,
                    "version": pkg_version,
                    "installed": [],
                    "preserved": preserved,
                    "removed_obsolete_files": removed_files,
                    "preserved_obsolete_files": preserved_obsolete,
                    "errors": [f"write failure: {exc}"],
                    "rolled_back": len(rollback_errors) == 0,
                }
                if rollback_errors:
                    result["rollback_errors"] = rollback_errors
                return result
            success_result: dict[str, Any] = _build_install_result(
                True,
                package=package_id,
                version=pkg_version,
                installed=installed,
                extended_files=extended_files,
                delegated_files=delegated_files,
                preserved=preserved,
                removed_obsolete_files=removed_files,
                preserved_obsolete_files=preserved_obsolete,
                replaced_files=replaced_files,
                adopted_bootstrap_files=adopted_bootstrap_files,
                merged_files=[item["file"] for item in merge_clean + merge_conflict],
                merge_clean=merge_clean,
                merge_conflict=merge_conflict,
                conflicts_detected=classification_report["conflict_plan"],
                session_id=None if session_payload is None else session_payload["session_id"],
                session_status=None if session_payload is None else session_payload["status"],
                session_expires_at=None if session_payload is None else session_payload["expires_at"],
                snapshot_written=snapshot_written,
                snapshot_skipped=snapshot_skipped,
                requires_user_resolution=len(merge_conflict) > 0,
                resolution_applied=(
                    "auto"
                    if conflict_mode == "auto" and not merge_conflict and session_payload is not None
                    else "manual"
                    if conflict_mode == "auto" and merge_conflict
                    else "assisted"
                    if conflict_mode == "assisted" and session_payload is not None
                    else "manual"
                    if used_manual_merge or (conflict_mode == "manual" and session_payload is not None)
                    else "replace" if replaced_files else "none"
                ),
                validator_results=auto_validator_results if auto_validator_results else None,
                remaining_conflicts=len(merge_conflict) if merge_conflict else None,
            )
            return success_result

        def _summarize_available_updates(report: dict[str, Any]) -> list[dict[str, Any]]:
            """Extract only updatable packages from the update planner report."""
            return [
                {
                    "package": item.get("package", ""),
                    "installed": item.get("installed", ""),
                    "latest": item.get("latest", ""),
                }
                for item in report.get("updates", [])
                if item.get("status") == "update_available"
            ]

        @self._mcp.tool()
        async def scf_check_updates() -> dict[str, Any]:
            """Return only the installed SCF packages that have an update available."""
            report = _plan_package_updates()
            if report.get("success") is False:
                return report
            updates = _summarize_available_updates(report)
            return {
                "success": True,
                "count": len(updates),
                "updates": updates,
            }

        @self._mcp.tool()
        async def scf_update_package(
            package_id: str,
            conflict_mode: str = "abort",
        ) -> dict[str, Any]:
            """Update one installed SCF package while preserving user-modified files."""
            if conflict_mode not in _SUPPORTED_CONFLICT_MODES:
                return {
                    "success": False,
                    "error": (
                        f"Unsupported conflict_mode '{conflict_mode}'. "
                        "Supported modes: abort, replace, manual, auto, assisted."
                    ),
                    "package": package_id,
                    "conflict_mode": conflict_mode,
                }

            installed_versions = manifest.get_installed_versions()
            if package_id not in installed_versions:
                return {
                    "success": False,
                    "error": f"Package '{package_id}' is not installed.",
                    "package": package_id,
                }

            version_from = installed_versions[package_id]
            plan_report = _plan_package_updates(package_id)
            if plan_report.get("success") is False:
                return plan_report

            requested_update = next(
                (item for item in plan_report.get("updates", []) if item.get("package") == package_id),
                None,
            )
            if requested_update is None:
                return {
                    "success": False,
                    "error": f"Package '{package_id}' is not installed.",
                    "package": package_id,
                }

            if requested_update.get("status") == "up_to_date":
                return {
                    "success": True,
                    "package": package_id,
                    "already_up_to_date": True,
                    "version_from": version_from,
                    "version_to": version_from,
                    "updated_files": [],
                    "preserved_files": [],
                }

            blocked = [
                item for item in plan_report.get("plan", {}).get("blocked", [])
                if item.get("package") == package_id
            ]
            if blocked:
                return {
                    "success": False,
                    "package": package_id,
                    "error": "Cannot update package because the update plan is blocked.",
                    "blocked": blocked,
                    "version_from": version_from,
                    "version_to": requested_update.get("latest", version_from),
                }

            install_report = await scf_install_package(package_id, conflict_mode=conflict_mode)
            if install_report.get("success") is False:
                result = {
                    "success": False,
                    "package": package_id,
                    "error": install_report.get("error", "unknown error"),
                    "version_from": version_from,
                    "version_to": requested_update.get("latest", version_from),
                    "details": install_report,
                }
                if "conflicts_detected" in install_report:
                    result["conflicts_detected"] = [
                        {
                            "package": package_id,
                            "conflicts": list(install_report.get("conflicts_detected", [])),
                        }
                    ]
                return result

            preserved_files = list(install_report.get("preserved", [])) + list(
                install_report.get("preserved_obsolete_files", [])
            )
            return {
                "success": True,
                "package": package_id,
                "version_from": version_from,
                "version_to": install_report.get("version", requested_update.get("latest", version_from)),
                "updated_files": list(install_report.get("installed", [])),
                "preserved_files": preserved_files,
                "removed_obsolete_files": list(install_report.get("removed_obsolete_files", [])),
                "merged_files": list(install_report.get("merged_files", [])),
                "merge_clean": list(install_report.get("merge_clean", [])),
                "merge_conflict": list(install_report.get("merge_conflict", [])),
                "session_id": install_report.get("session_id"),
                "session_status": install_report.get("session_status"),
                "session_expires_at": install_report.get("session_expires_at"),
                "snapshot_written": list(install_report.get("snapshot_written", [])),
                "snapshot_skipped": list(install_report.get("snapshot_skipped", [])),
                "requires_user_resolution": bool(install_report.get("requires_user_resolution", False)),
                "resolution_applied": install_report.get("resolution_applied", "none"),
                "validator_results": install_report.get("validator_results"),
                "remaining_conflicts": install_report.get("remaining_conflicts"),
                "already_up_to_date": False,
            }

        def _plan_package_updates(requested_package_id: str | None = None) -> dict[str, Any]:
            entries = manifest.load()
            if not entries:
                return {
                    "success": True,
                    "message": "No SCF packages installed via manifest.",
                    "updates": [],
                    "plan": {
                        "requested_package": requested_package_id,
                        "can_apply": False,
                        "order": [],
                        "blocked": [],
                    },
                }
            try:
                reg_packages = registry.list_packages()
            except Exception as exc:  # noqa: BLE001
                return {"success": False, "error": f"Registry unavailable: {exc}"}

            installed_versions = manifest.get_installed_versions()
            reg_index: dict[str, Any] = {p["id"]: p for p in reg_packages if "id" in p}
            updates: list[dict[str, Any]] = []
            manifest_cache: dict[str, dict[str, Any]] = {}
            dependency_map: dict[str, list[str]] = {}
            candidate_ids: set[str] = set()
            blocked: list[dict[str, Any]] = []

            for pkg_id in sorted(installed_versions):
                reg_entry = reg_index.get(pkg_id)
                if reg_entry is None:
                    updates.append({
                        "package": pkg_id,
                        "status": "not_in_registry",
                        "installed": installed_versions[pkg_id],
                    })
                    continue

                installed_ver = installed_versions[pkg_id]
                registry_latest_ver = str(reg_entry.get("latest_version", "")).strip()
                pkg_manifest: dict[str, Any] | None = None
                manifest_error: str | None = None
                try:
                    pkg_manifest = registry.fetch_package_manifest(reg_entry["repo_url"])
                    manifest_cache[pkg_id] = pkg_manifest
                except Exception as exc:  # noqa: BLE001
                    manifest_error = str(exc)

                latest_ver = _resolve_package_version(
                    pkg_manifest.get("version", "") if pkg_manifest is not None else "",
                    registry_latest_ver,
                )
                status = "up_to_date" if installed_ver == latest_ver else "update_available"
                update_entry: dict[str, Any] = {
                    "package": pkg_id,
                    "status": status,
                    "installed": installed_ver,
                    "latest": latest_ver,
                    "registry_status": reg_entry.get("status", "unknown"),
                }

                if pkg_manifest is not None:
                    if status == "update_available":
                        dependencies = _normalize_string_list(pkg_manifest.get("dependencies", []))
                        dependency_map[pkg_id] = dependencies
                        min_engine_version = str(
                            pkg_manifest.get("min_engine_version", reg_entry.get("engine_min_version", ""))
                        ).strip()
                        missing_dependencies = [
                            dependency for dependency in dependencies if dependency not in installed_versions
                        ]
                        engine_compatible = _is_engine_version_compatible(
                            ENGINE_VERSION,
                            min_engine_version,
                        )
                        update_entry["dependencies"] = dependencies
                        update_entry["missing_dependencies"] = missing_dependencies
                        update_entry["engine_min_version"] = min_engine_version
                        update_entry["engine_compatible"] = engine_compatible

                        if missing_dependencies:
                            update_entry["status"] = "blocked_missing_dependencies"
                            blocked.append({
                                "package": pkg_id,
                                "reason": "missing_dependencies",
                                "missing_dependencies": missing_dependencies,
                            })
                        elif not engine_compatible:
                            update_entry["status"] = "blocked_engine_version"
                            blocked.append({
                                "package": pkg_id,
                                "reason": "engine_version",
                                "required_engine_version": min_engine_version,
                                "engine_version": ENGINE_VERSION,
                            })
                        else:
                            candidate_ids.add(pkg_id)
                elif manifest_error is not None:
                    update_entry["status"] = "metadata_unavailable"
                    update_entry["error"] = f"Cannot fetch package manifest: {manifest_error}"
                    blocked.append({
                        "package": pkg_id,
                        "reason": "metadata_unavailable",
                        "error": manifest_error,
                    })

                updates.append(update_entry)

            selected_ids = set(candidate_ids)
            selected_blocked = list(blocked)
            if requested_package_id:
                matching_update = next(
                    (item for item in updates if item.get("package") == requested_package_id),
                    None,
                )
                if matching_update is None:
                    return {
                        "success": False,
                        "error": f"Package '{requested_package_id}' is not installed.",
                        "updates": updates,
                    }
                selected_ids = {requested_package_id} if requested_package_id in candidate_ids else set()
                selected_blocked = [
                    item for item in blocked if item.get("package") == requested_package_id
                ]
                if requested_package_id in candidate_ids:
                    pending = [requested_package_id]
                    while pending:
                        current = pending.pop()
                        for dependency in dependency_map.get(current, []):
                            if dependency in candidate_ids and dependency not in selected_ids:
                                selected_ids.add(dependency)
                                pending.append(dependency)

            resolution = _resolve_dependency_update_order(list(selected_ids), dependency_map)
            if resolution["cycles"]:
                for pkg_id in resolution["cycles"]:
                    selected_blocked.append({
                        "package": pkg_id,
                        "reason": "dependency_cycle",
                    })

            plan_order: list[dict[str, Any]] = []
            for pkg_id in resolution["order"]:
                update_entry = next(item for item in updates if item.get("package") == pkg_id)
                plan_order.append({
                    "package": pkg_id,
                    "installed": update_entry.get("installed", ""),
                    "target": update_entry.get("latest", ""),
                    "dependencies": [
                        dependency
                        for dependency in dependency_map.get(pkg_id, [])
                        if dependency in selected_ids
                    ],
                })

            summary = {
                "up_to_date": len([u for u in updates if u.get("status") == "up_to_date"]),
                "update_available": len([u for u in updates if u.get("status") == "update_available"]),
                "not_in_registry": len([u for u in updates if u.get("status") == "not_in_registry"]),
                "blocked": len(selected_blocked),
            }
            return {
                "success": True,
                "updates": updates,
                "total": len(updates),
                "summary": summary,
                "plan": {
                    "requested_package": requested_package_id,
                    "can_apply": len(plan_order) > 0 and len(selected_blocked) == 0,
                    "order": plan_order,
                    "blocked": selected_blocked,
                },
            }

        @self._mcp.tool()
        async def scf_update_packages() -> dict[str, Any]:
            """Check installed SCF packages for updates and build an ordered update preview."""
            return _plan_package_updates()

        @self._mcp.tool()
        async def scf_apply_updates(
            package_id: str | None = None,
            conflict_mode: str = "abort",
        ) -> dict[str, Any]:
            """Apply package updates by reinstalling latest versions from the registry.

            If package_id is provided, applies the update only for that package.
            Otherwise applies all available updates.
            """
            if conflict_mode not in _SUPPORTED_CONFLICT_MODES:
                return {
                    "success": False,
                    "error": (
                        f"Unsupported conflict_mode '{conflict_mode}'. "
                        "Supported modes: abort, replace, manual, auto, assisted."
                    ),
                    "package": package_id,
                    "conflict_mode": conflict_mode,
                }
            report = _plan_package_updates(package_id)
            if report.get("success") is False:
                return report
            plan = report.get("plan", {})
            plan_order = list(plan.get("order", []))
            blocked = list(plan.get("blocked", []))
            target_ids = [item.get("package", "") for item in plan_order if item.get("package")]
            if blocked:
                return {
                    "success": False,
                    "error": "Cannot apply updates because the update plan is blocked.",
                    "plan": plan,
                    "updates": report.get("updates", []),
                }
            if package_id and not target_ids:
                return {
                    "success": False,
                    "error": f"No update available for package '{package_id}'.",
                    "updates": report.get("updates", []),
                    "plan": plan,
                }
            if not target_ids:
                return {
                    "success": True,
                    "message": "No updates to apply.",
                    "applied": [],
                    "failed": [],
                    "plan": plan,
                }
            preflight_reports: list[dict[str, Any]] = []
            batch_conflicts: list[dict[str, Any]] = []
            for pkg_id in target_ids:
                preview = await scf_plan_install(pkg_id)
                preflight_reports.append(preview)
                if preview.get("success") is False:
                    return {
                        "success": False,
                        "error": f"Cannot preflight package '{pkg_id}' before apply.",
                        "applied": [],
                        "failed": [],
                        "plan": plan,
                        "preflight": preflight_reports,
                    }
                preview_conflicts = list(preview.get("conflict_plan", []))
                if preview_conflicts and conflict_mode != "replace":
                    batch_conflicts.append(
                        {
                            "package": pkg_id,
                            "conflicts": preview_conflicts,
                        }
                    )
            if batch_conflicts:
                return {
                    "success": False,
                    "error": "Batch preflight detected unresolved conflicts. No files written.",
                    "applied": [],
                    "failed": [],
                    "plan": plan,
                    "batch_conflicts": batch_conflicts,
                    "preflight": preflight_reports,
                }
            applied: list[dict[str, Any]] = []
            failed: list[dict[str, Any]] = []
            for pkg_id in target_ids:
                result = await scf_install_package(pkg_id, conflict_mode=conflict_mode)
                if result.get("success") is True:
                    applied.append(result)
                else:
                    failed.append({"package": pkg_id, "error": result.get("error", "unknown error")})
            return {
                "success": len(failed) == 0,
                "applied": applied,
                "failed": failed,
                "total_targets": len(target_ids),
                "plan": plan,
                "conflict_mode": conflict_mode,
            }

        @self._mcp.tool()
        async def scf_plan_install(package_id: str) -> dict[str, Any]:
            """Return a dry-run install plan for one SCF package without modifying the workspace."""
            install_context = _get_package_install_context(package_id)
            if install_context.get("success") is False:
                return install_context

            files = install_context["files"]
            pkg_version = install_context["pkg_version"]
            min_engine_version = install_context["min_engine_version"]
            dependencies = install_context["dependencies"]
            file_policies = install_context["file_policies"]
            installed_versions = install_context["installed_versions"]
            missing_dependencies = install_context["missing_dependencies"]
            present_conflicts = install_context["present_conflicts"]
            engine_compatible = install_context["engine_compatible"]
            try:
                classification_report = _classify_install_files(
                    package_id,
                    files,
                    file_policies=file_policies,
                )
            except ValueError as exc:
                return {
                    "success": False,
                    "package": package_id,
                    "version": pkg_version,
                    "error": str(exc),
                }

            dependency_issues: list[dict[str, Any]] = []
            if not engine_compatible:
                dependency_issues.append(
                    {
                        "reason": "engine_version",
                        "required_engine_version": min_engine_version,
                        "engine_version": ENGINE_VERSION,
                    }
                )
            if missing_dependencies:
                dependency_issues.append(
                    {
                        "reason": "missing_dependencies",
                        "missing_dependencies": missing_dependencies,
                    }
                )
            if present_conflicts:
                dependency_issues.append(
                    {
                        "reason": "declared_conflicts",
                        "present_conflicts": present_conflicts,
                    }
                )

            return {
                "success": True,
                "package": package_id,
                "version": pkg_version,
                "write_plan": classification_report["write_plan"],
                "extend_plan": classification_report["extend_plan"],
                "delegate_plan": classification_report["delegate_plan"],
                "preserve_plan": classification_report["preserve_plan"],
                "conflict_plan": classification_report["conflict_plan"],
                "merge_plan": classification_report["merge_plan"],
                "dependency_issues": dependency_issues,
                "ownership_issues": classification_report["ownership_issues"],
                "installed_packages": installed_versions,
                "conflict_mode_required": classification_report["conflict_mode_required"],
                "can_install": len(dependency_issues) == 0 and len(classification_report["conflict_plan"]) == 0,
                "can_install_with_replace": len(dependency_issues) == 0 and classification_report["can_install_with_replace"],
                "supported_conflict_modes": ["abort", "replace", "manual", "auto", "assisted"],
                "engine_version": ENGINE_VERSION,
                "min_engine_version": min_engine_version,
                "dependencies": dependencies,
            }

        @self._mcp.tool()
        async def scf_remove_package(package_id: str) -> dict[str, Any]:
            """Remove an installed SCF package from the workspace.

            Deletes all files installed by the package that have not been
            modified by the user. Modified files are preserved and reported.
            """
            installed = manifest.get_installed_versions()
            if package_id not in installed:
                return {
                    "success": False,
                    "error": (
                        f"Pacchetto '{package_id}' non trovato nel manifest. "
                        "Usa scf_list_installed_packages per vedere i pacchetti installati."
                    ),
                    "package": package_id,
                }
            preserved = manifest.remove_package(package_id)
            deleted_snapshots = snapshots.delete_package_snapshots(package_id)
            return {
                "success": True,
                "package": package_id,
                "preserved_user_modified": preserved,
                "deleted_snapshots": deleted_snapshots,
            }

        @self._mcp.tool()
        async def scf_get_package_changelog(package_id: str) -> dict[str, Any]:
            """Return the changelog content for one installed SCF package."""
            content = inventory.get_package_changelog(package_id)
            if content is None:
                return {
                    "error": f"Changelog not found for package '{package_id}'.",
                    "package": package_id,
                }
            changelog_path = self._ctx.github_root / _CHANGELOGS_SUBDIR / f"{package_id}.md"
            return {
                "package": package_id,
                "path": str(changelog_path),
                "content": content,
                "version": _extract_version_from_changelog(changelog_path),
            }

        @self._mcp.tool()
        async def scf_verify_workspace() -> dict[str, Any]:
            """Verify runtime manifest integrity against files currently present in .github/."""
            report = manifest.verify_integrity()
            summary = dict(report.get("summary", {}))
            issue_count = int(summary.get("issue_count", 0))
            summary["is_clean"] = issue_count == 0
            report["summary"] = summary
            return report

        @self._mcp.tool()
        async def scf_verify_system() -> dict[str, Any]:
            """Verifica la coerenza cross-component tra motore, pacchetti e registry."""
            issues: list[dict[str, Any]] = []
            warnings: list[str] = []
            installed = manifest.get_installed_versions()

            if not installed:
                return {
                    "engine_version": ENGINE_VERSION,
                    "packages_checked": 0,
                    "issues": [],
                    "warnings": [],
                    "manifest_empty": True,
                    "is_coherent": True,
                }

            try:
                reg_packages = registry.list_packages()
            except Exception as exc:  # noqa: BLE001
                return {"success": False, "error": f"Registry non raggiungibile: {exc}"}

            reg_index = {p["id"]: p for p in reg_packages if "id" in p}

            for pkg_id, _installed_ver in installed.items():
                reg_entry = reg_index.get(pkg_id)
                if reg_entry is None:
                    warnings.append(f"Pacchetto '{pkg_id}' non trovato nel registry")
                    continue
                try:
                    pkg_manifest_data = registry.fetch_package_manifest(reg_entry["repo_url"])
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"Manifest non raggiungibile per '{pkg_id}': {exc}")
                    continue

                manifest_ver = str(pkg_manifest_data.get("version", "")).strip()
                registry_ver = str(reg_entry.get("latest_version", "")).strip()
                if manifest_ver != registry_ver:
                    issues.append({
                        "type": "registry_stale",
                        "package": pkg_id,
                        "registry_version": registry_ver,
                        "manifest_version": manifest_ver,
                        "fix": f"Aggiornare registry.json: latest_version → {manifest_ver}",
                    })

                min_engine_pkg = str(pkg_manifest_data.get("min_engine_version", "")).strip()
                min_engine_reg = str(reg_entry.get("engine_min_version", "")).strip()
                if min_engine_pkg and min_engine_reg and min_engine_pkg != min_engine_reg:
                    issues.append({
                        "type": "engine_min_mismatch",
                        "package": pkg_id,
                        "registry_engine_min": min_engine_reg,
                        "manifest_engine_min": min_engine_pkg,
                        "fix": f"Aggiornare registry.json: engine_min_version → {min_engine_pkg}",
                    })

            return {
                "engine_version": ENGINE_VERSION,
                "packages_checked": len(installed),
                "issues": issues,
                "warnings": warnings,
                "manifest_empty": False,
                "is_coherent": len(issues) == 0,
            }

        @self._mcp.tool()
        async def scf_get_runtime_state() -> dict[str, Any]:
            """Leggi lo stato runtime dell'orchestratore dal workspace corrente."""
            return inventory.get_orchestrator_state()

        @self._mcp.tool()
        async def scf_update_runtime_state(patch: dict[str, Any]) -> dict[str, Any]:
            """Aggiorna selettivamente lo stato runtime dell'orchestratore nel workspace."""
            return inventory.set_orchestrator_state(patch)

        @self._mcp.tool()
        async def scf_bootstrap_workspace(
            install_base: bool = False,
            conflict_mode: str = "abort",
        ) -> dict[str, Any]:
            """Bootstrap the base SPARK assets into this workspace and optionally install spark-base."""
            if install_base and conflict_mode not in _SUPPORTED_CONFLICT_MODES:
                return {
                    "success": False,
                    "status": "error",
                    "files_written": [],
                    "preserved": [],
                    "workspace": str(self._ctx.workspace_root),
                    "install_base_requested": install_base,
                    "conflict_mode": conflict_mode,
                    "note": (
                        f"Unsupported conflict_mode '{conflict_mode}'. "
                        "Supported modes: abort, replace, manual, auto, assisted."
                    ),
                }
            engine_github_root = Path(__file__).resolve().parent / ".github"
            prompts_source_dir = engine_github_root / "prompts"
            agent_source = engine_github_root / "agents" / "spark-assistant.agent.md"
            guide_source = engine_github_root / "instructions" / "spark-assistant-guide.instructions.md"
            workspace_github_root = self._ctx.github_root
            sentinel = workspace_github_root / "agents" / "spark-assistant.agent.md"
            sentinel_rel = "agents/spark-assistant.agent.md"

            async def _finalize_bootstrap_result(result: dict[str, Any]) -> dict[str, Any]:
                result["install_base_requested"] = install_base
                result["conflict_mode"] = conflict_mode
                if not install_base:
                    return result

                installed_versions = manifest.get_installed_versions()
                if "spark-base" in installed_versions:
                    result["base_install"] = {
                        "success": True,
                        "status": "already_installed",
                        "package": "spark-base",
                        "version": installed_versions["spark-base"],
                    }
                    result["note"] = f"{result['note']} spark-base is already installed."
                    return result

                base_install = await scf_install_package("spark-base", conflict_mode=conflict_mode)
                result["base_install"] = base_install
                if not base_install.get("success", False):
                    result["success"] = False
                    result["bootstrap_status"] = result["status"]
                    result["status"] = "base_install_failed"
                    result["note"] = (
                        "Bootstrap completed, but spark-base installation failed. "
                        f"Details: {base_install.get('error', 'unknown error')}"
                    )
                    return result

                result["bootstrap_status"] = result["status"]
                if result["status"] == "already_bootstrapped":
                    result["status"] = "already_bootstrapped_and_installed"
                    result["note"] = "Bootstrap assets already present and spark-base installed successfully."
                else:
                    result["status"] = "bootstrapped_and_installed"
                    result["note"] = "Bootstrap completed and spark-base installed successfully."
                return result

            prompt_sources = sorted(prompts_source_dir.glob("scf-*.prompt.md"))
            bootstrap_targets: list[tuple[Path, Path]] = [
                (source_path, workspace_github_root / "prompts" / source_path.name)
                for source_path in prompt_sources
            ]
            bootstrap_targets.append((agent_source, workspace_github_root / "agents" / "spark-assistant.agent.md"))
            user_guide_source = engine_github_root / "agents" / "spark-guide.agent.md"
            bootstrap_targets.append((user_guide_source, workspace_github_root / "agents" / "spark-guide.agent.md"))
            bootstrap_targets.append(
                (guide_source, workspace_github_root / "instructions" / "spark-assistant-guide.instructions.md")
            )

            # Sentinel-based idempotency gate.
            if sentinel.is_file():
                user_mod = manifest.is_user_modified(sentinel_rel)
                if user_mod is False:
                    # Tracked with matching SHA — workspace already bootstrapped.
                    return await _finalize_bootstrap_result({
                        "success": True,
                        "status": "already_bootstrapped",
                        "files_written": [],
                        "preserved": [],
                        "workspace": str(self._ctx.workspace_root),
                        "note": "Bootstrap assets already present and verified. Run /scf-list-available to inspect the package catalog.",
                    })
                if user_mod is True:
                    # Sentinel tracked but modified by user — do not overwrite.
                    return {
                        "success": True,
                        "status": "user_modified",
                        "files_written": [],
                        "preserved": [sentinel_rel],
                        "workspace": str(self._ctx.workspace_root),
                        "install_base_requested": install_base,
                        "note": "Sentinel file has been modified by user. No files overwritten.",
                    }
                # user_mod is None → sentinel exists but not tracked; fall through to copy.

            missing_sources = [
                str(source_path)
                for source_path, _ in bootstrap_targets
                if not source_path.is_file()
            ]
            if missing_sources:
                return {
                    "success": False,
                    "status": "error",
                    "files_written": [],
                    "preserved": [],
                    "workspace": str(self._ctx.workspace_root),
                    "install_base_requested": install_base,
                    "note": f"Bootstrap sources missing from engine repository: {missing_sources}",
                }

            files_written: list[str] = []
            preserved: list[str] = []
            written_paths: list[Path] = []
            identical_paths: list[Path] = []

            try:
                for source_path, dest_path in bootstrap_targets:
                    rel_path = dest_path.relative_to(self._ctx.workspace_root).as_posix()
                    if dest_path.is_file():
                        if manifest._sha256(dest_path) == manifest._sha256(source_path):
                            _log.info("Bootstrap file already matches source: %s", rel_path)
                            identical_paths.append(dest_path)
                        else:
                            _log.warning("Bootstrap file preserved (existing different content): %s", rel_path)
                            preserved.append(rel_path)
                        continue

                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_bytes(source_path.read_bytes())
                    written_paths.append(dest_path)
                    files_written.append(rel_path)
                    sys.stderr.write(
                        f"[SPARK-ENGINE][INFO] Bootstrapped: {dest_path.relative_to(workspace_github_root).as_posix()}\n"
                    )
            except OSError as exc:
                rollback_errors: list[str] = []
                for written_path in reversed(written_paths):
                    try:
                        if written_path.is_file():
                            written_path.unlink()
                    except OSError as rollback_exc:
                        rollback_errors.append(f"{written_path}: {rollback_exc}")

                rollback_note = ""
                if rollback_errors:
                    rollback_note = f" Rollback issues: {rollback_errors}"
                return {
                    "success": False,
                    "status": "error",
                    "files_written": [],
                    "preserved": preserved,
                    "workspace": str(self._ctx.workspace_root),
                    "install_base_requested": install_base,
                    "note": f"Bootstrap failed while copying files: {exc}.{rollback_note}",
                }

            if written_paths or identical_paths:
                bootstrap_manifest_targets = [
                    (dest_path.relative_to(workspace_github_root).as_posix(), dest_path)
                    for dest_path in written_paths + identical_paths
                    if not any(
                        owner != _BOOTSTRAP_PACKAGE_ID
                        for owner in manifest.get_file_owners(
                            dest_path.relative_to(workspace_github_root).as_posix()
                        )
                    )
                ]
                if bootstrap_manifest_targets:
                    manifest.upsert_many(
                        _BOOTSTRAP_PACKAGE_ID,
                        ENGINE_VERSION,
                        bootstrap_manifest_targets,
                    )
                    _save_snapshots(
                        _BOOTSTRAP_PACKAGE_ID,
                        bootstrap_manifest_targets,
                    )

            return await _finalize_bootstrap_result({
                "success": True,
                "status": "bootstrapped",
                "files_written": files_written,
                "preserved": preserved,
                "workspace": str(self._ctx.workspace_root),
                "note": "Bootstrap completed. Run /scf-list-available to inspect the package catalog.",
            })

        @self._mcp.tool()
        async def scf_resolve_conflict_ai(session_id: str, conflict_id: str) -> dict[str, Any]:
            """Proponi una risoluzione automatica conservativa per un conflitto di merge."""
            session = sessions.load_active_session(session_id)
            if session is None:
                return {
                    "success": False,
                    "error": "session_not_found",
                    "session_id": session_id,
                    "conflict_id": conflict_id,
                }

            session_status = str(session.get("status", "")).strip() or "unknown"
            if session_status != "active":
                return {
                    "success": False,
                    "error": "session_not_active",
                    "session_id": session_id,
                    "session_status": session_status,
                    "conflict_id": conflict_id,
                }

            resolution = _propose_conflict_resolution(session, conflict_id)
            if resolution.get("error") == "conflict_not_found":
                return {
                    "success": False,
                    "error": "conflict_not_found",
                    "session_id": session_id,
                    "conflict_id": conflict_id,
                }

            return {
                "success": bool(resolution.get("success", False)),
                "session_id": session_id,
                "conflict_id": conflict_id,
                "proposed_text": resolution.get("proposed_text"),
                "validator_results": resolution.get("validator_results"),
                "resolution_status": resolution.get("resolution_status", "manual"),
                "fallback": resolution.get("fallback"),
                "reason": resolution.get("reason"),
            }

        @self._mcp.tool()
        async def scf_approve_conflict(session_id: str, conflict_id: str) -> dict[str, Any]:
            """Approva e scrivi nel workspace una proposta gia' validata per un conflitto."""
            session = sessions.load_active_session(session_id)
            if session is None:
                return {
                    "success": False,
                    "error": "session_not_found",
                    "session_id": session_id,
                    "conflict_id": conflict_id,
                }

            session_status = str(session.get("status", "")).strip() or "unknown"
            if session_status != "active":
                return {
                    "success": False,
                    "error": "session_not_active",
                    "session_id": session_id,
                    "session_status": session_status,
                    "conflict_id": conflict_id,
                }

            found = _find_session_entry(session, conflict_id)
            if found is None:
                return {
                    "success": False,
                    "error": "conflict_not_found",
                    "session_id": session_id,
                    "conflict_id": conflict_id,
                }

            index, file_entry = found
            proposed_text = file_entry.get("proposed_text")
            if not isinstance(proposed_text, str) or not proposed_text:
                return {
                    "success": False,
                    "error": "proposed_text_missing",
                    "session_id": session_id,
                    "conflict_id": conflict_id,
                }

            validator_results = file_entry.get("validator_results")
            if not isinstance(validator_results, dict):
                validator_results = run_post_merge_validators(
                    proposed_text,
                    str(file_entry.get("base_text", "") or ""),
                    str(file_entry.get("ours_text", "") or ""),
                    str(file_entry.get("file", file_entry.get("workspace_path", "")) or ""),
                )
            if not validator_results.get("passed", False):
                file_entry["validator_results"] = validator_results
                file_entry["resolution_status"] = "manual"
                _replace_session_entry(session, index, file_entry)
                sessions.save_session(session)
                return {
                    "success": False,
                    "error": "validator_failed",
                    "session_id": session_id,
                    "conflict_id": conflict_id,
                    "validator_results": validator_results,
                }

            workspace_path = str(file_entry.get("workspace_path", "")).strip()
            dest = self._ctx.workspace_root / workspace_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(proposed_text, encoding="utf-8")

            file_entry["validator_results"] = validator_results
            file_entry["resolution_status"] = "approved"
            _replace_session_entry(session, index, file_entry)
            sessions.save_session(session)

            return {
                "success": True,
                "session_id": session_id,
                "conflict_id": conflict_id,
                "approved": True,
                "remaining_conflicts": _count_remaining_conflicts(session),
            }

        @self._mcp.tool()
        async def scf_reject_conflict(session_id: str, conflict_id: str) -> dict[str, Any]:
            """Rifiuta una proposta e mantiene il file in fallback manuale con marker."""
            session = sessions.load_active_session(session_id)
            if session is None:
                return {
                    "success": False,
                    "error": "session_not_found",
                    "session_id": session_id,
                    "conflict_id": conflict_id,
                }

            session_status = str(session.get("status", "")).strip() or "unknown"
            if session_status != "active":
                return {
                    "success": False,
                    "error": "session_not_active",
                    "session_id": session_id,
                    "session_status": session_status,
                    "conflict_id": conflict_id,
                }

            found = _find_session_entry(session, conflict_id)
            if found is None:
                return {
                    "success": False,
                    "error": "conflict_not_found",
                    "session_id": session_id,
                    "conflict_id": conflict_id,
                }

            index, file_entry = found
            marker_text = _render_marker_text(file_entry)
            workspace_path = str(file_entry.get("workspace_path", "")).strip()
            dest = self._ctx.workspace_root / workspace_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(marker_text, encoding="utf-8")

            file_entry["resolution_status"] = "rejected"
            _replace_session_entry(session, index, file_entry)
            sessions.save_session(session)

            return {
                "success": True,
                "session_id": session_id,
                "conflict_id": conflict_id,
                "rejected": True,
                "fallback": "manual",
                "remaining_conflicts": _count_remaining_conflicts(session),
            }

        @self._mcp.tool()
        async def scf_finalize_update(session_id: str) -> dict[str, Any]:
            """Finalize a manual merge session after the user resolves all conflict markers."""
            session = sessions.load_active_session(session_id)
            if session is None:
                return {
                    "success": False,
                    "error": f"Merge session '{session_id}' not found.",
                    "session_id": session_id,
                }

            session_status = str(session.get("status", "")).strip() or "unknown"
            if session_status != "active":
                return {
                    "success": False,
                    "error": f"Merge session '{session_id}' is not active.",
                    "session_id": session_id,
                    "session_status": session_status,
                }

            package_id = str(session.get("package", "")).strip()
            package_version = str(session.get("package_version", "")).strip()
            pending: list[dict[str, Any]] = []
            written_files: list[str] = []
            manifest_targets: list[tuple[str, Path]] = []
            validator_results_map: dict[str, Any] = {}
            updated_session = dict(session)
            updated_files = list(updated_session.get("files", []))

            for index, file_entry in enumerate(list(session.get("files", []))):
                workspace_path = str(file_entry.get("workspace_path", "")).strip()
                manifest_rel = str(file_entry.get("manifest_rel", "")).strip()
                public_file = str(file_entry.get("file", workspace_path)).strip()
                dest = self._ctx.workspace_root / workspace_path
                if not dest.is_file():
                    pending.append({
                        "file": public_file,
                        "reason": "missing_file",
                    })
                    continue
                content = _read_text_if_possible(dest)
                if content is None:
                    pending.append({
                        "file": public_file,
                        "reason": "unreadable_text",
                    })
                    continue
                if merge_engine.has_conflict_markers(content):
                    pending.append({
                        "file": public_file,
                        "reason": "conflict_markers_present",
                    })
                    continue

                if isinstance(file_entry.get("validator_results"), dict):
                    validator_results_map[public_file] = file_entry["validator_results"]

                updated_file_entry = dict(file_entry)
                updated_file_entry["resolution_status"] = "approved"
                updated_files[index] = MergeSessionManager._normalize_session_file_entry(updated_file_entry)
                written_files.append(public_file)
                manifest_targets.append((manifest_rel, dest))

            if pending:
                return {
                    "success": False,
                    "error": "Manual merge session still has unresolved files.",
                    "session_id": session_id,
                    "session_status": session_status,
                    "manual_pending": pending,
                }

            manifest.upsert_many(package_id, package_version, manifest_targets)
            snapshot_report = _save_snapshots(package_id, manifest_targets)
            updated_session["files"] = updated_files
            finalized_session = sessions.mark_status(session_id, "finalized", session=updated_session)
            return {
                "success": True,
                "session_id": session_id,
                "session_status": None if finalized_session is None else finalized_session.get("status"),
                "written_files": written_files,
                "manifest_updated": [manifest_rel for manifest_rel, _ in manifest_targets],
                "snapshot_updated": snapshot_report["written"],
                "snapshot_skipped": snapshot_report["skipped"],
                "manual_pending": [],
                "validator_results": validator_results_map,
            }

        _log.info("Tools registered: 33 total")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _build_app() -> FastMCP:
    mcp: FastMCP = FastMCP("sparkFrameworkEngine")

    locator = WorkspaceLocator()
    context = locator.resolve()
    _log.info("Workspace resolved: %s", context.workspace_root)

    inventory = FrameworkInventory(context)
    _log.info(
        "Framework inventory: %d agents, %d skills, %d instructions, %d prompts",
        len(inventory.list_agents()), len(inventory.list_skills()),
        len(inventory.list_instructions()), len(inventory.list_prompts()),
    )

    app = SparkFrameworkEngine(mcp, context, inventory)
    app.register_resources()
    app.register_tools()

    return mcp


if __name__ == "__main__":
    _build_app().run(transport="stdio")
