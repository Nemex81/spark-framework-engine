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
import subprocess
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

ENGINE_VERSION: str = "1.0.0"

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
    scripts_root: Path
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
        scripts_root = workspace_root / "scripts"
        engine_root = workspace_root / "spark-framework-engine"

        if not github_root.is_dir():
            _log.warning(".github/ not found in workspace: %s", github_root)
        if not scripts_root.is_dir():
            _log.warning("scripts/ not found in workspace: %s", scripts_root)

        return WorkspaceContext(
            workspace_root=workspace_root,
            github_root=github_root,
            scripts_root=scripts_root,
            engine_root=engine_root,
        )


# ---------------------------------------------------------------------------
# Standalone parsers
# ---------------------------------------------------------------------------

# Pre-compiled patterns for YAML list detection in frontmatter.
_FM_INLINE_LIST_RE: re.Pattern[str] = re.compile(r"^\[(.+)\]$")
_FM_BLOCK_ITEM_RE: re.Pattern[str] = re.compile(r"^(\s+)-\s+(.*)")


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


def extract_framework_version(changelog_path: Path) -> str:
    """Extract the latest framework version from FRAMEWORK_CHANGELOG.md."""
    if not changelog_path.is_file():
        _log.warning("FRAMEWORK_CHANGELOG.md not found: %s", changelog_path)
        return "unknown"
    try:
        text = changelog_path.read_text(encoding="utf-8")
    except OSError as exc:
        _log.error("Cannot read FRAMEWORK_CHANGELOG.md: %s", exc)
        return "unknown"
    pattern = re.compile(
        r"^\s*#{1,3}\s+\[?(v?[\d]+\.[\d]+\.[\d]+[^\]\s]*)\]?",
        re.MULTILINE,
    )
    match = pattern.search(text)
    return match.group(1) if match else "unknown"


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
        return self._list_by_pattern(self._ctx.github_root / "skills", "*.skill.md", "skill")

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

    def list_scripts(self) -> list[FrameworkFile]:
        return self._list_by_pattern(self._ctx.scripts_root, "*.py", "script")

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

    def get_framework_version(self) -> str:
        return extract_framework_version(self._ctx.github_root / "FRAMEWORK_CHANGELOG.md")


# ---------------------------------------------------------------------------
# workspace-info builder
# ---------------------------------------------------------------------------


def build_workspace_info(context: WorkspaceContext, inventory: FrameworkInventory) -> dict[str, Any]:
    profile = inventory.get_project_profile()
    initialized: bool = bool(profile.metadata.get("initialized", False)) if profile else False
    return {
        "workspace_root": str(context.workspace_root),
        "github_root": str(context.github_root),
        "scripts_root": str(context.scripts_root),
        "initialized": initialized,
        "framework_version": inventory.get_framework_version(),
        "agent_count": len(inventory.list_agents()),
        "skill_count": len(inventory.list_skills()),
        "instruction_count": len(inventory.list_instructions()),
        "prompt_count": len(inventory.list_prompts()),
        "script_count": len(inventory.list_scripts()),
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


# ---------------------------------------------------------------------------
# ScriptExecutor
# ---------------------------------------------------------------------------

_SCRIPT_TIMEOUT_SECONDS: int = 30


class ScriptExecutor:
    """Run selected scripts from scripts/ with allowlist, timeout and NVDA-safe output."""

    _ALLOWLIST: frozenset[str] = frozenset({
        "detect_agent.py",
        "validate_gates.py",
        "ci-local-validate.py",
        "generate-changelog.py",
        "sync-documentation.py",
        "create-project-files.py",
    })

    def __init__(self, context: WorkspaceContext) -> None:
        self._ctx = context

    def run(self, script_name: str, args: list[str]) -> dict[str, Any]:
        if script_name not in self._ALLOWLIST:
            return {
                "success": False,
                "error": f"{script_name!r} is not in the allowed set. Allowed: {sorted(self._ALLOWLIST)}",
                "stdout": "", "stderr": "", "returncode": -1,
            }
        script_path = self._ctx.scripts_root / script_name
        if not script_path.is_file():
            return {
                "success": False,
                "error": f"Script not found: {script_path}",
                "stdout": "", "stderr": "", "returncode": -1,
            }
        cmd = [sys.executable, str(script_path)] + args
        _log.info("Running script: %s %s", script_name, args)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=_SCRIPT_TIMEOUT_SECONDS, cwd=str(self._ctx.workspace_root),
            )
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Script timed out after {_SCRIPT_TIMEOUT_SECONDS}s: {script_name}",
                "stdout": "", "stderr": "", "returncode": -1,
            }
        except OSError as exc:
            return {
                "success": False, "error": f"OS error running {script_name}: {exc}",
                "stdout": "", "stderr": "", "returncode": -1,
            }
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode,
        }


# ---------------------------------------------------------------------------
# SparkFrameworkEngine — Resources (16) and Tools (15)
# ---------------------------------------------------------------------------


