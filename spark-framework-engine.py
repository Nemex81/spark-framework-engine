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
import shutil
import sys
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar

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

ENGINE_VERSION: str = "3.0.0"


# ---------------------------------------------------------------------------
# Changelogs directory
# ---------------------------------------------------------------------------
_CHANGELOGS_SUBDIR: str = "changelogs"
_SNAPSHOTS_SUBDIR: str = "runtime/snapshots"
_MERGE_SESSIONS_SUBDIR: str = "runtime/merge-sessions"
_BACKUPS_SUBDIR: str = "runtime/backups"
_USER_PREFS_FILENAME: str = "runtime/spark-user-prefs.json"
_ALLOWED_UPDATE_MODES: frozenset[str] = frozenset(
    {"ask", "integrative", "replace", "conservative", "selective"}
)

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

        prefix_len = self._shared_prefix_len_threeway(base_lines, ours_lines, theirs_lines)
        suffix_len = self._shared_suffix_len_threeway(
            base_lines,
            ours_lines,
            theirs_lines,
            prefix_len,
        )
        ours_end = len(ours_lines) - suffix_len if suffix_len else len(ours_lines)
        theirs_end = len(theirs_lines) - suffix_len if suffix_len else len(theirs_lines)
        base_end = len(base_lines) - suffix_len if suffix_len else len(base_lines)

        prefix_text = "".join(ours_lines[:prefix_len])
        suffix_text = "".join(ours_lines[len(ours_lines) - suffix_len :]) if suffix_len else ""

        base_start = prefix_len

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

    @classmethod
    def _shared_prefix_len_threeway(
        cls,
        base_lines: list[str],
        ours_lines: list[str],
        theirs_lines: list[str],
    ) -> int:
        return min(
            cls._shared_prefix_len(base_lines, ours_lines),
            cls._shared_prefix_len(base_lines, theirs_lines),
            cls._shared_prefix_len(ours_lines, theirs_lines),
        )

    @staticmethod
    def _shared_suffix_len(left: list[str], right: list[str], prefix_len: int) -> int:
        max_suffix = min(len(left), len(right)) - prefix_len
        index = 0
        while index < max_suffix and left[-(index + 1)] == right[-(index + 1)]:
            index += 1
        return index

    @classmethod
    def _shared_suffix_len_threeway(
        cls,
        base_lines: list[str],
        ours_lines: list[str],
        theirs_lines: list[str],
        prefix_len: int,
    ) -> int:
        return min(
            cls._shared_suffix_len(base_lines, ours_lines, prefix_len),
            cls._shared_suffix_len(base_lines, theirs_lines, prefix_len),
            cls._shared_suffix_len(ours_lines, theirs_lines, prefix_len),
        )


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


def _default_update_policy() -> dict[str, Any]:
    """Return the canonical workspace update policy defaults."""
    return {
        "auto_update": False,
        "default_mode": "ask",
        "mode_per_package": {},
        "mode_per_file_role": {},
        "last_changed": "",
        "changed_by_user": False,
    }


def _default_update_policy_payload() -> dict[str, Any]:
    """Wrap the default update policy in the persisted JSON payload shape."""
    return {"update_policy": _default_update_policy()}


def _update_policy_path(github_root: Path) -> Path:
    """Return the persisted workspace update policy path."""
    return github_root / _USER_PREFS_FILENAME


def _normalize_update_mode(mode: str) -> str:
    """Normalize an update mode token for validation and storage."""
    return mode.strip().lower()


def _validate_update_mode(mode: str, *, allow_selective: bool) -> str | None:
    """Validate and normalize one update mode token."""
    normalized = _normalize_update_mode(mode)
    if normalized not in _ALLOWED_UPDATE_MODES:
        return None
    if not allow_selective and normalized == "selective":
        return None
    return normalized


def _normalize_manifest_relative_path(path_value: str) -> str | None:
    """Normalize a package path to the manifest-relative form under .github/."""
    normalized = path_value.replace("\\", "/").strip()
    if not normalized:
        return None
    if normalized.startswith(".github/"):
        normalized = normalized[len(".github/") :]
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        return None

    candidate = PurePosixPath(normalized)
    parts = candidate.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return None
    return candidate.as_posix()


def _infer_scf_file_role(path_value: str) -> str:
    """Infer a default SCF file role from its package-relative path."""
    normalized = path_value.replace("\\", "/")
    if "/agents/" in f"/{normalized}" or normalized.endswith(".agent.md"):
        return "agent"
    if "/instructions/" in f"/{normalized}" or normalized.endswith(".instructions.md"):
        return "instruction"
    if "/skills/" in f"/{normalized}" or normalized.endswith("/SKILL.md") or normalized.endswith(".skill.md"):
        return "skill"
    if "/prompts/" in f"/{normalized}" or normalized.endswith(".prompt.md"):
        return "prompt"
    return "config"


def _read_update_policy_payload(github_root: Path) -> tuple[dict[str, Any], str]:
    """Load the workspace update policy, falling back to defaults when missing or invalid."""
    policy_path = _update_policy_path(github_root)
    if not policy_path.is_file():
        return _default_update_policy_payload(), "default_missing"

    try:
        raw_payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning("spark-user-prefs.json unreadable, using defaults: %s", exc)
        return _default_update_policy_payload(), "default_corrupt"

    if not isinstance(raw_payload, dict):
        return _default_update_policy_payload(), "default_invalid"

    raw_policy = raw_payload.get("update_policy", raw_payload)
    if not isinstance(raw_policy, dict):
        return _default_update_policy_payload(), "default_invalid"

    policy = _default_update_policy()
    if isinstance(raw_policy.get("auto_update"), bool):
        policy["auto_update"] = raw_policy["auto_update"]

    default_mode = raw_policy.get("default_mode")
    if isinstance(default_mode, str):
        validated_mode = _validate_update_mode(default_mode, allow_selective=False)
        if validated_mode is not None:
            policy["default_mode"] = validated_mode

    mode_per_package = raw_policy.get("mode_per_package")
    if isinstance(mode_per_package, dict):
        policy["mode_per_package"] = {
            str(key).strip(): normalized_mode
            for key, value in mode_per_package.items()
            if str(key).strip()
            for normalized_mode in [_validate_update_mode(str(value), allow_selective=True)]
            if normalized_mode is not None
        }

    mode_per_file_role = raw_policy.get("mode_per_file_role")
    if isinstance(mode_per_file_role, dict):
        policy["mode_per_file_role"] = {
            str(key).strip(): normalized_mode
            for key, value in mode_per_file_role.items()
            if str(key).strip()
            for normalized_mode in [_validate_update_mode(str(value), allow_selective=True)]
            if normalized_mode is not None
        }

    last_changed = raw_policy.get("last_changed")
    if isinstance(last_changed, str):
        policy["last_changed"] = last_changed.strip()

    changed_by_user = raw_policy.get("changed_by_user")
    if isinstance(changed_by_user, bool):
        policy["changed_by_user"] = changed_by_user

    return {"update_policy": policy}, "file"


def _write_update_policy_payload(github_root: Path, payload: dict[str, Any]) -> Path:
    """Persist the workspace update policy payload to disk."""
    policy_path = _update_policy_path(github_root)
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return policy_path


# ---------------------------------------------------------------------------
# WorkspaceLocator
# ---------------------------------------------------------------------------


class WorkspaceLocator:
    """Resolve the active workspace using env, local config and SCF markers."""

    OVERRIDE_RESOURCE_TYPES: ClassVar[tuple[str, ...]] = (
        "agents",
        "prompts",
        "skills",
        "instructions",
    )

    @staticmethod
    def get_engine_cache_dir(engine_dir: Path) -> Path:
        """Return a writable cache directory for the engine.

        Prefer ``engine_dir/cache/``; fall back to a per-user location
        (``%APPDATA%\\spark-engine\\cache`` on Windows, ``~/.cache/spark-engine``
        otherwise) when the engine directory is not writable.
        Creates the directory if missing.
        """
        primary = engine_dir / "cache"
        try:
            primary.mkdir(parents=True, exist_ok=True)
            probe = primary / ".write-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return primary
        except OSError:
            _log.warning(
                "Engine cache dir not writable (%s); using per-user fallback",
                primary,
            )

        if os.name == "nt":
            base_str = os.environ.get("APPDATA") or os.path.expanduser("~")
            fallback = Path(base_str) / "spark-engine" / "cache"
        else:
            fallback = Path(os.path.expanduser("~/.cache/spark-engine"))

        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    @staticmethod
    def get_override_dir(
        workspace: Path,
        resource_type: str,
        github_write_authorized: bool = True,
    ) -> Path:
        """Return ``workspace/.github/overrides/{resource_type}/``.

        Creates the directory only when ``github_write_authorized`` is True.
        Raises ValueError on unknown resource types.
        """
        if resource_type not in WorkspaceLocator.OVERRIDE_RESOURCE_TYPES:
            raise ValueError(
                f"Unknown override resource type: {resource_type!r}"
            )
        target = workspace / ".github" / "overrides" / resource_type
        if github_write_authorized:
            target.mkdir(parents=True, exist_ok=True)
        return target

    @staticmethod
    def _parse_workspace_flag(argv: list[str] | None = None) -> str | None:
        """Return the value of ``--workspace`` from argv if present.

        Accepts ``--workspace VALUE`` or ``--workspace=VALUE``.
        """
        args = list(sys.argv[1:] if argv is None else argv)
        i = 0
        while i < len(args):
            token = args[i]
            if token == "--workspace":
                if i + 1 < len(args):
                    return args[i + 1]
                return None
            if token.startswith("--workspace="):
                return token.split("=", 1)[1]
            i += 1
        return None

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
        workspace_root: Path | None = None

        cli_value = self._parse_workspace_flag()
        if cli_value:
            cli_candidate = Path(cli_value).expanduser().resolve()
            if not cli_candidate.is_dir():
                _log.warning(
                    "Ignoring --workspace because it is not a directory: %s",
                    cli_candidate,
                )
            else:
                workspace_root = cli_candidate
                _log.info("Workspace resolved via --workspace: %s", workspace_root)

        workspace_root_str: str | None = (
            None if workspace_root is not None else os.environ.get("WORKSPACE_FOLDER")
        )

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


# ---------------------------------------------------------------------------
# FrameworkInventory
# ---------------------------------------------------------------------------


