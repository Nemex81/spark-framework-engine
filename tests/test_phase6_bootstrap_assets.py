"""Tests for Phase 6 v3.0 bootstrap asset rendering helpers.

Covers AGENTS.md safe-merge, AGENTS-{plugin}.md rendering, .clinerules
template, project-profile.md template and the orchestrating
``_apply_phase6_assets`` helper.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ENGINE_PY = REPO_ROOT / "spark-framework-engine.py"


def _load_engine_module():  # noqa: ANN202 - test helper
    spec = importlib.util.spec_from_file_location(
        "spark_framework_engine_phase6_test", ENGINE_PY
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[spec.name] = module  # type: ignore[union-attr]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


engine = _load_engine_module()


class TestRenderAgentsMd:
    def test_render_fresh_workspace(self) -> None:
        text = engine._render_agents_md(
            engine_agents=[("spark-assistant", "spark-framework-engine")],
            package_agents={},
            existing_content=None,
        )
        assert engine._AGENTS_INDEX_BEGIN in text
        assert engine._AGENTS_INDEX_END in text
        assert "@spark-assistant" in text
        assert "nessun pacchetto" in text

    def test_render_with_packages(self) -> None:
        text = engine._render_agents_md(
            engine_agents=[("spark-welcome", "spark-framework-engine")],
            package_agents={
                "spark-base": [("spark-guide", "Helper agent")],
                "scf-pycode-crafter": [("py-Agent-Code", "")],
            },
            existing_content=None,
        )
        assert "### spark-base" in text
        assert "### scf-pycode-crafter" in text
        assert "@spark-guide" in text
        assert "Helper agent" in text
        assert "@py-Agent-Code" in text

    def test_safe_merge_preserves_user_text(self) -> None:
        existing = (
            "# My custom header\n\nUser intro paragraph.\n\n"
            f"{engine._AGENTS_INDEX_BEGIN}\nold content\n{engine._AGENTS_INDEX_END}\n"
            "\n## User-managed appendix\n\nMore user notes.\n"
        )
        merged = engine._render_agents_md(
            engine_agents=[("spark-assistant", "engine")],
            package_agents={},
            existing_content=existing,
        )
        assert merged.startswith("# My custom header\n")
        assert "User intro paragraph." in merged
        assert "## User-managed appendix" in merged
        assert "More user notes." in merged
        assert "old content" not in merged
        assert "@spark-assistant" in merged

    def test_appends_block_when_no_markers(self) -> None:
        existing = "# Existing AGENTS.md\n\nSome legacy text.\n"
        merged = engine._render_agents_md(
            engine_agents=[("a", "engine")],
            package_agents={},
            existing_content=existing,
        )
        assert merged.startswith("# Existing AGENTS.md\n")
        assert engine._AGENTS_INDEX_BEGIN in merged
        assert merged.endswith("\n")


class TestRenderPluginAgentsMd:
    def test_render_with_agents(self) -> None:
        text = engine._render_plugin_agents_md(
            "scf-pycode-crafter",
            [("py-Agent-Code", "Python coder"), ("py-Agent-Validate", "")],
        )
        assert text.startswith("---\n")
        assert "scf_owner: \"scf-pycode-crafter\"" in text
        assert "@py-Agent-Code" in text
        assert "Python coder" in text
        assert "@py-Agent-Validate" in text

    def test_render_empty_package(self) -> None:
        text = engine._render_plugin_agents_md("empty-pkg", [])
        assert "pacchetto installato senza agenti" in text


class TestRenderClinerules:
    def test_with_summary(self) -> None:
        text = engine._render_clinerules("Project alpha — Python")
        assert "Project alpha" in text
        assert ".github/AGENTS.md" in text

    def test_without_summary(self) -> None:
        text = engine._render_clinerules(None)
        assert "non ancora compilato" in text


class TestProjectProfileTemplate:
    def test_template_has_frontmatter(self) -> None:
        text = engine._render_project_profile_template()
        assert text.startswith("---\n")
        assert "scf_owner:" in text
        assert "spark-welcome" in text


class TestExtractProfileSummary:
    def test_extracts_first_paragraph(self) -> None:
        profile = (
            "---\nspark: true\n---\n\n# Title\n\nReal summary line.\n"
            "More details about the project.\n\n## Section\n"
        )
        summary = engine._extract_profile_summary(profile)
        assert summary is not None
        assert "Real summary line." in summary

    def test_returns_none_for_empty(self) -> None:
        assert engine._extract_profile_summary("") is None
        assert engine._extract_profile_summary("# Only header\n") is None


class TestApplyPhase6Assets:
    @pytest.fixture()
    def engine_root(self, tmp_path: Path) -> Path:
        eng = tmp_path / "engine"
        (eng / ".github").mkdir(parents=True)
        (eng / "engine-manifest.json").write_text(
            json.dumps(
                {
                    "package": "spark-framework-engine",
                    "version": "3.0.0",
                    "mcp_resources": {
                        "agents": ["spark-assistant", "spark-welcome"],
                    },
                }
            ),
            encoding="utf-8",
        )
        # Simulate one installed package in the centralized store.
        pkg_agents = eng / "packages" / "spark-base" / ".github" / "agents"
        pkg_agents.mkdir(parents=True)
        (pkg_agents / "spark-guide.agent.md").write_text(
            "---\nname: spark-guide\ndescription: Onboarding helper\n---\n# spark-guide\n",
            encoding="utf-8",
        )
        return eng

    @pytest.fixture()
    def workspace(self, tmp_path: Path) -> Path:
        ws = tmp_path / "ws"
        ws.mkdir()
        return ws

    def test_writes_all_assets_when_authorized(
        self, workspace: Path, engine_root: Path
    ) -> None:
        report = engine._apply_phase6_assets(
            workspace_root=workspace,
            engine_root=engine_root,
            installed_packages=["spark-base"],
            github_write_authorized=True,
        )
        agents_md = workspace / ".github" / "AGENTS.md"
        plugin_md = workspace / ".github" / "AGENTS-spark-base.md"
        profile = workspace / ".github" / "project-profile.md"
        clinerules = workspace / ".clinerules"
        assert agents_md.is_file()
        assert plugin_md.is_file()
        assert profile.is_file()
        assert clinerules.is_file()
        assert report["agents_md"] == "written"
        assert "AGENTS-spark-base.md" in report["plugin_agents_md"]
        assert report["project_profile"] == "created"
        assert report["clinerules"] == "created"
        assert "@spark-guide" in agents_md.read_text(encoding="utf-8")
        assert "Onboarding helper" in plugin_md.read_text(encoding="utf-8")

    def test_skipped_when_unauthorized(
        self, workspace: Path, engine_root: Path
    ) -> None:
        report = engine._apply_phase6_assets(
            workspace_root=workspace,
            engine_root=engine_root,
            installed_packages=["spark-base"],
            github_write_authorized=False,
        )
        assert "github_write_unauthorized" in report["skipped"]
        assert not (workspace / ".github" / "AGENTS.md").exists()

    def test_idempotent_second_run(
        self, workspace: Path, engine_root: Path
    ) -> None:
        engine._apply_phase6_assets(
            workspace, engine_root, ["spark-base"], github_write_authorized=True
        )
        # User edits project-profile.md
        profile = workspace / ".github" / "project-profile.md"
        profile.write_text("# Custom profile content\n", encoding="utf-8")
        report = engine._apply_phase6_assets(
            workspace, engine_root, ["spark-base"], github_write_authorized=True
        )
        assert report["agents_md"] == "unchanged"
        assert report["project_profile"] == "preserved"
        assert profile.read_text(encoding="utf-8") == "# Custom profile content\n"

    def test_clinerules_not_overwritten(
        self, workspace: Path, engine_root: Path
    ) -> None:
        clinerules = workspace / ".clinerules"
        clinerules.write_text("user content\n", encoding="utf-8")
        report = engine._apply_phase6_assets(
            workspace, engine_root, [], github_write_authorized=True
        )
        assert report["clinerules"] == "preserved"
        assert clinerules.read_text(encoding="utf-8") == "user content\n"

    def test_safe_merge_preserves_user_agents_md(
        self, workspace: Path, engine_root: Path
    ) -> None:
        github = workspace / ".github"
        github.mkdir()
        agents_md = github / "AGENTS.md"
        agents_md.write_text(
            f"# User AGENTS\n\nUser preface.\n\n"
            f"{engine._AGENTS_INDEX_BEGIN}\nold\n{engine._AGENTS_INDEX_END}\n"
            f"\n## User appendix\nUser tail.\n",
            encoding="utf-8",
        )
        engine._apply_phase6_assets(
            workspace, engine_root, ["spark-base"], github_write_authorized=True
        )
        text = agents_md.read_text(encoding="utf-8")
        assert "User preface." in text
        assert "## User appendix" in text
        assert "User tail." in text
        assert "old" not in text
