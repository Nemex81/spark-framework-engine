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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
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

ENGINE_VERSION: str = "1.8.0"


# ---------------------------------------------------------------------------
# Changelogs directory
# ---------------------------------------------------------------------------
_CHANGELOGS_SUBDIR: str = "changelogs"

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


# ---------------------------------------------------------------------------
# WorkspaceLocator
# ---------------------------------------------------------------------------


class WorkspaceLocator:
    """Resolve WORKSPACE_FOLDER env var with fallback to cwd."""

    def resolve(self) -> WorkspaceContext:
        workspace_root_str: str | None = os.environ.get("WORKSPACE_FOLDER")
        if workspace_root_str:
            workspace_root = Path(workspace_root_str)
        else:
            workspace_root = Path.cwd()
            _log.warning(
                "WORKSPACE_FOLDER env var not set; falling back to cwd: %s",
                workspace_root,
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
_MANIFEST_FILENAME: str = ".scf-manifest.json"


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
            return list(raw.get("entries", []))
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
        entries = [e for e in entries if e.get("file") != file_rel]
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
            if self._is_user_modified(entry, file_path):
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
        entries = [entry for entry in entries if str(entry.get("file", "")).strip() not in replacements]
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
# SparkFrameworkEngine — Resources (15) and Tools (28)
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
        """Register all 28 MCP tools."""
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
                    "version": pkg_manifest.get("version", pkg.get("latest_version", "")),
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
        async def scf_install_package(package_id: str) -> dict[str, Any]:
            """Install an SCF package from the public registry into the active workspace .github/."""
            try:
                packages = registry.list_packages()
            except Exception as exc:  # noqa: BLE001
                return {
                    "success": False,
                    "error": f"Registry unavailable: {exc}",
                    "removed_obsolete_files": [],
                    "preserved_obsolete_files": [],
                }
            pkg = next((p for p in packages if p.get("id") == package_id), None)
            if pkg is None:
                return {
                    "success": False,
                    "error": f"Package '{package_id}' not found in registry.",
                    "available": [p.get("id") for p in packages],
                    "removed_obsolete_files": [],
                    "preserved_obsolete_files": [],
                }
            if pkg.get("status") == "deprecated":
                return {
                    "success": False,
                    "error": (
                        f"Package '{package_id}' is deprecated. "
                        "Check the registry for its successor."
                    ),
                    "removed_obsolete_files": [],
                    "preserved_obsolete_files": [],
                }
            # Fetch package file manifest
            try:
                pkg_manifest = registry.fetch_package_manifest(pkg["repo_url"])
            except RuntimeError as exc:
                return {
                    "success": False,
                    "error": f"Cannot fetch package manifest: {exc}",
                    "removed_obsolete_files": [],
                    "preserved_obsolete_files": [],
                }
            files: list[str] = pkg_manifest.get("files", [])
            if not files:
                return {
                    "success": False,
                    "error": f"Package '{package_id}' has no files in its manifest.",
                    "removed_obsolete_files": [],
                    "preserved_obsolete_files": [],
                }
            pkg_version = str(pkg_manifest.get("version", pkg.get("latest_version", "unknown"))).strip()
            min_engine_version = str(
                pkg_manifest.get("min_engine_version", pkg.get("engine_min_version", ""))
            ).strip()
            dependencies = _normalize_string_list(pkg_manifest.get("dependencies", []))
            declared_conflicts = _normalize_string_list(pkg_manifest.get("conflicts", []))
            file_ownership_policy = (
                str(pkg_manifest.get("file_ownership_policy", "error")).strip() or "error"
            )
            installed_versions = manifest.get_installed_versions()
            if not _is_engine_version_compatible(ENGINE_VERSION, min_engine_version):
                return {
                    "success": False,
                    "error": (
                        f"Package '{package_id}' requires engine version >= {min_engine_version}."
                    ),
                    "package": package_id,
                    "required_engine_version": min_engine_version,
                    "engine_version": ENGINE_VERSION,
                    "removed_obsolete_files": [],
                    "preserved_obsolete_files": [],
                }
            missing_dependencies = [
                dependency for dependency in dependencies if dependency not in installed_versions
            ]
            if missing_dependencies:
                return {
                    "success": False,
                    "error": (
                        f"Package '{package_id}' requires missing dependencies: "
                        f"{', '.join(missing_dependencies)}"
                    ),
                    "package": package_id,
                    "missing_dependencies": missing_dependencies,
                    "installed_packages": installed_versions,
                    "removed_obsolete_files": [],
                    "preserved_obsolete_files": [],
                }
            present_conflicts = [
                conflict for conflict in declared_conflicts if conflict in installed_versions
            ]
            if present_conflicts:
                return {
                    "success": False,
                    "error": (
                        f"Package '{package_id}' conflicts with installed packages: "
                        f"{', '.join(present_conflicts)}"
                    ),
                    "package": package_id,
                    "present_conflicts": present_conflicts,
                    "installed_packages": installed_versions,
                    "removed_obsolete_files": [],
                    "preserved_obsolete_files": [],
                }
            ownership_conflicts: list[dict[str, Any]] = []
            for file_path in files:
                rel = file_path.removeprefix(".github/")
                owners = [owner for owner in manifest.get_file_owners(rel) if owner != package_id]
                if owners:
                    ownership_conflicts.append(
                        {
                            "file": file_path,
                            "owners": owners,
                        }
                    )
            if ownership_conflicts:
                return {
                    "success": False,
                    "error": (
                        f"Package '{package_id}' conflicts with files already owned by another package."
                    ),
                    "package": package_id,
                    "file_ownership_policy": file_ownership_policy,
                    "effective_file_ownership_policy": "error",
                    "conflicts": ownership_conflicts,
                    "removed_obsolete_files": [],
                    "preserved_obsolete_files": [],
                }
            preserved: list[str] = []
            fetch_errors: list[str] = []
            staged_files: list[tuple[str, str, str]] = []
            for file_path in files:
                raw_url = (
                    pkg["repo_url"].replace(
                        "https://github.com/", "https://raw.githubusercontent.com/"
                    )
                    + "/main/"
                    + file_path
                )
                rel = file_path.removeprefix(".github/")
                if manifest.is_user_modified(rel) is True:
                    preserved.append(file_path)
                    continue
                try:
                    content = registry.fetch_raw_file(raw_url)
                except (urllib.error.URLError, OSError) as exc:
                    fetch_errors.append(f"{file_path}: {exc}")
                    continue
                staged_files.append((file_path, rel, content))
            if fetch_errors:
                return {
                    "success": False,
                    "package": package_id,
                    "version": pkg_version,
                    "installed": [],
                    "preserved": preserved,
                    "removed_obsolete_files": [],
                    "preserved_obsolete_files": [],
                    "errors": fetch_errors,
                }
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
            try:
                for file_path, rel, content in staged_files:
                    dest = self._ctx.workspace_root / file_path
                    previous_content: str | None = None
                    if dest.is_file():
                        previous_content = dest.read_text(encoding="utf-8")
                    backups[dest] = previous_content
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(content, encoding="utf-8")
                    written_paths.append((file_path, rel, dest))
                manifest.upsert_many(
                    package_id,
                    pkg_version,
                    [(rel, dest) for _, rel, dest in written_paths],
                )
                installed = [file_path for file_path, _, _ in written_paths]
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
            success_result: dict[str, Any] = {
                "success": True,
                "package": package_id,
                "version": pkg_version,
                "installed": installed,
                "preserved": preserved,
                "removed_obsolete_files": removed_files,
                "preserved_obsolete_files": preserved_obsolete,
            }
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
        async def scf_update_package(package_id: str) -> dict[str, Any]:
            """Update one installed SCF package while preserving user-modified files."""
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

            apply_report = await scf_apply_updates(package_id)
            if apply_report.get("success") is False:
                return {
                    "success": False,
                    "package": package_id,
                    "error": apply_report.get("error", "unknown error"),
                    "version_from": version_from,
                    "version_to": requested_update.get("latest", version_from),
                    "details": apply_report,
                }

            applied_items = list(apply_report.get("applied", []))
            requested_result = next(
                (item for item in applied_items if item.get("package") == package_id),
                None,
            )
            if requested_result is None:
                return {
                    "success": False,
                    "package": package_id,
                    "error": f"Update completed without an applied result for '{package_id}'.",
                    "version_from": version_from,
                    "version_to": requested_update.get("latest", version_from),
                    "details": apply_report,
                }

            preserved_files = list(requested_result.get("preserved", [])) + list(
                requested_result.get("preserved_obsolete_files", [])
            )
            return {
                "success": True,
                "package": package_id,
                "version_from": version_from,
                "version_to": requested_result.get("version", requested_update.get("latest", version_from)),
                "updated_files": list(requested_result.get("installed", [])),
                "preserved_files": preserved_files,
                "removed_obsolete_files": list(requested_result.get("removed_obsolete_files", [])),
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
                latest_ver = str(reg_entry.get("latest_version", "")).strip()
                status = "up_to_date" if installed_ver == latest_ver else "update_available"
                update_entry: dict[str, Any] = {
                    "package": pkg_id,
                    "status": status,
                    "installed": installed_ver,
                    "latest": latest_ver,
                    "registry_status": reg_entry.get("status", "unknown"),
                }

                pkg_manifest: dict[str, Any] | None = None
                manifest_error: str | None = None
                if status == "update_available":
                    try:
                        pkg_manifest = registry.fetch_package_manifest(reg_entry["repo_url"])
                        manifest_cache[pkg_id] = pkg_manifest
                    except Exception as exc:  # noqa: BLE001
                        manifest_error = str(exc)
                        update_entry["status"] = "metadata_unavailable"
                        update_entry["error"] = f"Cannot fetch package manifest: {exc}"

                if pkg_manifest is not None:
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
        async def scf_apply_updates(package_id: str | None = None) -> dict[str, Any]:
            """Apply package updates by reinstalling latest versions from the registry.

            If package_id is provided, applies the update only for that package.
            Otherwise applies all available updates.
            """
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
            applied: list[dict[str, Any]] = []
            failed: list[dict[str, Any]] = []
            for pkg_id in target_ids:
                result = await scf_install_package(pkg_id)
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
            return {
                "success": True,
                "package": package_id,
                "preserved_user_modified": preserved,
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
        async def scf_bootstrap_workspace() -> dict[str, Any]:
            """Bootstrap the base SPARK prompts and assistant agent into this workspace."""
            engine_github_root = Path(__file__).resolve().parent / ".github"
            prompts_source_dir = engine_github_root / "prompts"
            agent_source = engine_github_root / "agents" / "spark-assistant.agent.md"
            guide_source = engine_github_root / "instructions" / "spark-assistant-guide.instructions.md"
            workspace_github_root = self._ctx.github_root
            sentinel = workspace_github_root / "agents" / "spark-assistant.agent.md"
            sentinel_exists = sentinel.is_file()

            prompt_sources = sorted(prompts_source_dir.glob("scf-*.prompt.md"))
            bootstrap_targets: list[tuple[Path, Path]] = [
                (source_path, workspace_github_root / "prompts" / source_path.name)
                for source_path in prompt_sources
            ]
            bootstrap_targets.append((agent_source, workspace_github_root / "agents" / "spark-assistant.agent.md"))
            bootstrap_targets.append(
                (guide_source, workspace_github_root / "instructions" / "spark-assistant-guide.instructions.md")
            )

            if sentinel_exists and all(dest_path.is_file() for _, dest_path in bootstrap_targets):
                present_files = [
                    dest_path.relative_to(self._ctx.workspace_root).as_posix()
                    for _, dest_path in bootstrap_targets
                    if dest_path.is_file()
                ]
                return {
                    "success": True,
                    "already_bootstrapped": True,
                    "files_copied": [],
                    "files_skipped": present_files,
                    "workspace": str(self._ctx.workspace_root),
                    "note": "Bootstrap assets already present in this workspace. Run /scf-list-available to inspect the package catalog.",
                }

            missing_sources = [
                str(source_path)
                for source_path, _ in bootstrap_targets
                if not source_path.is_file()
            ]
            if missing_sources:
                return {
                    "success": False,
                    "already_bootstrapped": sentinel_exists,
                    "files_copied": [],
                    "files_skipped": [],
                    "workspace": str(self._ctx.workspace_root),
                    "note": f"Bootstrap sources missing from engine repository: {missing_sources}",
                }

            files_copied: list[str] = []
            files_skipped: list[str] = []
            written_paths: list[Path] = []

            try:
                for source_path, dest_path in bootstrap_targets:
                    rel_path = dest_path.relative_to(self._ctx.workspace_root).as_posix()
                    if dest_path.is_file():
                        if manifest._sha256(dest_path) == manifest._sha256(source_path):
                            _log.info("Bootstrap file already matches source: %s", rel_path)
                        else:
                            _log.warning("Bootstrap file preserved (existing different content): %s", rel_path)
                        files_skipped.append(rel_path)
                        continue

                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_bytes(source_path.read_bytes())
                    written_paths.append(dest_path)
                    files_copied.append(rel_path)
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
                    "already_bootstrapped": sentinel_exists,
                    "files_copied": [],
                    "files_skipped": files_skipped,
                    "workspace": str(self._ctx.workspace_root),
                    "note": f"Bootstrap failed while copying files: {exc}.{rollback_note}",
                }

            return {
                "success": True,
                "already_bootstrapped": sentinel_exists,
                "files_copied": files_copied,
                "files_skipped": files_skipped,
                "workspace": str(self._ctx.workspace_root),
                "note": "Bootstrap completed. Run /scf-list-available to inspect the package catalog.",
            }

        _log.info("Tools registered: 28 total")


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