class FrameworkInventory:
    """Discover framework files under .github/ and scripts/ dynamically."""

    def __init__(self, context: WorkspaceContext) -> None:
        self._ctx = context
        # mcp_registry / resource_store sono popolati on-demand da
        # populate_mcp_registry(); rimangono None fino a quel momento per
        # mantenere il costo del costruttore minimo (compatibilità v2.x).
        self.mcp_registry: McpResourceRegistry | None = None
        self.resource_store: PackageResourceStore | None = None

    def populate_mcp_registry(
        self,
        engine_manifest: Mapping[str, Any] | None = None,
        package_manifests: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> "McpResourceRegistry":
        """Costruisce e popola ``self.mcp_registry`` con risorse engine + pacchetti.

        Parametri:
            engine_manifest: contenuto di ``engine-manifest.json`` (engine root).
            package_manifests: dict ``{package_id: manifest_dict}`` per i
                pacchetti i cui file vivono nel deposito centralizzato
                ``engine_dir/packages/{pkg}/.github/...``.

        Dopo aver registrato le risorse engine+pacchetti, esegue uno scan
        di ``workspace/.github/overrides/{type}/`` e applica gli override
        trovati al registry.
        """
        registry = McpResourceRegistry()
        store = PackageResourceStore(self._ctx.engine_root)
        self.mcp_registry = registry
        self.resource_store = store

        # 1) Risorse engine-proprie (engine-manifest.json)
        if engine_manifest:
            self._register_engine_resources(registry, engine_manifest)

        # 2) Risorse dei pacchetti (deposito centralizzato)
        if package_manifests:
            for package_id, manifest in package_manifests.items():
                self._register_package_resources(
                    registry, store, package_id, manifest
                )

        # 3) Override del workspace
        self._scan_workspace_overrides(registry)

        return registry

    def _register_engine_resources(
        self,
        registry: "McpResourceRegistry",
        engine_manifest: Mapping[str, Any],
    ) -> None:
        engine_root = self._ctx.engine_root
        resources = engine_manifest.get("mcp_resources") or {}
        if not isinstance(resources, Mapping):
            return
        package_id = str(engine_manifest.get("package", "spark-framework-engine"))
        for resource_type in _RESOURCE_TYPES:
            names = resources.get(resource_type) or []
            if not isinstance(names, list):
                continue
            for name in names:
                path = self._find_engine_resource_path(
                    engine_root, resource_type, str(name)
                )
                if path is None:
                    continue
                uri = McpResourceRegistry.make_uri(resource_type, str(name))
                registry.register(uri, path, package_id, resource_type)

    def _find_engine_resource_path(
        self, engine_root: Path, resource_type: str, name: str
    ) -> Path | None:
        base = engine_root / ".github" / resource_type
        if not base.is_dir():
            return None
        for candidate in _resource_filename_candidates(resource_type, name):
            target = base / candidate
            if target.is_file():
                return target.resolve()
        return None

    def _register_package_resources(
        self,
        registry: "McpResourceRegistry",
        store: "PackageResourceStore",
        package_id: str,
        manifest: Mapping[str, Any],
    ) -> None:
        resources = manifest.get("mcp_resources") or {}
        if not isinstance(resources, Mapping):
            return
        for resource_type in _RESOURCE_TYPES:
            names = resources.get(resource_type) or []
            if not isinstance(names, list):
                continue
            for name in names:
                path = store.resolve(package_id, resource_type, str(name))
                if path is None:
                    continue
                uri = McpResourceRegistry.make_uri(resource_type, str(name))
                registry.register(uri, path, package_id, resource_type)

    def _scan_workspace_overrides(self, registry: "McpResourceRegistry") -> None:
        overrides_root = self._ctx.github_root / "overrides"
        if not overrides_root.is_dir():
            return
        for resource_type in _RESOURCE_TYPES:
            type_dir = overrides_root / resource_type
            if not type_dir.is_dir():
                continue
            for child in type_dir.iterdir():
                name = self._override_name_from_path(resource_type, child)
                if name is None:
                    continue
                uri = McpResourceRegistry.make_uri(resource_type, name)
                registry.register_override(uri, child)

    @staticmethod
    def _override_name_from_path(resource_type: str, path: Path) -> str | None:
        if resource_type == "agents":
            if path.is_file() and path.name.endswith(".agent.md"):
                return path.name[: -len(".agent.md")]
            if path.is_file() and path.name.endswith(".md"):
                return path.name[: -len(".md")]
            return None
        if resource_type == "prompts":
            if path.is_file() and path.name.endswith(".prompt.md"):
                return path.name[: -len(".prompt.md")]
            return None
        if resource_type == "instructions":
            if path.is_file() and path.name.endswith(".instructions.md"):
                return path.name[: -len(".instructions.md")]
            return None
        if resource_type == "skills":
            if path.is_file() and path.name.endswith(".skill.md"):
                return path.name[: -len(".skill.md")]
            if path.is_dir() and (path / "SKILL.md").is_file():
                return path.name
            return None
        return None

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
# EngineInventory (v2.4.0 — engine-hosted skills and instructions)
# ---------------------------------------------------------------------------


class EngineInventory(FrameworkInventory):
    """Discover skills/instructions under the engine's own ``.github/`` tree.

    The engine ships a curated set of universal skills and instructions that
    are hosted centrally and consumed by workspaces via dedicated MCP
    resource URIs (``engine-skills://``, ``engine-instructions://``). Unlike
    :class:`FrameworkInventory`, this inventory does NOT read from the user
    workspace: it reads from ``Path(__file__).resolve().parent / ".github"``.

    Starting with engine v3.0 it also loads ``engine-manifest.json`` from the
    engine root (next to ``spark-framework-engine.py``) and exposes its
    contents via :attr:`engine_manifest`. The manifest declares the engine's
    own ``workspace_files`` (Copilot-loaded instructions) and ``mcp_resources``
    (MCP-only agents/instructions/prompts/skills owned by the engine itself).
    """

    ENGINE_MANIFEST_FILENAME: ClassVar[str] = "engine-manifest.json"

    def __init__(self) -> None:  # noqa: D401 - simple override
        engine_root = Path(__file__).resolve().parent
        engine_github_root = engine_root / ".github"
        synthetic_ctx = WorkspaceContext(
            workspace_root=engine_root,
            github_root=engine_github_root,
            engine_root=engine_root,
        )
        super().__init__(synthetic_ctx)
        self.engine_manifest: dict[str, Any] = self._load_engine_manifest(engine_root)

    def _load_engine_manifest(self, engine_root: Path) -> dict[str, Any]:
        """Load ``engine-manifest.json`` from the engine root.

        Returns an empty dict (with a logged warning) when the file is
        missing or unreadable, so the engine can still boot during the
        v2.x → v3.0 migration window.
        """
        manifest_path = engine_root / self.ENGINE_MANIFEST_FILENAME
        if not manifest_path.is_file():
            _log.warning(
                "engine-manifest.json non trovato in %s — fallback a manifest vuoto",
                engine_root,
            )
            return {}
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _log.warning(
                "Impossibile leggere engine-manifest.json (%s): %s",
                manifest_path, exc,
            )
            return {}
        if not isinstance(data, dict):
            _log.warning(
                "engine-manifest.json non è un oggetto JSON: %s",
                type(data).__name__,
            )
            return {}
        return data

    def get_engine_workspace_files(self) -> list[str]:
        """Return the list of engine-owned workspace files (Copilot-loaded)."""
        files = self.engine_manifest.get("workspace_files", [])
        return [str(f) for f in files] if isinstance(files, list) else []

    def get_engine_mcp_resources(self) -> dict[str, list[str]]:
        """Return the engine-owned MCP resource lists by type."""
        resources = self.engine_manifest.get("mcp_resources", {})
        if not isinstance(resources, dict):
            return {"agents": [], "instructions": [], "prompts": [], "skills": []}
        out: dict[str, list[str]] = {}
        for key in ("agents", "instructions", "prompts", "skills"):
            value = resources.get(key, [])
            out[key] = [str(v) for v in value] if isinstance(value, list) else []
        return out


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

_MANIFEST_SCHEMA_VERSION: str = "3.0"
_SUPPORTED_MANIFEST_SCHEMA_VERSIONS: frozenset[str] = frozenset(
    {"1.0", "2.0", "2.1", "3.0"}
)
_LEGACY_MANIFEST_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0", "2.0", "2.1"})
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


def _get_registry_min_engine_version(package_entry: Mapping[str, Any]) -> str:
    """Return the canonical registry minimum engine version, accepting the legacy key."""
    return str(
        package_entry.get("min_engine_version", package_entry.get("engine_min_version", ""))
    ).strip()


def _build_registry_package_summary(package_entry: Mapping[str, Any]) -> dict[str, Any]:
    """Build the public summary payload for one registry package entry."""
    return {
        "id": package_entry.get("id"),
        "description": package_entry.get("description", ""),
        "latest_version": package_entry.get("latest_version", ""),
        "status": package_entry.get("status", "unknown"),
        "repo_url": package_entry.get("repo_url", ""),
        "min_engine_version": _get_registry_min_engine_version(package_entry),
    }


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
        """Persist entries to disk.

        Schema v3.0: emits an explicit ``overrides[]`` summary derived from
        entries tagged with ``override_type`` so external readers can locate
        workspace overrides without scanning every entry.
        """
        overrides_summary = self._build_overrides_summary(entries)
        payload: dict[str, Any] = {
            "schema_version": _MANIFEST_SCHEMA_VERSION,
            "entries": entries,
            "overrides": overrides_summary,
        }
        try:
            self._path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            _log.error("Cannot write manifest: %s", exc)
            raise

    @staticmethod
    def _build_overrides_summary(
        entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return ``[{type, name, file, sha256}, ...]`` for override entries."""
        out: list[dict[str, Any]] = []
        for entry in entries:
            override_type = str(entry.get("override_type", "")).strip()
            override_name = str(entry.get("override_name", "")).strip()
            if not override_type or not override_name:
                continue
            out.append(
                {
                    "type": override_type,
                    "name": override_name,
                    "file": str(entry.get("file", "")),
                    "sha256": str(entry.get("sha256", "")),
                }
            )
        out.sort(key=lambda item: (item["type"], item["name"]))
        return out

    def upsert(
        self,
        file_rel: str,
        package: str,
        package_version: str,
        file_abs: Path,
        merge_strategy: str | None = None,
    ) -> None:
        """Add or update the manifest entry for a single installed file."""
        entries = self.load()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entries = [
            e
            for e in entries
            if not (e.get("file") == file_rel and e.get("package") == package)
        ]
        new_entry = self._build_entry(
            file_rel,
            package,
            package_version,
            file_abs,
            now,
            self._resolve_entry_merge_strategy(entries, file_rel, package, merge_strategy),
        )
        entries.append(new_entry)
        self._sync_entries_for_files(entries, {file_rel: file_abs})
        self.save(entries)

    def remove_package(self, package: str) -> list[str]:
        """Remove a package's entries and delete unmodified files on disk.

        Returns the list of relative paths preserved because the user modified them.
        """
        entries = self.load()
        preserved: list[str] = []
        remaining: list[dict[str, Any]] = []
        updated_files: dict[str, Path] = {}
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
                                    updated_files[str(entry["file"])] = file_path
                                    _log.info(
                                        "[SPARK-ENGINE][INFO] Removed package section for user-modified shared file: %s",
                                        file_path,
                                    )
                            else:
                                file_path.write_text(updated_text, encoding="utf-8")
                                updated_files[str(entry["file"])] = file_path
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
        self._sync_entries_for_files(remaining, updated_files)
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
        merge_strategies_by_file: dict[str, str] | None = None,
        stub_files: set[str] | None = None,
    ) -> None:
        """Add or update manifest entries for many installed files in one save.

        When ``stub_files`` is provided, every file_rel listed in the set is
        persisted with ``stub: true`` in the manifest entry. Callers compute
        the set from the package manifest's ``engine_provided_skills`` and
        ``engine_provided_instructions`` fields.
        """
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
        files_by_rel = dict(files)
        stub_lookup = stub_files or set()
        for file_rel, file_abs in files:
            requested_strategy = None
            if merge_strategies_by_file is not None:
                requested_strategy = merge_strategies_by_file.get(file_rel)
            entries.append(
                self._build_entry(
                    file_rel,
                    package,
                    package_version,
                    file_abs,
                    now,
                    self._resolve_entry_merge_strategy(
                        entries,
                        file_rel,
                        package,
                        requested_strategy,
                    ),
                    stub=file_rel in stub_lookup,
                )
            )
        self._sync_entries_for_files(entries, files_by_rel)
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
        entries_by_file: dict[str, list[dict[str, Any]]] = {}

        for entry in entries:
            file_rel = str(entry.get("file", "")).strip()
            package_id = str(entry.get("package", "")).strip()
            if not file_rel:
                continue
            tracked_files.add(file_rel)
            entries_by_file.setdefault(file_rel, []).append(entry)
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
            and not self._entries_allow_shared_merge_sections(entries_by_file.get(file_rel, []))
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

    @staticmethod
    def _normalize_merge_strategy(value: Any) -> str:
        strategy = str(value).strip()
        return strategy or "replace"

    def _resolve_entry_merge_strategy(
        self,
        entries: list[dict[str, Any]],
        file_rel: str,
        package: str,
        requested_strategy: str | None,
    ) -> str:
        if requested_strategy is not None:
            return self._normalize_merge_strategy(requested_strategy)

        for entry in entries:
            if (
                str(entry.get("file", "")).strip() == file_rel
                and str(entry.get("package", "")).strip() == package
            ):
                raw_strategy = str(entry.get("scf_merge_strategy", "")).strip()
                if raw_strategy:
                    return self._normalize_merge_strategy(raw_strategy)

        for entry in entries:
            if str(entry.get("file", "")).strip() == file_rel:
                raw_strategy = str(entry.get("scf_merge_strategy", "")).strip()
                if raw_strategy:
                    return self._normalize_merge_strategy(raw_strategy)

        return "replace"

    def _build_entry(
        self,
        file_rel: str,
        package: str,
        package_version: str,
        file_abs: Path,
        installed_at: str,
        merge_strategy: str,
        stub: bool = False,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "file": file_rel,
            "package": package,
            "package_version": package_version,
            "installed_at": installed_at,
            "sha256": self._sha256(file_abs),
            "scf_merge_strategy": self._normalize_merge_strategy(merge_strategy),
        }
        if stub:
            entry["stub"] = True
        return entry

    def _sync_entries_for_files(
        self,
        entries: list[dict[str, Any]],
        files_by_rel: dict[str, Path],
    ) -> None:
        for file_rel, file_abs in files_by_rel.items():
            if not file_rel:
                continue
            sha256 = self._sha256(file_abs)
            related_entries = [
                entry
                for entry in entries
                if str(entry.get("file", "")).strip() == file_rel
            ]
            if not related_entries:
                continue

            uses_shared_merge = any(
                self._normalize_merge_strategy(entry.get("scf_merge_strategy")) == "merge_sections"
                for entry in related_entries
            )
            for entry in related_entries:
                entry["sha256"] = sha256
                if uses_shared_merge:
                    entry["scf_merge_strategy"] = "merge_sections"

    def _entries_allow_shared_merge_sections(self, entries: list[dict[str, Any]]) -> bool:
        owners = {
            str(entry.get("package", "")).strip()
            for entry in entries
            if str(entry.get("package", "")).strip()
        }
        if len(owners) < 2:
            return False
        return all(
            self._normalize_merge_strategy(entry.get("scf_merge_strategy")) == "merge_sections"
            for entry in entries
            if str(entry.get("package", "")).strip()
        )

    # ------------------------------------------------------------------
    # Override management (v3.0)
    # ------------------------------------------------------------------

    def _override_path(self, resource_type: str, name: str) -> Path:
        from_map = {
            "agents": f"{name}.agent.md",
            "prompts": f"{name}.prompt.md",
            "instructions": f"{name}.instructions.md",
            "skills": f"{name}.skill.md",
        }
        filename = from_map.get(resource_type)
        if filename is None:
            raise ValueError(f"Tipo risorsa non supportato: {resource_type}")
        return self._github_root / "overrides" / resource_type / filename

    def write_override(
        self,
        resource_type: str,
        name: str,
        content: str,
    ) -> Path:
        """Scrive un override workspace e registra l'entry nel manifest.

        Lancia ``ValueError`` se ``resource_type`` non e' supportato.
        Lancia ``OSError`` se la scrittura fallisce.
        """
        target = self._override_path(resource_type, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        rel = target.relative_to(self._github_root).as_posix()
        sha = _sha256_text(content)
        entries = self.load()
        entries = [e for e in entries if e.get("file") != rel]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entries.append({
            "file": rel,
            "package": "__workspace_override__",
            "package_version": "0.0.0",
            "installed_at": now,
            "sha256": sha,
            "scf_merge_strategy": "single_owner",
            "scf_owner": "__workspace_override__",
            "override_type": resource_type,
            "override_name": name,
        })
        self.save(entries)
        return target

    def drop_override(self, resource_type: str, name: str) -> bool:
        """Rimuove un override workspace e relativa entry manifest.

        Ritorna ``True`` se il file e' stato rimosso, ``False`` se assente.
        """
        target = self._override_path(resource_type, name)
        rel = target.relative_to(self._github_root).as_posix()
        existed = target.is_file()
        if existed:
            try:
                target.unlink()
            except OSError as exc:
                _log.warning("Impossibile rimuovere override %s: %s", target, exc)
                raise
        entries = self.load()
        new_entries = [e for e in entries if e.get("file") != rel]
        if len(new_entries) != len(entries):
            self.save(new_entries)
        return existed


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


def _normalize_remote_file_record(
    package_id: str,
    version: str,
    remote_file: dict[str, Any],
) -> dict[str, Any] | None:
    """Normalize one incoming package file record for diff classification."""
    raw_path = str(remote_file.get("path", remote_file.get("file", ""))).strip()
    manifest_rel = _normalize_manifest_relative_path(raw_path)
    if manifest_rel is None:
        return None

    incoming_sha256 = str(remote_file.get("sha256", "")).strip()
    if not incoming_sha256 and isinstance(remote_file.get("content"), str):
        incoming_sha256 = _sha256_text(remote_file["content"])

    public_file = f".github/{manifest_rel}"
    return {
        "file": public_file,
        "manifest_rel": manifest_rel,
        "package": package_id,
        "package_version": version,
        "scf_owner": str(remote_file.get("scf_owner", package_id)).strip() or package_id,
        "scf_version": str(remote_file.get("scf_version", version)).strip() or version,
        "scf_file_role": str(
            remote_file.get("scf_file_role", _infer_scf_file_role(manifest_rel))
        ).strip()
        or _infer_scf_file_role(manifest_rel),
        "scf_merge_strategy": str(remote_file.get("scf_merge_strategy", "replace")).strip()
        or "replace",
        "scf_merge_priority": int(remote_file.get("scf_merge_priority", 0) or 0),
        "scf_protected": bool(remote_file.get("scf_protected", False)),
        "incoming_sha256": incoming_sha256,
    }


def _scf_diff_workspace(
    package_id: str,
    version: str,
    remote_files: list[dict[str, Any]],
    manifest: ManifestManager,
) -> list[dict[str, Any]]:
    """Classify incoming package files against the current workspace state."""
    diff_records: list[dict[str, Any]] = []
    for remote_file in remote_files:
        normalized_record = _normalize_remote_file_record(package_id, version, remote_file)
        if normalized_record is None:
            continue

        manifest_rel = str(normalized_record["manifest_rel"])
        file_abs = manifest._github_root / manifest_rel
        exists = file_abs.is_file()
        current_sha256 = manifest._sha256(file_abs) if exists else ""
        incoming_sha256 = str(normalized_record.get("incoming_sha256", ""))
        tracked_state = manifest.is_user_modified(manifest_rel) if exists else None

        if not exists:
            status = "new"
        elif incoming_sha256 and current_sha256 == incoming_sha256:
            status = "unchanged"
        elif tracked_state is False:
            status = "updated_clean"
        else:
            status = "updated_user_modified"

        diff_records.append(
            {
                **normalized_record,
                "status": status,
                "exists": exists,
                "tracked": tracked_state is not None,
                "user_modified": tracked_state is True,
                "current_sha256": current_sha256,
            }
        )

    return diff_records


def _scf_backup_workspace(
    package_id: str,
    files_to_backup: list[tuple[str, Path]],
) -> str:
    """Create a timestamped backup directory for files about to be modified."""
    github_root: Path | None = None
    for _, file_abs in files_to_backup:
        for candidate in (file_abs.parent, *file_abs.parents):
            if candidate.name == ".github":
                github_root = candidate
                break
        if github_root is not None:
            break

    if github_root is None:
        raise ValueError("Cannot infer .github root for workspace backup.")

    timestamp = _utc_now().strftime("%Y%m%d-%H%M%S")
    backup_root = github_root / _BACKUPS_SUBDIR / timestamp
    backup_root.mkdir(parents=True, exist_ok=True)
    snapshot_manager = SnapshotManager(github_root / _SNAPSHOTS_SUBDIR)

    for rel_path, file_abs in files_to_backup:
        normalized_rel = snapshot_manager._validate_relative_path(rel_path)
        if normalized_rel is None or not file_abs.is_file():
            continue
        destination = backup_root / PurePosixPath(normalized_rel)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(file_abs.read_bytes())

    _log.info("Workspace backup created for %s: %s", package_id, backup_root)
    return str(backup_root)


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

    def __init__(
        self,
        github_root: Path,
        registry_url: str = _REGISTRY_URL,
        cache_path: Path | None = None,
    ) -> None:
        self._github_root = github_root
        self._registry_url = registry_url
        # v3.0: prefer engine-central cache when caller supplies one.
        # Legacy default kept for back-compat with v2.x callers and tests.
        self._cache_path = (
            cache_path
            if cache_path is not None
            else github_root / _REGISTRY_CACHE_FILENAME
        )

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
# Migration v2.x -> v3.0 helpers (Phase 0 - scf_migrate_workspace)
# ---------------------------------------------------------------------------


_V2_MIGRATION_KEEP_DIRS: tuple[str, ...] = (
    "instructions",
    "runtime",
)
_V2_MIGRATION_KEEP_FILES: tuple[str, ...] = (
    "copilot-instructions.md",
    "project-profile.md",
    ".scf-manifest.json",
    "AGENTS.md",  # legacy index, kept invariata in v3.0 baseline
)
_V2_MIGRATION_OVERRIDE_DIRS: tuple[str, ...] = (
    "agents",
    "prompts",
    "skills",
)
_V2_MIGRATION_DELETE_FILES: tuple[str, ...] = (
    ".scf-registry-cache.json",
)
_V2_MIGRATION_DELETE_PATTERNS: tuple[str, ...] = (
    "AGENTS-",  # AGENTS-{plugin}.md generated files
    "FRAMEWORK_CHANGELOG.md",
)


def _classify_v2_workspace_file(rel_path: Path) -> str:
    """Classify a workspace file under .github/ for migration to v3.0 schema.

    Args:
        rel_path: Path relative to the workspace `.github/` directory.

    Returns:
        One of: "keep", "move_to_override", "delete", "untouched".
    """
    parts = rel_path.parts
    if not parts:
        return "untouched"

    name = parts[-1]
    top = parts[0]

    if top in _V2_MIGRATION_KEEP_DIRS:
        return "keep"
    if name in _V2_MIGRATION_KEEP_FILES and len(parts) == 1:
        return "keep"

    if top in _V2_MIGRATION_OVERRIDE_DIRS:
        return "move_to_override"

    if name in _V2_MIGRATION_DELETE_FILES and len(parts) == 1:
        return "delete"
    for pattern in _V2_MIGRATION_DELETE_PATTERNS:
        if name.startswith(pattern):
            return "delete"

    return "untouched"


@dataclass(frozen=True)
class MigrationPlan:
    """Outcome of MigrationPlanner.analyze() — pure data, no side effects."""

    keep: tuple[str, ...]
    move_to_override: tuple[tuple[str, str], ...]
    delete: tuple[str, ...]
    untouched: tuple[str, ...]
    cache_relocate: tuple[str, str] | None  # (src_abs, dst_abs) or None

    def is_empty(self) -> bool:
        """Return True if the plan has no actions to execute."""
        return (
            not self.move_to_override
            and not self.delete
            and self.cache_relocate is None
        )

    def to_dict(self) -> dict[str, Any]:
        """Render the plan as a JSON-serialisable dict for tool responses."""
        return {
            "keep": list(self.keep),
            "move_to_override": [
                {"from": src, "to": dst} for src, dst in self.move_to_override
            ],
            "delete": list(self.delete),
            "untouched": list(self.untouched),
            "cache_relocate": (
                {"from": self.cache_relocate[0], "to": self.cache_relocate[1]}
                if self.cache_relocate is not None
                else None
            ),
        }


class MigrationPlanner:
    """Plan and execute v2.x -> v3.0 workspace migration with rollback support."""

    def __init__(self, workspace_root: Path, engine_cache_dir: Path | None = None) -> None:
        self._workspace_root = workspace_root
        self._github_root = workspace_root / ".github"
        self._engine_cache_dir = engine_cache_dir

    def analyze(self) -> MigrationPlan:
        """Scan the workspace and build a migration plan without writing anything."""
        if not self._github_root.is_dir():
            return MigrationPlan(
                keep=(),
                move_to_override=(),
                delete=(),
                untouched=(),
                cache_relocate=None,
            )

        keep: list[str] = []
        move: list[tuple[str, str]] = []
        delete: list[str] = []
        untouched: list[str] = []

        for entry in sorted(self._github_root.rglob("*")):
            if not entry.is_file():
                continue
            try:
                rel = entry.relative_to(self._github_root)
            except ValueError:
                continue
            # skip files already inside overrides/
            if rel.parts and rel.parts[0] == "overrides":
                untouched.append(str(rel.as_posix()))
                continue
            classification = _classify_v2_workspace_file(rel)
            rel_str = rel.as_posix()
            if classification == "keep":
                keep.append(rel_str)
            elif classification == "move_to_override":
                # map agents/X.agent.md -> overrides/agents/X.agent.md
                target = Path("overrides") / rel
                move.append((rel_str, target.as_posix()))
            elif classification == "delete":
                delete.append(rel_str)
            else:
                untouched.append(rel_str)

        cache_relocate = self._plan_cache_relocate()

        return MigrationPlan(
            keep=tuple(keep),
            move_to_override=tuple(move),
            delete=tuple(delete),
            untouched=tuple(untouched),
            cache_relocate=cache_relocate,
        )

    def _plan_cache_relocate(self) -> tuple[str, str] | None:
        """Plan the relocation of .scf-registry-cache.json into engine cache dir."""
        legacy = self._workspace_root / ".scf-registry-cache.json"
        if not legacy.is_file():
            return None
        if self._engine_cache_dir is None:
            return None
        target = self._engine_cache_dir / "registry-cache.json"
        return (str(legacy), str(target))

    def apply(self, plan: MigrationPlan) -> dict[str, Any]:
        """Execute the migration plan with backup-based rollback on error.

        Returns a dict with `executed`, `errors`, `rolled_back`, `backup_dir`.
        """
        if plan.is_empty():
            return {
                "executed": [],
                "errors": [],
                "rolled_back": False,
                "backup_dir": None,
            }

        backup_dir = self._create_backup()
        executed: list[str] = []
        errors: list[str] = []

        try:
            # 1. Move v2 files into overrides/
            for src_rel, dst_rel in plan.move_to_override:
                src = self._github_root / src_rel
                dst = self._github_root / dst_rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                src.replace(dst)
                executed.append(f"moved: {src_rel} -> {dst_rel}")

            # 2. Delete v2 generated files
            for rel in plan.delete:
                target = self._github_root / rel
                if target.is_file():
                    target.unlink()
                    executed.append(f"deleted: {rel}")

            # 3. Relocate registry cache (best effort)
            if plan.cache_relocate is not None:
                src_str, dst_str = plan.cache_relocate
                src = Path(src_str)
                dst = Path(dst_str)
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(src.read_bytes())
                    src.unlink()
                    executed.append(f"cache: {src_str} -> {dst_str}")
                except OSError as exc:
                    _log.warning(
                        "[SPARK-ENGINE][WARNING] cache relocate best-effort failed: %s",
                        exc,
                    )
                    errors.append(f"cache_relocate_failed: {exc}")

        except OSError as exc:
            _log.error(
                "[SPARK-ENGINE][ERROR] migration apply failed: %s; rolling back",
                exc,
            )
            errors.append(str(exc))
            self._rollback(backup_dir)
            return {
                "executed": executed,
                "errors": errors,
                "rolled_back": True,
                "backup_dir": str(backup_dir),
            }

        return {
            "executed": executed,
            "errors": errors,
            "rolled_back": False,
            "backup_dir": str(backup_dir),
        }

    def _create_backup(self) -> Path:
        """Create a timestamped backup of .github/ for rollback purposes."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup_dir = self._workspace_root / f".github.migrate-backup-{timestamp}"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(self._github_root, backup_dir)
        return backup_dir

    def _rollback(self, backup_dir: Path) -> None:
        """Restore .github/ from backup_dir after a failed apply."""
        if not backup_dir.is_dir():
            _log.error(
                "[SPARK-ENGINE][ERROR] rollback: backup dir missing %s",
                backup_dir,
            )
            return
        if self._github_root.exists():
            shutil.rmtree(self._github_root)
        shutil.copytree(backup_dir, self._github_root)


# ---------------------------------------------------------------------------
# Phase 6 — Bootstrap v3 asset rendering (AGENTS.md, .clinerules, profile)
# ---------------------------------------------------------------------------


_AGENTS_INDEX_BEGIN: str = "<!-- SCF:BEGIN:agents-index -->"
_AGENTS_INDEX_END: str = "<!-- SCF:END:agents-index -->"

_PROJECT_PROFILE_TEMPLATE: str = """---
spark: true
scf_file_role: "config"
scf_owner: "user"
scf_protected: true
---

# Project Profile

> Compila questo file con i dati del progetto. Lo gestisce l'agente
> `spark-welcome`. Dopo modifiche manuali rilancia
> `scf_bootstrap_workspace` per propagare le modifiche agli asset
> derivati (AGENTS.md, .clinerules).

## Identità progetto

- **Nome**:
- **Descrizione breve**:
- **Stack principale**:
- **Linguaggi**:
- **Framework**:

## Convenzioni

- **Stile codice**:
- **Test framework**:
- **Build/Deploy**:

## Pacchetti SCF consigliati

- (compilato da spark-welcome)

## Note

- (libero)
"""


_CLINERULES_TEMPLATE_HEADER: str = """# .clinerules — Generated by spark-framework-engine

> Regole base per agenti Cline / Roo Code. Il file è generato dal
> bootstrap dell'engine e NON sovrascritto se gia' esistente con
> contenuto utente.

"""


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


def _read_agent_summary(path: Path) -> str:
    """Return a short description for an agent file (frontmatter or first line)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    fm = parse_markdown_frontmatter(text)
    desc = str(fm.get("description") or "").strip()
    if desc:
        return desc[:200]
    body = text.split("---", 2)[-1] if text.startswith("---") else text
    for raw in body.splitlines():
        stripped = raw.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith(">"):
            return stripped[:200]
    return ""


def _collect_engine_agents(engine_root: Path) -> list[tuple[str, str]]:
    """Return ``[(name, owner_label)]`` for all agents declared by the engine manifest."""
    manifest_path = engine_root / "engine-manifest.json"
    if not manifest_path.is_file():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    agents = (manifest.get("mcp_resources") or {}).get("agents") or []
    if not isinstance(agents, list):
        return []
    owner = str(manifest.get("package", "spark-framework-engine"))
    return [(str(name), owner) for name in agents if isinstance(name, str)]


def _collect_package_agents(
    store: "PackageResourceStore",
    package_ids: Iterable[str],
) -> dict[str, list[tuple[str, str]]]:
    """Return ``{package_id: [(agent_name, summary), ...]}`` for installed packages."""
    out: dict[str, list[tuple[str, str]]] = {}
    for pkg_id in package_ids:
        names = store.list_resources(pkg_id, "agents")
        entries: list[tuple[str, str]] = []
        for name in names:
            path = store.resolve(pkg_id, "agents", name)
            summary = _read_agent_summary(path) if path is not None else ""
            entries.append((name, summary))
        if entries:
            out[pkg_id] = entries
    return out


def _apply_phase6_assets(
    workspace_root: Path,
    engine_root: Path,
    installed_packages: Iterable[str],
    github_write_authorized: bool,
) -> dict[str, Any]:
    """Generate AGENTS.md, AGENTS-{plugin}.md, .clinerules, project-profile.md.

    Idempotent: AGENTS.md uses safe-merge with SCF markers; AGENTS-{plugin}.md
    is rewritten on every run; .clinerules and project-profile.md are written
    only when missing. Returns a report dict.
    """
    report: dict[str, Any] = {
        "agents_md": None,
        "plugin_agents_md": [],
        "clinerules": None,
        "project_profile": None,
        "skipped": [],
    }
    if not github_write_authorized:
        report["skipped"].append("github_write_unauthorized")
        return report

    github_root = workspace_root / ".github"
    github_root.mkdir(parents=True, exist_ok=True)

    store = PackageResourceStore(engine_root)
    engine_agents = _collect_engine_agents(engine_root)
    package_agents = _collect_package_agents(store, list(installed_packages))

    # 1) AGENTS.md (safe-merge)
    agents_md_path = github_root / "AGENTS.md"
    existing = agents_md_path.read_text(encoding="utf-8") if agents_md_path.is_file() else None
    new_content = _render_agents_md(engine_agents, package_agents, existing)
    if existing != new_content:
        agents_md_path.write_text(new_content, encoding="utf-8")
        report["agents_md"] = "written"
    else:
        report["agents_md"] = "unchanged"

    # 2) AGENTS-{plugin}.md (always rewrite to keep in sync)
    for pkg_id, agents in package_agents.items():
        plugin_path = github_root / f"AGENTS-{pkg_id}.md"
        plugin_path.write_text(_render_plugin_agents_md(pkg_id, agents), encoding="utf-8")
        report["plugin_agents_md"].append(plugin_path.name)
    report["plugin_agents_md"].sort()

    # 3) project-profile.md (only if missing)
    profile_path = github_root / "project-profile.md"
    if not profile_path.is_file():
        profile_path.write_text(_render_project_profile_template(), encoding="utf-8")
        report["project_profile"] = "created"
    else:
        report["project_profile"] = "preserved"

    # 4) .clinerules (only if missing — never overwrite user content)
    clinerules_path = workspace_root / ".clinerules"
    if not clinerules_path.is_file():
        profile_text = (
            profile_path.read_text(encoding="utf-8")
            if profile_path.is_file() else ""
        )
        summary = _extract_profile_summary(profile_text)
        clinerules_path.write_text(_render_clinerules(summary), encoding="utf-8")
        report["clinerules"] = "created"
    else:
        report["clinerules"] = "preserved"

    return report


# ---------------------------------------------------------------------------
# PackageResourceStore (v3.0) — deposito centralizzato file di pacchetto
# ---------------------------------------------------------------------------

_RESOURCE_TYPES: tuple[str, ...] = ("agents", "prompts", "skills", "instructions")


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


# ---------------------------------------------------------------------------
# McpResourceRegistry (v3.0) — indice URI -> (engine_path, override_path)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# SparkFrameworkEngine — Resources (15) and Tools (40)
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
        # v3.0: traccia URI alias deprecati gia' loggati per evitare spam.
        self._logged_alias_uris: set[str] = set()

    def register_resources(self) -> None:
        """Register all MCP resources.

        Portability note: MCP Prompts are intentionally not registered here.
        VS Code handles .github/prompts/ natively as slash commands; alternative
        MCP clients will see prompts only as text resources, not as native MCP
        Prompt artefacts. Known v1 constraint, correct by design.
        """
        inventory = self._inventory
        ctx = self._ctx
        manifest = ManifestManager(ctx.github_root)
        resource_uris: list[str] = []

        def _register_resource(uri: str) -> Any:
            resource_uris.append(uri)
            return self._mcp.resource(uri)

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

        @_register_resource("agents://list")
        async def resource_agents_list() -> str:
            return _fmt_list(inventory.list_agents(), "SCF Agents")

        # v3.0: helper di lettura via registry con fallback all'inventory locale.
        def _registry_read(resource_type: str, name: str) -> str | None:
            registry = inventory.mcp_registry
            if registry is None:
                return None
            uri = McpResourceRegistry.make_uri(resource_type, name)
            target = registry.resolve(uri)
            if target is None or not target.is_file():
                # Fallback case-insensitive sui nomi registrati.
                lower = name.lower()
                for candidate_uri in registry.list_by_type(resource_type):
                    _, _, candidate_name = candidate_uri.partition("://")
                    if candidate_name.lower() == lower:
                        target = registry.resolve(candidate_uri)
                        break
            if target is None or not target.is_file():
                return None
            try:
                return target.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None

        @_register_resource("agents://{name}")
        async def resource_agent_by_name(name: str) -> str:
            content = _registry_read("agents", name)
            if content is not None:
                return content
            for ff in inventory.list_agents():
                if ff.name.lower() == name.lower():
                    return ff.path.read_text(encoding="utf-8", errors="replace")
            return f"Agent '{name}' not found. Use agents://list to see available agents."

        @_register_resource("skills://list")
        async def resource_skills_list() -> str:
            return _fmt_list(inventory.list_skills(), "SCF Skills")

        @_register_resource("skills://{name}")
        async def resource_skill_by_name(name: str) -> str:
            query = name.removesuffix(".skill")
            content = _registry_read("skills", query)
            if content is not None:
                return content
            qlow = query.lower()
            for ff in inventory.list_skills():
                if ff.name.lower().removesuffix(".skill") == qlow:
                    return ff.path.read_text(encoding="utf-8", errors="replace")
            return f"Skill '{name}' not found. Use skills://list to see available skills."

        @_register_resource("instructions://list")
        async def resource_instructions_list() -> str:
            return _fmt_list(inventory.list_instructions(), "SCF Instructions")

        @_register_resource("instructions://{name}")
        async def resource_instruction_by_name(name: str) -> str:
            query = name.removesuffix(".instructions")
            content = _registry_read("instructions", query)
            if content is not None:
                return content
            qlow = query.lower()
            for ff in inventory.list_instructions():
                if ff.name.lower().removesuffix(".instructions") == qlow:
                    return ff.path.read_text(encoding="utf-8", errors="replace")
            return f"Instruction '{name}' not found. Use instructions://list."

        # ---- v2.4.0: engine-hosted skills and instructions ----
        engine_inventory = EngineInventory()

        def _log_alias_once(alias_uri: str, canonical_uri: str) -> None:
            if alias_uri in self._logged_alias_uris:
                return
            self._logged_alias_uris.add(alias_uri)
            _log.warning(
                "[SPARK-ENGINE][WARN] URI deprecato %s -> usare %s. "
                "Alias rimosso in v4.0.",
                alias_uri,
                canonical_uri,
            )

        @_register_resource("engine-skills://list")
        async def resource_engine_skills_list() -> str:
            return _fmt_list(engine_inventory.list_skills(), "SCF Engine-Hosted Skills")

        @_register_resource("engine-skills://{name}")
        async def resource_engine_skill_by_name(name: str) -> str:
            _log_alias_once(f"engine-skills://{name}", f"skills://{name}")
            return await resource_skill_by_name(name)

        @_register_resource("engine-instructions://list")
        async def resource_engine_instructions_list() -> str:
            return _fmt_list(
                engine_inventory.list_instructions(), "SCF Engine-Hosted Instructions"
            )

        @_register_resource("engine-instructions://{name}")
        async def resource_engine_instruction_by_name(name: str) -> str:
            _log_alias_once(
                f"engine-instructions://{name}", f"instructions://{name}"
            )
            return await resource_instruction_by_name(name)

        @_register_resource("prompts://list")
        async def resource_prompts_list() -> str:
            return _fmt_list(inventory.list_prompts(), "SCF Prompts")

        @_register_resource("prompts://{name}")
        async def resource_prompt_by_name(name: str) -> str:
            query = name.removesuffix(".prompt")
            content = _registry_read("prompts", query)
            if content is not None:
                return content
            qlow = query.lower()
            for ff in inventory.list_prompts():
                if ff.name.lower().removesuffix(".prompt") == qlow:
                    return ff.path.read_text(encoding="utf-8", errors="replace")
            return f"Prompt '{name}' not found. Use prompts://list."

        @_register_resource("scf://global-instructions")
        async def resource_global_instructions() -> str:
            ff = inventory.get_global_instructions()
            return ff.path.read_text(encoding="utf-8", errors="replace") if ff else "copilot-instructions.md not found."

        @_register_resource("scf://project-profile")
        async def resource_project_profile() -> str:
            ff = inventory.get_project_profile()
            if ff is None:
                return "project-profile.md not found in .github/."
            content = ff.path.read_text(encoding="utf-8", errors="replace")
            if not ff.metadata.get("initialized", False):
                return "# WARNING: project not initialized (initialized: false)\nRun #project-setup to configure this workspace.\n\n" + content
            return content

        @_register_resource("scf://model-policy")
        async def resource_model_policy() -> str:
            ff = inventory.get_model_policy()
            return ff.path.read_text(encoding="utf-8", errors="replace") if ff else "model-policy.instructions.md not found."

        @_register_resource("scf://agents-index")
        async def resource_agents_index() -> str:
            indexes = inventory.list_agents_indexes()
            if not indexes:
                return "AGENTS.md not found."
            return "\n\n---\n\n".join(
                ff.path.read_text(encoding="utf-8", errors="replace")
                for ff in indexes
            )

        @_register_resource("scf://framework-version")
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

        @_register_resource("scf://workspace-info")
        async def resource_workspace_info_res() -> str:
            info = build_workspace_info(ctx, inventory)
            return _fmt_workspace_info(info)

        @_register_resource("scf://runtime-state")
        async def resource_runtime_state() -> str:
            """Stato runtime orchestratore come JSON formattato."""
            state = inventory.get_orchestrator_state()
            return json.dumps(state, indent=2, ensure_ascii=False)

        _log.info("[SPARK-ENGINE][INFO] Resources registrate: %d", len(resource_uris))

    def register_tools(self) -> None:  # noqa: C901
        """Register all MCP tools."""
        inventory = self._inventory
        tool_names: list[str] = []

        def _register_tool(name: str) -> Any:
            tool_names.append(name)
            return self._mcp.tool()

        def _ff_to_dict(ff: FrameworkFile) -> dict[str, Any]:
            return {"name": ff.name, "path": str(ff.path), "category": ff.category, "summary": ff.summary, "metadata": ff.metadata}

        # ------------------------------------------------------------------
        # v3.0 Override tools (scf_list_overrides, scf_read_resource,
        # scf_override_resource, scf_drop_override)
        # ------------------------------------------------------------------

        def _parse_resource_uri(uri: str) -> tuple[str, str] | None:
            if not isinstance(uri, str) or "://" not in uri:
                return None
            scheme, _, name = uri.partition("://")
            if scheme not in _RESOURCE_TYPES:
                return None
            if not name:
                return None
            return scheme, name

        def _ensure_registry() -> McpResourceRegistry:
            if inventory.mcp_registry is None:
                # Boot tardivo: popola con engine-manifest se possibile.
                try:
                    engine_manifest = EngineInventory().engine_manifest
                except Exception:  # pragma: no cover - difensivo
                    engine_manifest = {}
                inventory.populate_mcp_registry(engine_manifest=engine_manifest)
            assert inventory.mcp_registry is not None  # noqa: S101
            return inventory.mcp_registry

        @_register_tool("scf_list_overrides")
        async def scf_list_overrides(
            resource_type: str | None = None,
        ) -> dict[str, Any]:
            """Lista override workspace registrati nel McpResourceRegistry.

            Args:
                resource_type: filtro opzionale (agents|prompts|skills|instructions).
            """
            registry = _ensure_registry()
            if resource_type is not None and resource_type not in _RESOURCE_TYPES:
                return {
                    "success": False,
                    "error": f"resource_type non valido: {resource_type}",
                    "supported": list(_RESOURCE_TYPES),
                }
            items: list[dict[str, Any]] = []
            for uri in registry.list_all():
                if not registry.has_override(uri):
                    continue
                meta = registry.get_metadata(uri) or {}
                rtype = str(meta.get("resource_type", ""))
                if resource_type is not None and rtype != resource_type:
                    continue
                override_path = meta.get("override")
                sha = ""
                if override_path:
                    try:
                        sha = _sha256_text(
                            Path(override_path).read_text(encoding="utf-8")
                        )
                    except OSError:
                        sha = ""
                _, _, name = uri.partition("://")
                items.append({
                    "uri": uri,
                    "type": rtype,
                    "name": name,
                    "path": str(override_path) if override_path else None,
                    "sha256": sha,
                })
            return {"count": len(items), "items": items}

        @_register_tool("scf_read_resource")
        async def scf_read_resource(
            uri: str, source: str = "auto"
        ) -> dict[str, Any]:
            """Legge il contenuto di una risorsa MCP (engine o override).

            Args:
                uri: URI nel formato ``{type}://{name}``.
                source: ``auto`` (override > engine), ``engine``, ``override``.
            """
            parsed = _parse_resource_uri(uri)
            if parsed is None:
                return {
                    "success": False,
                    "error": f"URI non valido: {uri}",
                }
            if source not in ("auto", "engine", "override"):
                return {
                    "success": False,
                    "error": f"source non valido: {source}",
                }
            registry = _ensure_registry()
            target: Path | None
            actual_source: str
            if source == "engine":
                target = registry.resolve_engine(uri)
                actual_source = "engine"
            elif source == "override":
                if not registry.has_override(uri):
                    return {
                        "success": False,
                        "error": f"Override non presente per {uri}",
                    }
                meta = registry.get_metadata(uri) or {}
                ov = meta.get("override")
                target = Path(ov) if ov else None
                actual_source = "override"
            else:  # auto
                target = registry.resolve(uri)
                actual_source = "override" if registry.has_override(uri) else "engine"
            if target is None or not target.is_file():
                return {
                    "success": False,
                    "error": f"Risorsa non trovata: {uri} (source={source})",
                }
            try:
                content = target.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                return {
                    "success": False,
                    "error": f"Errore lettura {target}: {exc}",
                }
            return {
                "success": True,
                "uri": uri,
                "source": actual_source,
                "path": str(target),
                "content": content,
            }

        @_register_tool("scf_override_resource")
        async def scf_override_resource(
            uri: str, content: str
        ) -> dict[str, Any]:
            """Crea/aggiorna un override workspace per la risorsa indicata.

            Args:
                uri: URI nel formato ``{type}://{name}``.
                content: nuovo contenuto del file di override.
            """
            parsed = _parse_resource_uri(uri)
            if parsed is None:
                return {
                    "success": False,
                    "error": f"URI non valido: {uri}",
                }
            resource_type, name = parsed
            registry = _ensure_registry()
            if registry.resolve_engine(uri) is None and not registry.has_override(uri):
                return {
                    "success": False,
                    "error": (
                        f"Risorsa {uri} non registrata: l'override richiede una "
                        "risorsa engine o un override preesistente."
                    ),
                }
            orchestrator_state = inventory.get_orchestrator_state()
            if not bool(orchestrator_state.get("github_write_authorized", False)):
                return {
                    "success": False,
                    "error": "github_write_authorized=False: scrittura su .github/ non autorizzata.",
                    "authorization_required": True,
                }
            manifest_mgr = ManifestManager(self._ctx.github_root)
            try:
                target = manifest_mgr.write_override(resource_type, name, content)
            except (ValueError, OSError) as exc:
                return {"success": False, "error": str(exc)}
            registry.register_override(uri, target)
            return {
                "success": True,
                "uri": uri,
                "path": str(target),
                "sha256": _sha256_text(content),
            }

        @_register_tool("scf_drop_override")
        async def scf_drop_override(uri: str) -> dict[str, Any]:
            """Rimuove un override workspace e deregistra dal registry.

            Args:
                uri: URI nel formato ``{type}://{name}``.
            """
            parsed = _parse_resource_uri(uri)
            if parsed is None:
                return {
                    "success": False,
                    "error": f"URI non valido: {uri}",
                }
            resource_type, name = parsed
            registry = _ensure_registry()
            if not registry.has_override(uri):
                return {
                    "success": False,
                    "error": f"Nessun override registrato per {uri}",
                }
            orchestrator_state = inventory.get_orchestrator_state()
            if not bool(orchestrator_state.get("github_write_authorized", False)):
                return {
                    "success": False,
                    "error": "github_write_authorized=False: rimozione non autorizzata.",
                    "authorization_required": True,
                }
            manifest_mgr = ManifestManager(self._ctx.github_root)
            try:
                removed = manifest_mgr.drop_override(resource_type, name)
            except OSError as exc:
                return {"success": False, "error": str(exc)}
            registry.drop_override(uri)
            return {"success": True, "uri": uri, "file_removed": removed}

        @_register_tool("scf_list_agents")
        async def scf_list_agents() -> dict[str, Any]:
            """Return all discovered SCF agents with name, path and summary."""
            items = inventory.list_agents()
            return {"count": len(items), "agents": [_ff_to_dict(ff) for ff in items]}

        @_register_tool("scf_get_agent")
        async def scf_get_agent(name: str) -> dict[str, Any]:
            """Return full content and metadata for a single SCF agent by name."""
            for ff in inventory.list_agents():
                if ff.name.lower() == name.lower():
                    result = _ff_to_dict(ff)
                    result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
                    return result
            return {
                "success": False,
                "error": f"Agent '{name}' not found.",
                "available": [ff.name for ff in inventory.list_agents()],
            }

        @_register_tool("scf_list_skills")
        async def scf_list_skills() -> dict[str, Any]:
            """Return all discovered SCF skills with name, path and summary."""
            items = inventory.list_skills()
            return {"count": len(items), "skills": [_ff_to_dict(ff) for ff in items]}

        @_register_tool("scf_get_skill")
        async def scf_get_skill(name: str) -> dict[str, Any]:
            """Return full content and metadata for a single SCF skill by name."""
            query = name.lower().removesuffix(".skill")
            for ff in inventory.list_skills():
                if ff.name.lower().removesuffix(".skill") == query:
                    result = _ff_to_dict(ff)
                    result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
                    return result
            return {
                "success": False,
                "error": f"Skill '{name}' not found.",
                "available": [ff.name for ff in inventory.list_skills()],
            }

        @_register_tool("scf_list_instructions")
        async def scf_list_instructions() -> dict[str, Any]:
            """Return all discovered SCF instruction files with name, path and summary."""
            items = inventory.list_instructions()
            return {"count": len(items), "instructions": [_ff_to_dict(ff) for ff in items]}

        @_register_tool("scf_get_instruction")
        async def scf_get_instruction(name: str) -> dict[str, Any]:
            """Return full content and metadata for a single SCF instruction by name."""
            query = name.lower().removesuffix(".instructions")
            for ff in inventory.list_instructions():
                if ff.name.lower().removesuffix(".instructions") == query:
                    result = _ff_to_dict(ff)
                    result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
                    return result
            return {
                "success": False,
                "error": f"Instruction '{name}' not found.",
                "available": [ff.name for ff in inventory.list_instructions()],
            }

        @_register_tool("scf_list_prompts")
        async def scf_list_prompts() -> dict[str, Any]:
            """Return all SCF prompt files. Read-only — slash commands are handled natively by VS Code."""
            items = inventory.list_prompts()
            return {"count": len(items), "prompts": [_ff_to_dict(ff) for ff in items]}

        @_register_tool("scf_get_prompt")
        async def scf_get_prompt(name: str) -> dict[str, Any]:
            """Return full content of a SCF prompt file by stem name."""
            query = name.lower().removesuffix(".prompt")
            for ff in inventory.list_prompts():
                if ff.name.lower().removesuffix(".prompt") == query:
                    result = _ff_to_dict(ff)
                    result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
                    return result
            return {
                "success": False,
                "error": f"Prompt '{name}' not found.",
                "available": [ff.name for ff in inventory.list_prompts()],
            }

        @_register_tool("scf_get_project_profile")
        async def scf_get_project_profile() -> dict[str, Any]:
            """Return project-profile.md content, metadata and initialized state."""
            ff = inventory.get_project_profile()
            if ff is None:
                return {"success": False, "error": "project-profile.md not found in .github/."}
            result = _ff_to_dict(ff)
            result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
            result["initialized"] = bool(ff.metadata.get("initialized", False))
            if not result["initialized"]:
                result["warning"] = "Project not initialized. Run #project-setup to configure this workspace."
            return result

        @_register_tool("scf_get_global_instructions")
        async def scf_get_global_instructions() -> dict[str, Any]:
            """Return copilot-instructions.md content and metadata."""
            ff = inventory.get_global_instructions()
            if ff is None:
                return {"success": False, "error": "copilot-instructions.md not found in .github/."}
            result = _ff_to_dict(ff)
            result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
            return result

        @_register_tool("scf_get_model_policy")
        async def scf_get_model_policy() -> dict[str, Any]:
            """Return model-policy.instructions.md content and metadata."""
            ff = inventory.get_model_policy()
            if ff is None:
                return {
                    "success": False,
                    "error": "model-policy.instructions.md not found in .github/instructions/.",
                }
            result = _ff_to_dict(ff)
            result["content"] = ff.path.read_text(encoding="utf-8", errors="replace")
            return result

        @_register_tool("scf_get_framework_version")
        async def scf_get_framework_version() -> dict[str, Any]:
            """Return the engine version and installed SCF package versions."""
            return {
                "engine_version": ENGINE_VERSION,
                "packages": manifest.get_installed_versions(),
            }

        @_register_tool("scf_get_workspace_info")
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

        @_register_tool("scf_list_available_packages")
        async def scf_list_available_packages() -> dict[str, Any]:
            """List all packages currently available in the public SCF registry."""
            try:
                packages = registry.list_packages()
            except Exception as exc:  # noqa: BLE001
                return {"success": False, "error": f"Registry unavailable: {exc}"}
            return {
                "success": True,
                "count": len(packages),
                "packages": [_build_registry_package_summary(p) for p in packages],
            }

        @_register_tool("scf_get_package_info")
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
                pkg_manifest.get("min_engine_version", _get_registry_min_engine_version(pkg))
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
                    "min_engine_version": _get_registry_min_engine_version(pkg),
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

        def _build_remote_file_records(
            package_id: str,
            pkg_version: str,
            pkg: dict[str, Any],
            pkg_manifest: dict[str, Any],
            files: list[str],
            file_policies: dict[str, str],
        ) -> tuple[list[dict[str, Any]], list[str]]:
            """Fetch remote package files and attach SCF metadata for diffing and writes."""
            metadata_by_path: dict[str, dict[str, Any]] = {}
            raw_files_metadata = pkg_manifest.get("files_metadata", [])
            if isinstance(raw_files_metadata, list):
                for item in raw_files_metadata:
                    if not isinstance(item, dict):
                        continue
                    raw_path = str(item.get("path", "")).strip()
                    normalized_rel = _normalize_manifest_relative_path(raw_path)
                    if normalized_rel is None:
                        continue
                    metadata_by_path[f".github/{normalized_rel}"] = item

            remote_files: list[dict[str, Any]] = []
            fetch_errors: list[str] = []
            base_raw_url = pkg["repo_url"].replace(
                "https://github.com/", "https://raw.githubusercontent.com/"
            ) + "/main/"

            for file_path in files:
                metadata = metadata_by_path.get(file_path, {})
                merge_strategy = str(metadata.get("scf_merge_strategy", "")).strip()
                if not merge_strategy:
                    policy = file_policies.get(file_path, "error")
                    if policy == "extend":
                        merge_strategy = "merge_sections"
                    elif policy == "delegate":
                        merge_strategy = "user_protected"
                    else:
                        merge_strategy = "replace"
                        _log.info(
                            "Legacy file without SCF metadata treated with strategy replace: %s",
                            file_path,
                        )

                try:
                    merge_priority = int(metadata.get("scf_merge_priority", 0) or 0)
                except (TypeError, ValueError):
                    merge_priority = 0

                try:
                    content = registry.fetch_raw_file(base_raw_url + file_path)
                except (urllib.error.URLError, OSError) as exc:
                    fetch_errors.append(f"{file_path}: {exc}")
                    continue

                remote_files.append(
                    {
                        "path": file_path,
                        "content": content,
                        "sha256": _sha256_text(content),
                        "scf_owner": str(metadata.get("scf_owner", package_id)).strip() or package_id,
                        "scf_version": str(metadata.get("scf_version", pkg_version)).strip() or pkg_version,
                        "scf_file_role": str(
                            metadata.get(
                                "scf_file_role",
                                _infer_scf_file_role(file_path.removeprefix(".github/")),
                            )
                        ).strip()
                        or _infer_scf_file_role(file_path.removeprefix(".github/")),
                        "scf_merge_strategy": merge_strategy,
                        "scf_merge_priority": merge_priority,
                        "scf_protected": bool(metadata.get("scf_protected", False)),
                    }
                )

            return remote_files, fetch_errors

        def _build_diff_summary(diff_records: list[dict[str, Any]]) -> dict[str, Any]:
            """Return a compact diff summary excluding unchanged files."""
            counts: dict[str, int] = {}
            files_summary: list[dict[str, Any]] = []
            for item in diff_records:
                status = str(item.get("status", "")).strip()
                if status == "unchanged":
                    continue
                counts[status] = counts.get(status, 0) + 1
                files_summary.append(
                    {
                        "file": item.get("file", ""),
                        "status": status,
                        "scf_file_role": item.get("scf_file_role", "config"),
                        "scf_merge_strategy": item.get("scf_merge_strategy", "replace"),
                        "scf_protected": bool(item.get("scf_protected", False)),
                    }
                )
            return {
                "total": len(files_summary),
                "counts": counts,
                "files": files_summary,
            }

        def _resolve_effective_update_mode(
            package_id: str,
            requested_update_mode: str,
            diff_records: list[dict[str, Any]],
            policy_payload: dict[str, Any],
            policy_source: str,
        ) -> dict[str, Any]:
            """Resolve the package-level update mode from request and workspace policy."""
            policy = policy_payload.get("update_policy", _default_update_policy())
            auto_update = bool(policy.get("auto_update", False))
            if requested_update_mode:
                return {
                    "mode": requested_update_mode,
                    "source": "explicit",
                    "auto_update": auto_update,
                    "policy_source": policy_source,
                }

            mode_per_package = policy.get("mode_per_package", {})
            if isinstance(mode_per_package, dict):
                package_mode = _validate_update_mode(
                    str(mode_per_package.get(package_id, "")),
                    allow_selective=True,
                )
                if package_mode is not None:
                    return {
                        "mode": package_mode,
                        "source": "policy_package",
                        "auto_update": auto_update,
                        "policy_source": policy_source,
                    }

            default_mode = str(policy.get("default_mode", "ask")).strip() or "ask"
            mode_per_file_role = policy.get("mode_per_file_role", {})
            role_modes: set[str] = set()
            matched_role_override = False
            if isinstance(mode_per_file_role, dict):
                for item in diff_records:
                    if str(item.get("status", "")).strip() == "unchanged":
                        continue
                    role = str(item.get("scf_file_role", "config")).strip() or "config"
                    candidate_mode = _validate_update_mode(
                        str(mode_per_file_role.get(role, default_mode)),
                        allow_selective=True,
                    )
                    if role in mode_per_file_role:
                        matched_role_override = True
                    if candidate_mode is not None:
                        role_modes.add(candidate_mode)

            if len(role_modes) == 1:
                return {
                    "mode": next(iter(role_modes)),
                    "source": "policy_file_role" if matched_role_override else "policy_default",
                    "auto_update": auto_update,
                    "policy_source": policy_source,
                }
            if len(role_modes) > 1:
                return {
                    "mode": "selective",
                    "source": "policy_file_role",
                    "auto_update": auto_update,
                    "policy_source": policy_source,
                }

            return {
                "mode": default_mode,
                "source": "policy_default",
                "auto_update": auto_update,
                "policy_source": policy_source,
            }

        def _build_update_flow_payload(
            package_id: str,
            pkg_version: str,
            conflict_mode: str,
            requested_update_mode: str,
            effective_update_mode: dict[str, Any],
            diff_summary: dict[str, Any],
        ) -> dict[str, Any]:
            """Return the common OWN-D flow metadata for install/update responses."""
            orchestrator_state = inventory.get_orchestrator_state()
            auto_update = bool(effective_update_mode.get("auto_update", False))
            authorized = bool(orchestrator_state.get("github_write_authorized", False))
            policy_source = str(effective_update_mode.get("policy_source", "default_missing")).strip()
            policy_enforced = policy_source == "file" or bool(requested_update_mode)
            return {
                "update_mode_requested": requested_update_mode or None,
                "resolved_update_mode": effective_update_mode.get("mode", "ask"),
                "update_mode_source": effective_update_mode.get("source", "policy_default"),
                "policy_source": policy_source,
                "policy_enforced": policy_enforced,
                "auto_update": auto_update,
                "authorization_required": policy_enforced and not auto_update,
                "github_write_authorized": authorized,
                "diff_summary": diff_summary,
                "supported_update_modes": [
                    "integrative",
                    "replace",
                    "conservative",
                    "selective",
                ],
            }

        def _detect_workspace_migration_state() -> dict[str, Any]:
            """Return the current migration state for a legacy SCF workspace."""
            policy_payload, policy_source = _read_update_policy_payload(self._ctx.github_root)
            manifest_entries = manifest.load()
            sentinel_path = self._ctx.github_root / "agents" / "spark-assistant.agent.md"
            copilot_path = self._ctx.github_root / "copilot-instructions.md"
            copilot_exists = copilot_path.is_file()
            copilot_content = _read_text_if_possible(copilot_path) if copilot_exists else None
            copilot_format = (
                "unreadable"
                if copilot_exists and copilot_content is None
                else _classify_copilot_instructions_format(copilot_content or "")
                if copilot_exists
                else "missing"
            )
            missing_steps: list[str] = []
            legacy_workspace = bool(manifest_entries or sentinel_path.is_file() or copilot_exists)
            if legacy_workspace and policy_source != "file":
                missing_steps.append("configure_update_policy")
            if copilot_format in {"plain", "scf_markers_partial"}:
                missing_steps.append("migrate_copilot_instructions")
            return {
                "legacy_workspace": legacy_workspace,
                "policy_source": policy_source,
                "policy_path": str(_update_policy_path(self._ctx.github_root)),
                "copilot_instructions": {
                    "path": str(copilot_path),
                    "exists": copilot_exists,
                    "current_format": copilot_format,
                    "proposed_format": (
                        "scf_markers_complete"
                        if copilot_format == "scf_markers_partial"
                        else "scf_markers"
                        if copilot_format == "plain"
                        else None
                    ),
                },
                "missing_steps": missing_steps,
            }

        def _normalize_file_policies(
            raw_policies: Any,
            raw_files_metadata: Any = None,
        ) -> dict[str, str]:
            """Normalize install policies from legacy file_policies and schema 2.1 files_metadata."""
            normalized: dict[str, str] = {}
            if isinstance(raw_files_metadata, list):
                for item in raw_files_metadata:
                    if not isinstance(item, dict):
                        continue
                    raw_path = item.get("path")
                    raw_strategy = item.get("scf_merge_strategy")
                    if not isinstance(raw_path, str) or not isinstance(raw_strategy, str):
                        continue
                    path = raw_path.replace("\\", "/").strip()
                    strategy = raw_strategy.strip().lower()
                    if not path.startswith(".github/"):
                        continue
                    if strategy == "merge_sections":
                        normalized[path] = "extend"
                    elif strategy == "user_protected":
                        normalized[path] = "delegate"

            if not isinstance(raw_policies, dict):
                return normalized

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
                pkg_manifest.get("min_engine_version", _get_registry_min_engine_version(pkg))
            ).strip()
            dependencies = _normalize_string_list(pkg_manifest.get("dependencies", []))
            declared_conflicts = _normalize_string_list(pkg_manifest.get("conflicts", []))
            file_ownership_policy = (
                str(pkg_manifest.get("file_ownership_policy", "error")).strip() or "error"
            )
            file_policies = _normalize_file_policies(
                pkg_manifest.get("file_policies", {}),
                pkg_manifest.get("files_metadata", []),
            )
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

        @_register_tool("scf_list_installed_packages")
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

        @_register_tool("scf_install_package")
        async def scf_install_package(
            package_id: str,
            conflict_mode: str = "abort",
            update_mode: str = "",
            migrate_copilot_instructions: bool = False,
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
            requested_update_mode = ""
            if update_mode.strip():
                validated_update_mode = _validate_update_mode(
                    update_mode,
                    allow_selective=True,
                )
                if validated_update_mode is None:
                    return _build_install_result(
                        False,
                        error=(
                            f"Unsupported update_mode '{update_mode}'. Supported modes: "
                            "ask, integrative, replace, conservative, selective."
                        ),
                        package=package_id,
                        conflict_mode=conflict_mode,
                        update_mode=update_mode,
                    )
                requested_update_mode = validated_update_mode

            install_context = _get_package_install_context(package_id)
            if install_context.get("success") is False:
                return install_context

            pkg = install_context["pkg"]
            pkg_manifest = install_context["pkg_manifest"]
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

            remote_candidate_files = [
                str(item["file"])
                for item in classification_report["records"]
                if item.get("classification") != "delegate_skip"
            ]

            policy_payload, policy_source = _read_update_policy_payload(self._ctx.github_root)
            remote_files: list[dict[str, Any]] = []
            remote_fetch_errors: list[str] = []
            diff_records: list[dict[str, Any]] = []
            diff_summary = {"total": 0, "counts": {}, "files": []}
            if requested_update_mode or policy_source == "file":
                remote_files, remote_fetch_errors = _build_remote_file_records(
                    package_id,
                    pkg_version,
                    pkg,
                    pkg_manifest,
                    remote_candidate_files,
                    file_policies,
                )
                if remote_fetch_errors:
                    return _build_install_result(
                        False,
                        package=package_id,
                        version=pkg_version,
                        delegated_files=[
                            str(item["file"])
                            for item in classification_report["delegate_plan"]
                            if item.get("classification") == "delegate_skip"
                        ],
                        conflicts_detected=classification_report["conflict_plan"],
                        errors=remote_fetch_errors,
                    )

                diff_records = _scf_diff_workspace(
                    package_id,
                    pkg_version,
                    remote_files,
                    manifest,
                )
                diff_summary = _build_diff_summary(diff_records)
            effective_update_mode = _resolve_effective_update_mode(
                package_id,
                requested_update_mode,
                diff_records,
                policy_payload,
                policy_source,
            )
            flow_payload = _build_update_flow_payload(
                package_id,
                pkg_version,
                conflict_mode,
                requested_update_mode,
                effective_update_mode,
                diff_summary,
            )
            if flow_payload["authorization_required"] and not flow_payload["github_write_authorized"]:
                return _build_install_result(
                    True,
                    action_required="authorize_github_write",
                    message=(
                        "GitHub protected writes require authorization for this session before "
                        "installing package files under .github/."
                    ),
                    **flow_payload,
                )

            migration_state = _detect_workspace_migration_state()
            copilot_record = next(
                (
                    item for item in remote_files
                    if str(item.get("path", "")).strip() == ".github/copilot-instructions.md"
                    and str(item.get("scf_merge_strategy", "replace")).strip() == "merge_sections"
                ),
                None,
            )
            copilot_format = str(
                migration_state.get("copilot_instructions", {}).get("current_format", "missing")
            ).strip() or "missing"
            requires_copilot_migration = copilot_record is not None and copilot_format in {
                "plain",
                "scf_markers_partial",
            }
            explicit_copilot_migration = requires_copilot_migration and migrate_copilot_instructions
            if requires_copilot_migration and not migrate_copilot_instructions:
                return _build_install_result(
                    True,
                    action_required="migrate_copilot_instructions",
                    message=(
                        "copilot-instructions.md uses a legacy format. Confirm the explicit migration "
                        "before SPARK adds or updates SCF marker sections."
                    ),
                    current_format=copilot_format,
                    proposed_format=(
                        "scf_markers_complete"
                        if copilot_format == "scf_markers_partial"
                        else "scf_markers"
                    ),
                    migration_state=migration_state,
                    migrate_copilot_instructions=False,
                    **flow_payload,
                )
            if requires_copilot_migration and not flow_payload["github_write_authorized"]:
                return _build_install_result(
                    True,
                    action_required="authorize_github_write",
                    message=(
                        "Authorize writes under .github before migrating copilot-instructions.md "
                        "to the SCF marker format."
                    ),
                    current_format=copilot_format,
                    proposed_format=(
                        "scf_markers_complete"
                        if copilot_format == "scf_markers_partial"
                        else "scf_markers"
                    ),
                    migration_state=migration_state,
                    migrate_copilot_instructions=True,
                    **flow_payload,
                )

            if flow_payload["policy_enforced"] and not flow_payload["auto_update"] and not requested_update_mode:
                return _build_install_result(
                    True,
                    action_required="choose_update_mode",
                    message="Choose an update_mode to continue with the package install.",
                    suggested_update_mode=(
                        "integrative"
                        if flow_payload["resolved_update_mode"] == "ask"
                        else flow_payload["resolved_update_mode"]
                    ),
                    **flow_payload,
                )

            if requested_update_mode in {"ask", "selective"} or (
                flow_payload["policy_enforced"] and flow_payload["resolved_update_mode"] in {"ask", "selective"}
            ):
                return _build_install_result(
                    True,
                    action_required="choose_update_mode",
                    message="Choose an explicit update_mode to continue.",
                    suggested_update_mode=(
                        "integrative"
                        if flow_payload["resolved_update_mode"] == "ask"
                        else None
                    ),
                    **flow_payload,
                )

            effective_conflict_mode = (
                "replace"
                if flow_payload["resolved_update_mode"] == "replace"
                else conflict_mode
            )
            unresolved_conflicts = [
                item
                for item in classification_report["conflict_plan"]
                if item.get("classification") == "conflict_untracked_existing"
                and not (
                    explicit_copilot_migration
                    and str(item.get("file", "")).strip() == ".github/copilot-instructions.md"
                )
            ]
            if unresolved_conflicts and effective_conflict_mode == "abort":
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
                    **flow_payload,
                )

            preserved = [item["file"] for item in classification_report["preserve_plan"]]
            if not remote_files:
                remote_files, remote_fetch_errors = _build_remote_file_records(
                    package_id,
                    pkg_version,
                    pkg,
                    pkg_manifest,
                    remote_candidate_files,
                    file_policies,
                )
                if remote_fetch_errors:
                    return _build_install_result(
                        False,
                        package=package_id,
                        version=pkg_version,
                        delegated_files=[
                            str(item["file"])
                            for item in classification_report["delegate_plan"]
                            if item.get("classification") == "delegate_skip"
                        ],
                        preserved=preserved,
                        conflicts_detected=classification_report["conflict_plan"],
                        **flow_payload,
                        errors=remote_fetch_errors,
                    )
            remote_files_by_path = {
                str(item.get("path", item.get("file", ""))): item for item in remote_files
            }
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
                    if flow_payload["resolved_update_mode"] == "replace":
                        replaced_files.append(file_path)
                    else:
                        continue
                if item_classification == "update_tracked_clean" and flow_payload["resolved_update_mode"] == "conservative":
                    preserved.append(file_path)
                    continue
                if item_classification == "delegate_skip":
                    continue
                if item_classification == "merge_candidate":
                    if flow_payload["resolved_update_mode"] == "conservative":
                        preserved.append(file_path)
                        continue
                    if effective_conflict_mode == "replace":
                        replaced_files.append(file_path)
                    elif not _supports_stateful_merge(effective_conflict_mode):
                        preserved.append(file_path)
                        continue
                if item_classification == "conflict_cross_owner":
                    continue
                if (
                    item_classification == "conflict_untracked_existing"
                    and effective_conflict_mode != "replace"
                    and not (
                        explicit_copilot_migration
                        and file_path == ".github/copilot-instructions.md"
                    )
                ):
                    continue
                rel = file_path.removeprefix(".github/")
                if item_classification == "conflict_untracked_existing" and not explicit_copilot_migration:
                    replaced_files.append(file_path)
                remote_file = remote_files_by_path.get(file_path)
                if remote_file is None:
                    preserved.append(file_path)
                    continue
                content = str(remote_file.get("content", ""))
                staged_files.append(
                    (
                        file_path,
                        rel,
                        content,
                        item_classification,
                        bool(item.get("adopt_bootstrap_owner", False)),
                    )
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
            backup_path: str | None = None
            if flow_payload["resolved_update_mode"] == "replace":
                files_to_backup = [
                    (rel, self._ctx.workspace_root / file_path)
                    for file_path, rel, _, _, _ in staged_files
                    if (self._ctx.workspace_root / file_path).is_file()
                ]
                if files_to_backup:
                    try:
                        backup_path = _scf_backup_workspace(package_id, files_to_backup)
                    except (OSError, ValueError) as exc:
                        return _build_install_result(
                            False,
                            error=f"Cannot create workspace backup: {exc}",
                            delegated_files=delegated_files,
                            preserved=preserved,
                            replaced_files=replaced_files,
                            conflicts_detected=classification_report["conflict_plan"],
                            **flow_payload,
                        )
            try:
                for file_path, rel, content, staged_classification, adopt_bootstrap_owner in staged_files:
                    dest = self._ctx.workspace_root / file_path
                    previous_content = _read_text_if_possible(dest) if dest.is_file() else None
                    backups[dest] = previous_content

                    remote_strategy = str(
                        remote_files_by_path.get(file_path, {}).get(
                            "scf_merge_strategy",
                            "replace",
                        )
                    ).strip() or "replace"

                    if remote_strategy == "merge_sections":
                        merge_base_text = previous_content or ""
                        if (
                            file_path == ".github/copilot-instructions.md"
                            and migrate_copilot_instructions
                            and _classify_copilot_instructions_format(merge_base_text) in {
                                "plain",
                                "scf_markers_partial",
                            }
                        ):
                            merge_base_text = _prepare_copilot_instructions_migration(merge_base_text)
                        next_text = _scf_section_merge_text(
                            content,
                            merge_base_text,
                            remote_strategy,
                            package_id,
                            pkg_version,
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

                    if staged_classification == "extend_section":
                        if dest.exists() and previous_content is None:
                            raise OSError(f"Cannot extend non-text file: {dest}")
                        if remote_strategy == "replace":
                            remote_strategy = "merge_sections"
                        next_text = _scf_section_merge(
                            content,
                            dest,
                            remote_strategy,
                            package_id,
                            pkg_version,
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

                    if file_path in merge_candidates and _supports_stateful_merge(effective_conflict_mode):
                        base_text = snapshots.load_snapshot(package_id, rel)
                        ours_text = previous_content
                        if base_text is None or ours_text is None:
                            preserved.append(file_path)
                            snapshot_skipped.append(file_path)
                            continue

                        used_manual_merge = effective_conflict_mode == "manual"
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
                        if effective_conflict_mode in {"manual", "assisted"}:
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
                    manifest_merge_strategies = {
                        manifest_rel: str(
                            remote_files_by_path.get(f".github/{manifest_rel}", {}).get(
                                "scf_merge_strategy",
                                "replace",
                            )
                        ).strip()
                        or "replace"
                        for manifest_rel, _ in manifest_targets
                    }
                    manifest.upsert_many(
                        package_id,
                        pkg_version,
                        manifest_targets,
                        merge_strategies_by_file=manifest_merge_strategies,
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
                backup_path=backup_path,
                migration_state=migration_state if requires_copilot_migration else None,
                resolution_applied=(
                    "auto"
                    if effective_conflict_mode == "auto" and not merge_conflict and session_payload is not None
                    else "manual"
                    if effective_conflict_mode == "auto" and merge_conflict
                    else "assisted"
                    if effective_conflict_mode == "assisted" and session_payload is not None
                    else "manual"
                    if used_manual_merge or (effective_conflict_mode == "manual" and session_payload is not None)
                    else "replace" if replaced_files else "none"
                ),
                validator_results=auto_validator_results if auto_validator_results else None,
                remaining_conflicts=len(merge_conflict) if merge_conflict else None,
                **flow_payload,
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

        @_register_tool("scf_check_updates")
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

        @_register_tool("scf_update_package")
        async def scf_update_package(
            package_id: str,
            conflict_mode: str = "abort",
            update_mode: str = "",
            migrate_copilot_instructions: bool = False,
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

            if update_mode.strip():
                validated_update_mode = _validate_update_mode(
                    update_mode,
                    allow_selective=True,
                )
                if validated_update_mode is None:
                    return {
                        "success": False,
                        "error": (
                            f"Unsupported update_mode '{update_mode}'. Supported modes: "
                            "ask, integrative, replace, conservative, selective."
                        ),
                        "package": package_id,
                        "conflict_mode": conflict_mode,
                        "update_mode": update_mode,
                    }
                update_mode = validated_update_mode

            installed_versions = manifest.get_installed_versions()
            if package_id not in installed_versions:
                return {
                    "success": False,
                    "error": f"Package '{package_id}' is not installed.",
                    "package": package_id,
                }

            version_from = installed_versions[package_id]
            migration_state = _detect_workspace_migration_state()
            if (
                migration_state["legacy_workspace"]
                and migration_state["policy_source"] != "file"
                and not update_mode.strip()
            ):
                return {
                    "success": True,
                    "package": package_id,
                    "version_from": version_from,
                    "already_up_to_date": False,
                    "action_required": "configure_update_policy",
                    "available_update_modes": [
                        {
                            "value": "ask",
                            "label": "ask",
                            "recommended": True,
                            "description": "Keep auto_update disabled and ask before package updates.",
                        },
                        {
                            "value": "integrative",
                            "label": "integrative",
                            "recommended": False,
                            "description": "Enable automatic integrative updates for package files.",
                        },
                        {
                            "value": "conservative",
                            "label": "conservative",
                            "recommended": False,
                            "description": "Enable automatic conservative updates preserving local changes.",
                        },
                    ],
                    "recommended_update_mode": "ask",
                    "migration_state": migration_state,
                    "message": (
                        "Legacy workspace detected without spark-user-prefs.json. Configure the update "
                        "policy before applying package updates."
                    ),
                }

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

            install_report = await scf_install_package(
                package_id,
                conflict_mode=conflict_mode,
                update_mode=update_mode,
                migrate_copilot_instructions=migrate_copilot_instructions,
            )
            if install_report.get("action_required"):
                return {
                    "success": True,
                    "package": package_id,
                    "version_from": version_from,
                    "version_to": requested_update.get("latest", version_from),
                    "already_up_to_date": False,
                    **install_report,
                }

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
                "resolved_update_mode": install_report.get("resolved_update_mode"),
                "update_mode_source": install_report.get("update_mode_source"),
                "policy_source": install_report.get("policy_source"),
                "authorization_required": bool(install_report.get("authorization_required", False)),
                "github_write_authorized": bool(install_report.get("github_write_authorized", False)),
                "diff_summary": install_report.get("diff_summary"),
                "backup_path": install_report.get("backup_path"),
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
                            pkg_manifest.get(
                                "min_engine_version",
                                _get_registry_min_engine_version(reg_entry),
                            )
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
                        update_entry["min_engine_version"] = min_engine_version
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

        @_register_tool("scf_update_packages")
        async def scf_update_packages() -> dict[str, Any]:
            """Check installed SCF packages for updates and build an ordered update preview."""
            return _plan_package_updates()

        @_register_tool("scf_apply_updates")
        async def scf_apply_updates(
            package_id: str | None = None,
            conflict_mode: str = "abort",
            migrate_copilot_instructions: bool = False,
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
                result = await scf_install_package(
                    pkg_id,
                    conflict_mode=conflict_mode,
                    migrate_copilot_instructions=migrate_copilot_instructions,
                )
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

        @_register_tool("scf_plan_install")
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

        @_register_tool("scf_remove_package")
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

        @_register_tool("scf_get_package_changelog")
        async def scf_get_package_changelog(package_id: str) -> dict[str, Any]:
            """Return the changelog content for one installed SCF package."""
            content = inventory.get_package_changelog(package_id)
            if content is None:
                return {
                    "success": False,
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

        @_register_tool("scf_verify_workspace")
        async def scf_verify_workspace() -> dict[str, Any]:
            """Verify runtime manifest integrity against files currently present in .github/."""
            report = manifest.verify_integrity()
            summary = dict(report.get("summary", {}))
            issue_count = int(summary.get("issue_count", 0))
            summary["is_clean"] = issue_count == 0
            report["summary"] = summary
            return report

        @_register_tool("scf_verify_system")
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
                min_engine_reg = _get_registry_min_engine_version(reg_entry)
                if min_engine_pkg and min_engine_reg and min_engine_pkg != min_engine_reg:
                    issues.append({
                        "type": "engine_min_mismatch",
                        "package": pkg_id,
                        "registry_engine_min": min_engine_reg,
                        "manifest_engine_min": min_engine_pkg,
                        "fix": f"Aggiornare registry.json: min_engine_version → {min_engine_pkg}",
                    })

            return {
                "engine_version": ENGINE_VERSION,
                "packages_checked": len(installed),
                "issues": issues,
                "warnings": warnings,
                "manifest_empty": False,
                "is_coherent": len(issues) == 0,
            }

        @_register_tool("scf_get_runtime_state")
        async def scf_get_runtime_state() -> dict[str, Any]:
            """Leggi lo stato runtime dell'orchestratore dal workspace corrente."""
            return inventory.get_orchestrator_state()

        @_register_tool("scf_update_runtime_state")
        async def scf_update_runtime_state(patch: dict[str, Any]) -> dict[str, Any]:
            """Aggiorna selettivamente lo stato runtime dell'orchestratore nel workspace."""
            return inventory.set_orchestrator_state(patch)

        @_register_tool("scf_bootstrap_workspace")
        async def scf_bootstrap_workspace(
            install_base: bool = False,
            conflict_mode: str = "abort",
            update_mode: str = "",
            migrate_copilot_instructions: bool = False,
        ) -> dict[str, Any]:
            """Bootstrap the base SPARK assets into this workspace and optionally install spark-base.

            Returns a status-oriented payload with fields such as `status`,
            `files_written`, `preserved` and `note`, plus optional install and
            authorization metadata for extended flows.
            """
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
            normalized_bootstrap_mode = update_mode.strip().lower()
            allowed_bootstrap_modes = {"", "ask", "integrative", "conservative", "ask_later"}
            if normalized_bootstrap_mode not in allowed_bootstrap_modes:
                return {
                    "success": False,
                    "status": "error",
                    "files_written": [],
                    "preserved": [],
                    "workspace": str(self._ctx.workspace_root),
                    "install_base_requested": install_base,
                    "conflict_mode": conflict_mode,
                    "update_mode": update_mode,
                    "note": (
                        f"Unsupported update_mode '{update_mode}'. Supported modes: "
                        "ask, integrative, conservative, ask_later."
                    ),
                }
            engine_github_root = Path(__file__).resolve().parent / ".github"
            prompts_source_dir = engine_github_root / "prompts"
            agent_source = engine_github_root / "agents" / "spark-assistant.agent.md"
            guide_source = engine_github_root / "instructions" / "spark-assistant-guide.instructions.md"
            workspace_github_root = self._ctx.github_root
            sentinel = workspace_github_root / "agents" / "spark-assistant.agent.md"
            sentinel_rel = "agents/spark-assistant.agent.md"
            policy_payload, policy_source = _read_update_policy_payload(self._ctx.github_root)
            migration_state = _detect_workspace_migration_state()
            legacy_bootstrap_mode = normalized_bootstrap_mode == "" and policy_source != "file"

            def _bootstrap_policy_options() -> list[dict[str, Any]]:
                return [
                    {
                        "value": "ask",
                        "label": "ask",
                        "recommended": True,
                        "description": "Keep auto_update disabled and ask before package updates.",
                    },
                    {
                        "value": "integrative",
                        "label": "integrative",
                        "recommended": False,
                        "description": "Enable automatic integrative updates for package files.",
                    },
                    {
                        "value": "conservative",
                        "label": "conservative",
                        "recommended": False,
                        "description": "Enable automatic conservative updates preserving local changes.",
                    },
                    {
                        "value": "ask_later",
                        "label": "ask_later",
                        "recommended": False,
                        "description": "Create the policy file now and defer update mode choice to a later step.",
                    },
                ]

            def _configure_initial_bootstrap_policy(selected_mode: str) -> tuple[dict[str, Any], Path]:
                policy_payload = _default_update_policy_payload()
                policy = policy_payload["update_policy"]
                if selected_mode == "integrative":
                    policy["auto_update"] = True
                    policy["default_mode"] = "integrative"
                elif selected_mode == "conservative":
                    policy["auto_update"] = True
                    policy["default_mode"] = "conservative"
                else:
                    policy["auto_update"] = False
                    policy["default_mode"] = "ask"
                policy["changed_by_user"] = True
                policy["last_changed"] = _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
                return policy_payload, _write_update_policy_payload(self._ctx.github_root, policy_payload)

            diff_summary: dict[str, Any] = {"total": 0, "counts": {}, "files": []}
            effective_install_update_mode = "" if normalized_bootstrap_mode == "ask_later" else normalized_bootstrap_mode
            policy_created = False
            policy_path = _update_policy_path(self._ctx.github_root)

            if not legacy_bootstrap_mode:
                if policy_source != "file":
                    if normalized_bootstrap_mode == "":
                        return {
                            "success": True,
                            "status": "policy_configuration_required",
                            "files_written": [],
                            "preserved": [],
                            "workspace": str(self._ctx.workspace_root),
                            "install_base_requested": install_base,
                            "conflict_mode": conflict_mode,
                            "update_mode": update_mode,
                            "action_required": "configure_update_policy",
                            "available_update_modes": _bootstrap_policy_options(),
                            "recommended_update_mode": "ask",
                            "policy_source": policy_source,
                            "migration_state": migration_state,
                            "note": "Configure the initial workspace update policy before running the extended bootstrap flow.",
                        }
                    if migration_state["legacy_workspace"]:
                        orchestrator_state = inventory.get_orchestrator_state()
                        github_write_authorized = bool(
                            orchestrator_state.get("github_write_authorized", False)
                        )
                        if not github_write_authorized:
                            return {
                                "success": True,
                                "status": "authorization_required",
                                "files_written": [],
                                "preserved": [],
                                "workspace": str(self._ctx.workspace_root),
                                "install_base_requested": install_base,
                                "conflict_mode": conflict_mode,
                                "update_mode": update_mode,
                                "resolved_update_mode": normalized_bootstrap_mode or None,
                                "policy_source": policy_source,
                                "policy_created": False,
                                "authorization_required": True,
                                "github_write_authorized": False,
                                "diff_summary": diff_summary,
                                "migration_state": migration_state,
                                "action_required": "authorize_github_write",
                                "note": "Authorize writes under .github before migrating this legacy workspace.",
                            }
                    policy_payload, policy_path = _configure_initial_bootstrap_policy(normalized_bootstrap_mode)
                    policy_source = "file"
                    policy_created = True

                if install_base:
                    install_context = _get_package_install_context("spark-base")
                    if install_context.get("success") is False:
                        return {
                            **install_context,
                            "status": "error",
                            "files_written": [],
                            "preserved": [],
                            "workspace": str(self._ctx.workspace_root),
                            "install_base_requested": install_base,
                            "conflict_mode": conflict_mode,
                            "update_mode": update_mode,
                            "policy_source": policy_source,
                        }
                    remote_files, remote_fetch_errors = _build_remote_file_records(
                        "spark-base",
                        install_context["pkg_version"],
                        install_context["pkg"],
                        install_context["pkg_manifest"],
                        install_context["files"],
                        install_context["file_policies"],
                    )
                    if remote_fetch_errors:
                        return {
                            "success": False,
                            "status": "error",
                            "files_written": [],
                            "preserved": [],
                            "workspace": str(self._ctx.workspace_root),
                            "install_base_requested": install_base,
                            "conflict_mode": conflict_mode,
                            "update_mode": update_mode,
                            "policy_source": policy_source,
                            "errors": remote_fetch_errors,
                            "note": "Cannot build the spark-base bootstrap diff preview.",
                        }
                    diff_summary = _build_diff_summary(
                        _scf_diff_workspace(
                            "spark-base",
                            install_context["pkg_version"],
                            remote_files,
                            manifest,
                        )
                    )

                orchestrator_state_path = self._ctx.github_root / "runtime" / "orchestrator-state.json"
                if not orchestrator_state_path.is_file():
                    inventory.set_orchestrator_state({"github_write_authorized": False})
                orchestrator_state = inventory.get_orchestrator_state()
                github_write_authorized = bool(orchestrator_state.get("github_write_authorized", False))
                if not github_write_authorized:
                    return {
                        "success": True,
                        "status": "authorization_required",
                        "files_written": [],
                        "preserved": [],
                        "workspace": str(self._ctx.workspace_root),
                        "install_base_requested": install_base,
                        "conflict_mode": conflict_mode,
                        "update_mode": update_mode,
                        "resolved_update_mode": normalized_bootstrap_mode or None,
                        "policy_source": policy_source,
                        "policy_created": policy_created,
                        "policy_path": str(policy_path),
                        "authorization_required": True,
                        "github_write_authorized": False,
                        "diff_summary": diff_summary,
                        "action_required": "authorize_github_write",
                        "note": "Authorize writes under .github before running the extended bootstrap flow.",
                    }

            async def _finalize_bootstrap_result(result: dict[str, Any]) -> dict[str, Any]:
                result["install_base_requested"] = install_base
                result["conflict_mode"] = conflict_mode
                result["update_mode"] = update_mode
                result["policy_source"] = policy_source
                result["policy_created"] = policy_created
                if policy_created:
                    result["policy_path"] = str(policy_path)
                if not legacy_bootstrap_mode:
                    result["authorization_required"] = True
                    result["github_write_authorized"] = True
                    result["diff_summary"] = diff_summary

                # v3.0 — Phase 6 assets: AGENTS.md dinamico, .clinerules, profile.
                try:
                    orchestrator_state = inventory.get_orchestrator_state()
                    write_authorized = bool(
                        orchestrator_state.get("github_write_authorized", False)
                    )
                except Exception:  # pragma: no cover - defensive
                    write_authorized = False
                installed_for_phase6 = list(manifest.get_installed_versions().keys())
                try:
                    phase6_report = _apply_phase6_assets(
                        self._ctx.workspace_root,
                        self._ctx.engine_root,
                        installed_for_phase6,
                        github_write_authorized=write_authorized,
                    )
                    result["phase6_assets"] = phase6_report
                except OSError as exc:
                    _log.warning("Phase 6 asset rendering failed: %s", exc)
                    result["phase6_assets"] = {"error": str(exc)}

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

                base_install = await scf_install_package(
                    "spark-base",
                    conflict_mode=conflict_mode,
                    update_mode=effective_install_update_mode,
                    migrate_copilot_instructions=migrate_copilot_instructions,
                )
                result["base_install"] = base_install
                if base_install.get("action_required"):
                    result["bootstrap_status"] = result["status"]
                    result["status"] = "base_install_action_required"
                    result["note"] = "Bootstrap completed, but spark-base requires an additional action before installation can continue."
                    return result
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
                    _log.info(
                        "[SPARK-ENGINE][INFO] Bootstrapped: %s",
                        dest_path.relative_to(workspace_github_root).as_posix(),
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

        @_register_tool("scf_migrate_workspace")
        async def scf_migrate_workspace(
            dry_run: bool = True,
            force: bool = False,
        ) -> dict[str, Any]:
            """Migrate a v2.x workspace `.github/` layout to the v3.0 schema.

            Two-step flow: analyse first, then optionally execute.
            With dry_run=True (default) only the migration plan is returned.
            With dry_run=False and force=True, the plan is applied with a
            timestamped backup and rollback on error.
            """
            workspace_root = self._ctx.workspace_root
            engine_cache = self._ctx.engine_root / "cache"
            planner = MigrationPlanner(workspace_root, engine_cache)
            plan = planner.analyze()

            if dry_run:
                return {
                    "success": True,
                    "dry_run": True,
                    "migration_plan": plan.to_dict(),
                    "requires_confirmation": not plan.is_empty(),
                    "workspace": str(workspace_root),
                }

            if not force and not plan.is_empty():
                return {
                    "success": False,
                    "dry_run": False,
                    "error": "force=True required to apply a non-empty migration plan",
                    "migration_plan": plan.to_dict(),
                    "workspace": str(workspace_root),
                }

            if plan.is_empty():
                return {
                    "success": True,
                    "dry_run": False,
                    "status": "no_op",
                    "migration_plan": plan.to_dict(),
                    "workspace": str(workspace_root),
                }

            report = planner.apply(plan)
            return {
                "success": not report["rolled_back"],
                "dry_run": False,
                "status": "rolled_back" if report["rolled_back"] else "migrated",
                "migration_plan": plan.to_dict(),
                "report": report,
                "workspace": str(workspace_root),
            }

        @_register_tool("scf_resolve_conflict_ai")
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

        @_register_tool("scf_approve_conflict")
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

        @_register_tool("scf_reject_conflict")
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

        @_register_tool("scf_finalize_update")
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

        @_register_tool("scf_get_update_policy")
        async def scf_get_update_policy() -> dict[str, Any]:
            """Return the workspace update policy used for SCF file updates."""
            payload, source = _read_update_policy_payload(self._ctx.github_root)
            return {
                "success": True,
                "policy": payload["update_policy"],
                "path": str(_update_policy_path(self._ctx.github_root)),
                "source": source,
            }

        @_register_tool("scf_set_update_policy")
        async def scf_set_update_policy(
            auto_update: bool,
            default_mode: str | None = None,
            mode_per_package: dict[str, str] | None = None,
            mode_per_file_role: dict[str, str] | None = None,
        ) -> dict[str, Any]:
            """Create or update the workspace update policy for SCF file operations."""
            payload, source = _read_update_policy_payload(self._ctx.github_root)
            policy = dict(payload["update_policy"])

            if default_mode is not None:
                validated_default_mode = _validate_update_mode(
                    default_mode,
                    allow_selective=False,
                )
                if validated_default_mode is None:
                    return {
                        "success": False,
                        "error": (
                            "Invalid default_mode. Supported values: ask, integrative, "
                            "replace, conservative."
                        ),
                        "path": str(_update_policy_path(self._ctx.github_root)),
                    }
                policy["default_mode"] = validated_default_mode

            if mode_per_package is not None:
                normalized_package_modes: dict[str, str] = {}
                invalid_package_modes: list[str] = []
                for package_key, mode_value in mode_per_package.items():
                    normalized_key = str(package_key).strip()
                    validated_mode = _validate_update_mode(str(mode_value), allow_selective=True)
                    if not normalized_key or validated_mode is None:
                        invalid_package_modes.append(f"{package_key}={mode_value}")
                        continue
                    normalized_package_modes[normalized_key] = validated_mode
                if invalid_package_modes:
                    return {
                        "success": False,
                        "error": "Invalid mode_per_package entries.",
                        "invalid_entries": invalid_package_modes,
                        "path": str(_update_policy_path(self._ctx.github_root)),
                    }
                policy["mode_per_package"] = normalized_package_modes

            if mode_per_file_role is not None:
                normalized_role_modes: dict[str, str] = {}
                invalid_role_modes: list[str] = []
                for role_key, mode_value in mode_per_file_role.items():
                    normalized_key = str(role_key).strip()
                    validated_mode = _validate_update_mode(str(mode_value), allow_selective=True)
                    if not normalized_key or validated_mode is None:
                        invalid_role_modes.append(f"{role_key}={mode_value}")
                        continue
                    normalized_role_modes[normalized_key] = validated_mode
                if invalid_role_modes:
                    return {
                        "success": False,
                        "error": "Invalid mode_per_file_role entries.",
                        "invalid_entries": invalid_role_modes,
                        "path": str(_update_policy_path(self._ctx.github_root)),
                    }
                policy["mode_per_file_role"] = normalized_role_modes

            policy["auto_update"] = bool(auto_update)
            policy["last_changed"] = _format_utc_timestamp(_utc_now())
            policy["changed_by_user"] = True

            saved_path = _write_update_policy_payload(
                self._ctx.github_root,
                {"update_policy": policy},
            )
            return {
                "success": True,
                "policy": policy,
                "path": str(saved_path),
                "source": source,
            }

        _log.info("[SPARK-ENGINE][INFO] Tools registrati: %d", len(tool_names))


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

    # v3.0: popola McpResourceRegistry con risorse engine + override workspace.
    # I package_manifests del deposito centralizzato vengono integrati in Fase 5.
    try:
        engine_inv = EngineInventory()
        engine_manifest = engine_inv.engine_manifest
    except Exception as exc:  # pragma: no cover - difensivo
        _log.warning("Caricamento engine-manifest fallito: %s", exc)
        engine_manifest = {}
    inventory.populate_mcp_registry(engine_manifest=engine_manifest)
    if inventory.mcp_registry is not None:
        _log.info(
            "MCP resource registry: %d URI registrati",
            len(inventory.mcp_registry.list_all()),
        )

    app = SparkFrameworkEngine(mcp, context, inventory)
    app.register_resources()
    app.register_tools()
    _log.info("Tools registered: 40 total")

    return mcp


if __name__ == "__main__":
    _build_app().run(transport="stdio")
