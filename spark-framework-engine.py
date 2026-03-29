"""SPARK Framework Engine: expose the SPARK Code Framework as MCP Resources and Tools.

Transport: stdio only.
Logging: stderr or file — never stdout (would corrupt the JSON-RPC stream).
Python: 3.10+ required (MCP SDK baseline).

Domain boundary:
- Slash commands (/scf-*): handled by VS Code natively from .github/prompts/
- Tools and Resources: handled by this server — dynamic, on-demand, Agent mode only
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
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


def parse_markdown_frontmatter(content: str) -> dict[str, Any]:
    """Parse optional YAML-style key:value frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    result: dict[str, Any] = {}
    for raw_line in parts[1].strip().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, raw_value = line.partition(":")
        value_str = raw_value.strip().strip('"').strip("'")
        if value_str.lower() in ("true", "yes"):
            result[key.strip()] = True
        elif value_str.lower() in ("false", "no"):
            result[key.strip()] = False
        elif value_str.isdigit():
            result[key.strip()] = int(value_str)
        else:
            result[key.strip()] = value_str
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
# SparkFrameworkEngine — Resources (16) and Tools (13)
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
        """Register all 16 MCP resources."""
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
        """Register all 13 MCP tools."""
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

        _log.info("Tools registered: 13 total")


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
