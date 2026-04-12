from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_MODULE_PATH = Path(__file__).parent.parent / "spark-init.py"
_SPEC = importlib.util.spec_from_file_location("spark_init", _MODULE_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules["spark_init"] = _MODULE
_SPEC.loader.exec_module(_MODULE)


def test_build_workspace_template_returns_empty_settings_and_root_mcp(tmp_path: Path) -> None:
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    engine_script = tmp_path / "spark-framework-engine.py"

    workspace_data = _MODULE._build_workspace_template(project_root, engine_script)

    assert workspace_data["settings"] == {}
    assert "mcp" in workspace_data
    assert "servers" in workspace_data["mcp"]
    assert workspace_data["mcp"]["servers"][_MODULE.SERVER_ID]["args"] == [str(engine_script)]


def test_update_existing_workspace_moves_legacy_settings_mcp_to_root_and_preserves_other_keys(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    engine_script = tmp_path / "spark-framework-engine.py"
    workspace_path = project_root / "demo.code-workspace"
    workspace_path.write_text(
        """{
  "folders": [{"path": "."}],
  "settings": {
    "editor.tabSize": 4,
    "mcp": {
      "servers": {
        "legacy": {
          "type": "stdio"
        }
      }
    }
  },
  "extensions": {
    "recommendations": ["ms-python.python"]
  },
  "launch": {
    "configurations": []
  }
}
""",
        encoding="utf-8",
    )

    success, _message = _MODULE._update_existing_workspace(
        workspace_path,
        project_root,
        engine_script,
    )

    assert success is True

    workspace_data = _MODULE.json.loads(workspace_path.read_text(encoding="utf-8"))

    assert workspace_data["settings"] == {"editor.tabSize": 4}
    assert "mcp" in workspace_data
    assert "mcp" not in workspace_data["settings"]
    assert workspace_data["extensions"] == {
        "recommendations": ["ms-python.python"]
    }
    assert workspace_data["launch"] == {"configurations": []}
    assert workspace_data["mcp"]["servers"][_MODULE.SERVER_ID] == _MODULE._build_server_config(
        project_root,
        engine_script,
    )


def test_update_existing_workspace_returns_error_when_root_mcp_is_not_an_object(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    engine_script = tmp_path / "spark-framework-engine.py"
    workspace_path = project_root / "demo.code-workspace"
    workspace_path.write_text(
        """{
  "settings": {},
  "mcp": []
}
""",
        encoding="utf-8",
    )

    success, message = _MODULE._update_existing_workspace(
        workspace_path,
        project_root,
        engine_script,
    )

    assert success is False
    assert "la chiave 'mcp' deve essere un oggetto JSON" in message