class SparkFrameworkEngine:
    """Register MCP resources and tools over FastMCP via workspace discovery.

    MCP Prompts are intentionally NOT registered here.
    VS Code already exposes .github/prompts/*.prompt.md as native slash commands.
    Registering them again via MCP would create duplicate entries in the / picker.
    Prompt files remain accessible as Resources (prompts://list, prompts://{name})
    and via scf_list_prompts / scf_get_prompt tools for Agent mode consumption.
    """

    def __init__(self, mcp: FastMCP, context: WorkspaceContext, inventory: FrameworkInventory, executor: ScriptExecutor) -> None:
        self._mcp = mcp
        self._ctx = context
        self._inventory = inventory
        self._executor = executor

    def register_resources(self) -> None:
        """Register all 16 MCP resources.

        Portability note: MCP Prompts are intentionally not registered here.
        VS Code handles .github/prompts/ natively as slash commands; alternative
        MCP clients will see prompts only as text resources, not as native MCP
        Prompt artefacts. Known v1 constraint, correct by design.
        """
        inventory = self._inventory
        ctx = self._ctx

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

        @self._mcp.resource("scripts://list")
        async def resource_scripts_list() -> str:
            return _fmt_list(inventory.list_scripts(), "SCF Scripts")

        @self._mcp.resource("scripts://{name}")
        async def resource_script_by_name(name: str) -> str:
            query = name.lower().removesuffix(".py")
            for ff in inventory.list_scripts():
                if ff.name.lower() == query:
                    return ff.path.read_text(encoding="utf-8", errors="replace")
            return f"Script '{name}' not found. Use scripts://list."

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
            ff = inventory.get_agents_index()
            return ff.path.read_text(encoding="utf-8", errors="replace") if ff else "AGENTS.md not found."

        @self._mcp.resource("scf://framework-version")
        async def resource_framework_version() -> str:
            return f"SPARK Framework Engine version: {inventory.get_framework_version()}"

        @self._mcp.resource("scf://workspace-info")
        async def resource_workspace_info_res() -> str:
            info = build_workspace_info(ctx, inventory)
            return _fmt_workspace_info(info)

        _log.info("Resources registered: 5 list + 5 template + 6 scf:// singletons (16 total)")

    def register_tools(self) -> None:  # noqa: C901
        """Register all 15 MCP tools."""
        inventory = self._inventory
        executor = self._executor

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
        async def scf_list_scripts() -> dict[str, Any]:
            """Return all scripts in scripts/ with allowlist status."""
            items = inventory.list_scripts()
            return {"count": len(items), "scripts": [{**_ff_to_dict(ff), "allowed": ff.path.name in ScriptExecutor._ALLOWLIST} for ff in items]}

        @self._mcp.tool()
        async def scf_run_script(script_name: str, args: list[str] | None = None) -> dict[str, Any]:
            """Execute an allowlisted script from scripts/ and return captured output. Timeout: 30s."""
            return executor.run(script_name, args or [])

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
            """Return the latest SCF framework version from FRAMEWORK_CHANGELOG.md."""
            return {"framework_version": inventory.get_framework_version()}

        @self._mcp.tool()
        async def scf_get_workspace_info() -> dict[str, Any]:
            """Return workspace paths, initialization state and SCF asset counts."""
            return build_workspace_info(self._ctx, inventory)

        manifest = ManifestManager(self._ctx.github_root)
        registry = RegistryClient(self._ctx.github_root)

        @self._mcp.tool()
        async def scf_install_package(package_id: str) -> dict[str, Any]:
            """Install an SCF package from the public registry into the active workspace .github/."""
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
            if pkg.get("status") == "deprecated":
                return {
                    "success": False,
                    "error": (
                        f"Package '{package_id}' is deprecated. "
                        "Check the registry for its successor."
                    ),
                }
            # Full file installation requires scf-pack-* repos to publish their
            # file listing. Pending until the first package repos are available.
            return {
                "success": False,
                "error": (
                    "Package file installation not yet available: "
                    "scf-pack-* package repos are pending creation."
                ),
                "package": pkg,
            }

        @self._mcp.tool()
        async def scf_update_packages() -> dict[str, Any]:
            """Check installed SCF packages for updates and report upgrade opportunities."""
            entries = manifest.load()
            if not entries:
                return {"message": "No SCF packages installed via manifest.", "updates": []}
            try:
                reg_packages = registry.list_packages()
            except Exception as exc:  # noqa: BLE001
                return {"success": False, "error": f"Registry unavailable: {exc}"}
            reg_index: dict[str, Any] = {p["id"]: p for p in reg_packages if "id" in p}
            updates: list[dict[str, Any]] = []
            seen: set[str] = set()
            for entry in entries:
                pkg_id = entry.get("package", "")
                if not pkg_id or pkg_id in seen:
                    continue
                seen.add(pkg_id)
                reg_entry = reg_index.get(pkg_id)
                if reg_entry is None:
                    updates.append({"package": pkg_id, "status": "not_in_registry"})
                    continue
                installed_ver = entry.get("package_version", "")
                latest_ver = reg_entry.get("latest_version", "")
                if installed_ver == latest_ver:
                    updates.append({
                        "package": pkg_id,
                        "status": "up_to_date",
                        "version": installed_ver,
                    })
                else:
                    updates.append({
                        "package": pkg_id,
                        "status": "update_available",
                        "installed": installed_ver,
                        "latest": latest_ver,
                    })
            return {"updates": updates, "total": len(updates)}

        _log.info("Tools registered: 15 total")


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
        "Framework inventory: %d agents, %d skills, %d instructions, %d prompts, %d scripts",
        len(inventory.list_agents()), len(inventory.list_skills()),
        len(inventory.list_instructions()), len(inventory.list_prompts()),
        len(inventory.list_scripts()),
    )

    executor = ScriptExecutor(context)
    app = SparkFrameworkEngine(mcp, context, inventory, executor)
    app.register_resources()
    app.register_tools()

    return mcp


if __name__ == "__main__":
    _build_app().run(transport="stdio")
