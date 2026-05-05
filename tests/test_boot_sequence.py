from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

_spec = importlib.util.spec_from_file_location("spark_framework_engine", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["spark_framework_engine"] = _module
assert _spec is not None
assert _spec.loader is not None
_spec.loader.exec_module(_module)  # type: ignore[union-attr]


def test_build_app_triggers_minimal_bootstrap_for_user_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setenv("WORKSPACE_FOLDER", str(project_root))

    called: dict[str, bool] = {"value": False}

    def _fake_ensure_minimal_bootstrap(self) -> dict[str, object]:
        called["value"] = True
        return {"success": True, "status": "bootstrapped"}

    monkeypatch.setattr(
        _module.SparkFrameworkEngine,
        "ensure_minimal_bootstrap",
        _fake_ensure_minimal_bootstrap,
    )

    _module._build_app(engine_root=_ENGINE_PATH.parent)

    assert called["value"] is True