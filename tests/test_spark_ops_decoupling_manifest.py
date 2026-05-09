"""Regression tests for the spark-base to spark-ops resource split."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGES_ROOT = REPO_ROOT / "packages"

MIGRATED_AGENTS = {"Agent-FrameworkDocs", "Agent-Orchestrator", "Agent-Release"}
MIGRATED_PROMPTS = {
    "framework-changelog",
    "framework-release",
    "framework-update",
    "orchestrate",
    "release",
}
MIGRATED_SKILLS = {"error-recovery", "semantic-gate", "task-scope-guard"}

BASE_OWNED_AFTER_SPLIT = {
    "agents": {"Agent-Research", "Agent-Git", "spark-assistant", "spark-guide"},
    "prompts": {"framework-unlock", "git-commit", "git-merge", "scf-install"},
    "skills": {
        "rollback-procedure",
        "framework-scope-guard",
        "semver-bump",
        "git-execution",
    },
}


def _load_manifest(package_id: str) -> dict[str, Any]:
    manifest_path = PACKAGES_ROOT / package_id / "package-manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _dependency_versions(manifest: dict[str, Any]) -> dict[str, str]:
    return {
        str(item["id"]): str(item["min_version"])
        for item in manifest.get("dependencies", [])
    }


def test_spark_ops_manifest_exposes_only_operational_resources() -> None:
    manifest = _load_manifest("spark-ops")
    resources = manifest["mcp_resources"]

    assert manifest["schema_version"] == "3.1"
    assert manifest["delivery_mode"] == "mcp_only"
    assert manifest["workspace_files"] == []
    assert _dependency_versions(manifest) == {"spark-base": "2.0.0"}
    assert set(resources["agents"]) == MIGRATED_AGENTS
    assert set(resources["prompts"]) == MIGRATED_PROMPTS
    assert set(resources["skills"]) == MIGRATED_SKILLS
    assert resources["instructions"] == []


def test_spark_base_manifest_no_longer_exports_operational_resources() -> None:
    manifest = _load_manifest("spark-base")
    resources = manifest["mcp_resources"]
    file_paths = set(manifest["files"])
    metadata_paths = {item["path"] for item in manifest["files_metadata"]}
    engine_skills = set(manifest["engine_provided_skills"])

    assert manifest["version"] == "2.0.0"
    assert set(resources["agents"]).isdisjoint(MIGRATED_AGENTS)
    assert set(resources["prompts"]).isdisjoint(MIGRATED_PROMPTS)
    assert set(resources["skills"]).isdisjoint(MIGRATED_SKILLS)
    assert engine_skills.isdisjoint(MIGRATED_SKILLS)

    for agent in MIGRATED_AGENTS:
        assert f".github/agents/{agent}.md" not in file_paths
        assert f".github/agents/{agent}.md" not in metadata_paths

    for prompt in MIGRATED_PROMPTS:
        prompt_path = f".github/prompts/{prompt}.prompt.md"
        assert prompt_path not in file_paths
        assert prompt_path not in metadata_paths

    for skill in MIGRATED_SKILLS:
        skill_path = (
            ".github/skills/error-recovery/SKILL.md"
            if skill == "error-recovery"
            else f".github/skills/{skill}.skill.md"
        )
        assert skill_path not in file_paths
        assert skill_path not in metadata_paths


def test_spark_base_retains_shared_dependencies_needed_by_user_facing_agents() -> None:
    resources = _load_manifest("spark-base")["mcp_resources"]

    assert BASE_OWNED_AFTER_SPLIT["agents"].issubset(set(resources["agents"]))
    assert BASE_OWNED_AFTER_SPLIT["prompts"].issubset(set(resources["prompts"]))
    assert BASE_OWNED_AFTER_SPLIT["skills"].issubset(set(resources["skills"]))


def test_embedded_plugins_depend_on_decoupled_operational_layer() -> None:
    master_dependencies = _dependency_versions(_load_manifest("scf-master-codecrafter"))
    python_dependencies = _dependency_versions(_load_manifest("scf-pycode-crafter"))

    assert master_dependencies["spark-base"] == "2.0.0"
    assert master_dependencies["spark-ops"] == "1.0.0"
    assert python_dependencies["scf-master-codecrafter"] == "2.7.0"