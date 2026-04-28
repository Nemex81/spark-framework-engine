"""Tests for ManifestManager v3.0 schema.

Covers schema bump to 3.0, ``overrides[]`` summary emission, backward-compat
reads of v2.x manifests, and override write/drop cycle.
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
        "spark_framework_engine_manifest_v3_test", ENGINE_PY
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[spec.name] = module  # type: ignore[union-attr]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


engine = _load_engine_module()


@pytest.fixture()
def github_root(tmp_path: Path) -> Path:
    root = tmp_path / ".github"
    root.mkdir()
    return root


class TestSchemaV3Save:
    def test_save_emits_schema_v3(self, github_root: Path) -> None:
        manager = engine.ManifestManager(github_root)
        manager.save([])
        payload = json.loads((github_root / ".scf-manifest.json").read_text("utf-8"))
        assert payload["schema_version"] == "3.0"
        assert payload["entries"] == []
        assert payload["overrides"] == []

    def test_overrides_summary_derived_from_entries(self, github_root: Path) -> None:
        manager = engine.ManifestManager(github_root)
        entries = [
            {
                "file": ".github/overrides/agents/spark-guide.md",
                "package": "__workspace_override__",
                "package_version": "0.0.0",
                "installed_at": "2026-04-28T00:00:00Z",
                "sha256": "deadbeef",
                "scf_merge_strategy": "single_owner",
                "override_type": "agents",
                "override_name": "spark-guide",
            },
            {
                "file": ".github/copilot-instructions.md",
                "package": "spark-base",
                "package_version": "1.5.0",
                "installed_at": "2026-04-28T00:00:00Z",
                "sha256": "cafef00d",
                "scf_merge_strategy": "merge_sections",
            },
        ]
        manager.save(entries)
        payload = json.loads((github_root / ".scf-manifest.json").read_text("utf-8"))
        assert len(payload["overrides"]) == 1
        ov = payload["overrides"][0]
        assert ov["type"] == "agents"
        assert ov["name"] == "spark-guide"
        assert ov["sha256"] == "deadbeef"

    def test_overrides_summary_sorted(self, github_root: Path) -> None:
        manager = engine.ManifestManager(github_root)
        entries = [
            {
                "file": ".github/overrides/skills/zeta.skill.md",
                "package": "__workspace_override__",
                "package_version": "0.0.0",
                "installed_at": "2026-04-28T00:00:00Z",
                "sha256": "1",
                "scf_merge_strategy": "single_owner",
                "override_type": "skills",
                "override_name": "zeta",
            },
            {
                "file": ".github/overrides/agents/alpha.agent.md",
                "package": "__workspace_override__",
                "package_version": "0.0.0",
                "installed_at": "2026-04-28T00:00:00Z",
                "sha256": "2",
                "scf_merge_strategy": "single_owner",
                "override_type": "agents",
                "override_name": "alpha",
            },
        ]
        manager.save(entries)
        payload = json.loads((github_root / ".scf-manifest.json").read_text("utf-8"))
        names = [(o["type"], o["name"]) for o in payload["overrides"]]
        assert names == [("agents", "alpha"), ("skills", "zeta")]


class TestBackwardCompatRead:
    def test_reads_v2_1_manifest(self, github_root: Path) -> None:
        legacy = {
            "schema_version": "2.1",
            "entries": [
                {
                    "file": "agents/spark-assistant.agent.md",
                    "package": "spark-base",
                    "package_version": "1.4.0",
                    "installed_at": "2026-01-01T00:00:00Z",
                    "sha256": "abc",
                    "scf_merge_strategy": "replace",
                }
            ],
        }
        (github_root / ".scf-manifest.json").write_text(
            json.dumps(legacy), encoding="utf-8"
        )
        manager = engine.ManifestManager(github_root)
        entries = manager.load()
        assert len(entries) == 1
        assert entries[0]["package"] == "spark-base"

    def test_reads_v2_0_manifest(self, github_root: Path) -> None:
        legacy = {"schema_version": "2.0", "entries": []}
        (github_root / ".scf-manifest.json").write_text(
            json.dumps(legacy), encoding="utf-8"
        )
        manager = engine.ManifestManager(github_root)
        assert manager.load() == []

    def test_rejects_unsupported_schema(self, github_root: Path) -> None:
        future = {"schema_version": "9.9", "entries": [{"file": "x"}]}
        (github_root / ".scf-manifest.json").write_text(
            json.dumps(future), encoding="utf-8"
        )
        manager = engine.ManifestManager(github_root)
        assert manager.load() == []

    def test_v2_to_v3_upgrade_on_save(self, github_root: Path) -> None:
        legacy = {
            "schema_version": "2.1",
            "entries": [
                {
                    "file": "x.md",
                    "package": "p",
                    "package_version": "1.0",
                    "installed_at": "2026-01-01T00:00:00Z",
                    "sha256": "a",
                    "scf_merge_strategy": "replace",
                }
            ],
        }
        path = github_root / ".scf-manifest.json"
        path.write_text(json.dumps(legacy), encoding="utf-8")
        manager = engine.ManifestManager(github_root)
        entries = manager.load()
        manager.save(entries)
        payload = json.loads(path.read_text("utf-8"))
        assert payload["schema_version"] == "3.0"
        assert "overrides" in payload


class TestOverrideCycleV3:
    def test_write_override_emits_v3_summary(self, github_root: Path) -> None:
        manager = engine.ManifestManager(github_root)
        manager.write_override("agents", "spark-guide", "# custom\n")
        payload = json.loads((github_root / ".scf-manifest.json").read_text("utf-8"))
        assert payload["schema_version"] == "3.0"
        assert any(
            o["type"] == "agents" and o["name"] == "spark-guide"
            for o in payload["overrides"]
        )
        assert (
            github_root / "overrides" / "agents" / "spark-guide.agent.md"
        ).is_file()

    def test_drop_override_clears_summary(self, github_root: Path) -> None:
        manager = engine.ManifestManager(github_root)
        manager.write_override("agents", "spark-guide", "# custom\n")
        existed = manager.drop_override("agents", "spark-guide")
        assert existed is True
        payload = json.loads((github_root / ".scf-manifest.json").read_text("utf-8"))
        assert payload["overrides"] == []
        assert not (
            github_root / "overrides" / "agents" / "spark-guide.agent.md"
        ).is_file()

    def test_invalid_override_type_raises(self, github_root: Path) -> None:
        manager = engine.ManifestManager(github_root)
        with pytest.raises(ValueError):
            manager.write_override("bogus", "x", "content")
