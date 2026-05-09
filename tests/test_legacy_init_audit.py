"""Tests per audit init utente con file preesistenti nel workspace.

Copre due scenari:
- Scenario X: file non-SPARK con nome identico a un file bootstrap SPARK
- Scenario Y: file SPARK con versione obsoleta o deprecata
- Scenario Y-2 (GAP-Y-2): frontmatter-only update con force=True

AUDIT: spark-init-legacy-audit-v1.0
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_ENGINE_PATH = Path(__file__).parent.parent / "spark-framework-engine.py"

_spec = importlib.util.spec_from_file_location("spark_framework_engine_legacy_audit", _ENGINE_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules.setdefault("spark_framework_engine_legacy_audit", _module)
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

SparkFrameworkEngine: Any = _module.SparkFrameworkEngine
WorkspaceContext: Any = _module.WorkspaceContext
FrameworkInventory: Any = _module.FrameworkInventory

from spark.boot.tools_bootstrap import _apply_frontmatter_only_update  # noqa: E402


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self) -> Any:
        def _decorator(func: Any) -> Any:
            self.tools[func.__name__] = func
            return func
        return _decorator

    def resource(self, *_args: Any, **_kwargs: Any) -> Any:
        def _decorator(func: Any) -> Any:
            return func
        return _decorator


@pytest.fixture()
def workspace_root(tmp_path: Path) -> Path:
    """Workspace temporaneo isolato per ogni test."""
    return tmp_path


@pytest.fixture()
def bootstrap_tool(workspace_root: Path) -> Any:
    """Tool scf_bootstrap_workspace istanziato su workspace temporaneo."""
    ctx = WorkspaceContext(
        workspace_root=workspace_root,
        github_root=workspace_root / ".github",
        engine_root=_ENGINE_PATH.parent,
    )
    inventory = FrameworkInventory(ctx)
    mcp = _FakeMCP()
    engine = SparkFrameworkEngine(mcp, ctx, inventory)
    engine.register_tools()
    return mcp.tools["scf_bootstrap_workspace"]


# ---------------------------------------------------------------------------
# SCENARIO X — File non-SPARK con nome identico
# ---------------------------------------------------------------------------

async def test_bootstrap_classifies_non_spark_conflict_file(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    """Scenario X: file non-SPARK preesistente con nome identico a un file bootstrap.

    Il preservation gate deve:
    - NON sovrascrivere il file utente (files_protected non vuoto)
    - Classificare il file in files_conflict_non_spark (non ha spark: true)
    - NON metterlo in files_conflict_spark_outdated
    """
    # Crea un file non-SPARK al path di un file bootstrap (copilot-instructions.md)
    target_dir = workspace_root / ".github"
    target_dir.mkdir(parents=True, exist_ok=True)
    non_spark_file = target_dir / "copilot-instructions.md"
    non_spark_file.write_text(
        "# User copilot instructions\n\nNo SPARK frontmatter here.\n",
        encoding="utf-8",
    )

    result = await bootstrap_tool()

    assert result["success"] is True
    # Il file deve essere protetto — non sovrascritto
    assert ".github/copilot-instructions.md" in result["files_protected"], (
        "Il file non-SPARK deve essere in files_protected"
    )
    # Classificazione: deve andare in files_conflict_non_spark
    assert "files_conflict_non_spark" in result, (
        "Il payload deve contenere files_conflict_non_spark"
    )
    assert ".github/copilot-instructions.md" in result["files_conflict_non_spark"], (
        "Il file non-SPARK deve essere classificato in files_conflict_non_spark"
    )
    # NON deve essere classificato come SPARK obsoleto
    assert "files_conflict_spark_outdated" in result, (
        "Il payload deve contenere files_conflict_spark_outdated"
    )
    assert ".github/copilot-instructions.md" not in result["files_conflict_spark_outdated"], (
        "Il file non-SPARK NON deve essere in files_conflict_spark_outdated"
    )
    # Il contenuto utente deve essere intatto
    assert non_spark_file.read_text(encoding="utf-8") == (
        "# User copilot instructions\n\nNo SPARK frontmatter here.\n"
    )


async def test_bootstrap_non_spark_conflict_payload_is_empty_on_clean_workspace(
    bootstrap_tool: Any,
) -> None:
    """Su workspace vergine, files_conflict_* deve essere vuoto."""
    result = await bootstrap_tool()

    assert result["success"] is True
    assert "files_conflict_non_spark" in result
    assert result["files_conflict_non_spark"] == []
    assert "files_conflict_spark_outdated" in result
    assert result["files_conflict_spark_outdated"] == []


# ---------------------------------------------------------------------------
# SCENARIO Y — File SPARK con versione obsoleta
# ---------------------------------------------------------------------------

async def test_bootstrap_classifies_spark_outdated_conflict_file(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    """Scenario Y: file SPARK obsoleto preesistente al path di un file bootstrap.

    Il preservation gate deve:
    - NON sovrascrivere il file utente (files_protected non vuoto)
    - Classificare il file in files_conflict_spark_outdated (ha spark: true)
    - NON metterlo in files_conflict_non_spark
    """
    # Crea un file .md con frontmatter SPARK (versione obsoleta) al path di un file bootstrap
    target_dir = workspace_root / ".github" / "instructions"
    target_dir.mkdir(parents=True, exist_ok=True)
    spark_outdated_file = target_dir / "workflow-standard.instructions.md"
    spark_outdated_file.write_text(
        "---\nspark: true\nscf_owner: spark-base\nversion: 0.1.0\n---\n\n"
        "# Workflow Standard (vecchia versione)\n\nContenuto obsoleto.\n",
        encoding="utf-8",
    )

    result = await bootstrap_tool()

    assert result["success"] is True
    # Il file deve essere protetto
    assert ".github/instructions/workflow-standard.instructions.md" in result["files_protected"], (
        "Il file SPARK obsoleto deve essere in files_protected"
    )
    # Classificazione: deve andare in files_conflict_spark_outdated
    assert "files_conflict_spark_outdated" in result, (
        "Il payload deve contenere files_conflict_spark_outdated"
    )
    assert ".github/instructions/workflow-standard.instructions.md" in result["files_conflict_spark_outdated"], (
        "Il file SPARK obsoleto deve essere in files_conflict_spark_outdated"
    )
    # NON deve essere classificato come non-SPARK
    assert "files_conflict_non_spark" in result
    assert ".github/instructions/workflow-standard.instructions.md" not in result["files_conflict_non_spark"], (
        "Il file SPARK NON deve essere in files_conflict_non_spark"
    )
    # Il contenuto originale deve essere intatto
    assert "0.1.0" in spark_outdated_file.read_text(encoding="utf-8")


async def test_bootstrap_spark_outdated_includes_version_details(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    """Scenario Y: il payload include spark_outdated_details con versione esistente.

    Verifica che per ogni file SPARK obsoleto protetto, il payload riporti
    la versione dichiarata nel frontmatter del file esistente.
    """
    target_dir = workspace_root / ".github" / "instructions"
    target_dir.mkdir(parents=True, exist_ok=True)
    spark_outdated_file = target_dir / "workflow-standard.instructions.md"
    old_version = "0.2.5"
    spark_outdated_file.write_text(
        f"---\nspark: true\nscf_owner: spark-base\nversion: {old_version}\n---\n\n"
        "# Workflow Standard (vecchia versione)\n",
        encoding="utf-8",
    )

    result = await bootstrap_tool()

    assert "spark_outdated_details" in result, (
        "Il payload deve contenere spark_outdated_details"
    )
    details = result["spark_outdated_details"]
    assert isinstance(details, list)

    # Cerca il dettaglio per il file specifico
    matching = [
        d for d in details
        if ".github/instructions/workflow-standard.instructions.md" in d.get("file", "")
    ]
    assert matching, "Deve esserci un dettaglio per il file SPARK obsoleto"
    assert matching[0].get("existing_version") == old_version, (
        f"La versione esistente deve essere {old_version}"
    )


async def test_bootstrap_non_md_file_classified_as_non_spark(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    """Un file non-.md preesistente viene classificato come non-SPARK (nessun frontmatter).

    Verifica che la classificazione non fallisca su file non testuali o non markdown.
    """
    # spark-packages.json è un file .json (non markdown) nel perimetro bootstrap
    target_dir = workspace_root / ".github"
    target_dir.mkdir(parents=True, exist_ok=True)
    json_file = target_dir / "spark-packages.json"
    json_file.write_text(
        '{"user_custom": true, "packages": []}\n',
        encoding="utf-8",
    )

    result = await bootstrap_tool()

    assert result["success"] is True
    assert "files_conflict_non_spark" in result
    # Il file .json deve andare in non_spark (non ha frontmatter SPARK)
    assert ".github/spark-packages.json" in result["files_protected"] or (
        ".github/spark-packages.json" not in result["files_conflict_spark_outdated"]
    ), "Un file .json non-SPARK non deve mai finire in files_conflict_spark_outdated"


# ---------------------------------------------------------------------------
# SCENARIO Y-2 (GAP-Y-2) — Frontmatter-only update con force=True
# ---------------------------------------------------------------------------


async def test_force_true_updates_frontmatter_only_for_spark_outdated(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    """GAP-Y-2: force=True su file SPARK obsoleto aggiorna solo il frontmatter.

    Verifica che quando un file SPARK preesistente viene incontrato con force=True,
    il bootstrap aggiorni solo il blocco frontmatter YAML (dal sorgente engine)
    e preservi il body utente invariato.
    """
    # Prepara un file SPARK obsoleto con body personalizzato
    target_dir = workspace_root / ".github" / "instructions"
    target_dir.mkdir(parents=True, exist_ok=True)
    spark_file = target_dir / "workflow-standard.instructions.md"
    user_body = "\n\n# Old Body Title\n\nUser custom section preserved here.\n"
    old_frontmatter = "---\nspark: true\nscf_owner: spark-base\nversion: 0.1.0\n---"
    spark_file.write_text(old_frontmatter + user_body, encoding="utf-8")

    result = await bootstrap_tool(force=True)

    assert result["success"] is True
    # Il file deve essere stato aggiornato (frontmatter-only)
    assert "files_updated_frontmatter_only" in result, (
        "Il payload deve contenere files_updated_frontmatter_only"
    )
    assert ".github/instructions/workflow-standard.instructions.md" in result[
        "files_updated_frontmatter_only"
    ], "Il file SPARK obsoleto deve essere in files_updated_frontmatter_only"
    # Deve essere in files_written (backward compat)
    assert ".github/instructions/workflow-standard.instructions.md" in result["files_written"], (
        "Il file aggiornato deve essere in files_written"
    )
    # NON deve essere in files_protected
    assert ".github/instructions/workflow-standard.instructions.md" not in result["files_protected"], (
        "Il file aggiornato NON deve essere in files_protected"
    )
    # Verifica il contenuto: body utente conservato, frontmatter aggiornato
    final_content = spark_file.read_text(encoding="utf-8")
    assert "User custom section preserved here." in final_content, (
        "Il body utente deve essere preservato dopo il frontmatter-only update"
    )
    # Il frontmatter del file sorgente engine deve essere presente (contiene spark: true)
    assert "spark: true" in final_content, (
        "Il frontmatter engine (spark: true) deve essere presente nel file aggiornato"
    )
    # Il vecchio frontmatter (versione 0.1.0) non deve più essere presente nel campo version
    # (il frontmatter è stato sostituito da quello engine che non ha il campo version)
    assert "version: 0.1.0" not in final_content, (
        "Il campo version: 0.1.0 dell'old frontmatter non deve essere nel file aggiornato"
    )


async def test_force_true_preserves_user_body_when_spark_outdated(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    """GAP-Y-2: il body utente completo è preservato dopo frontmatter-only update.

    Test dedicato al contenuto del file risultante: il body deve essere
    identico a quello dell'utente (non del sorgente engine).
    """
    target_dir = workspace_root / ".github" / "instructions"
    target_dir.mkdir(parents=True, exist_ok=True)
    spark_file = target_dir / "workflow-standard.instructions.md"
    user_body_marker = "CUSTOM_MARKER_THAT_ONLY_USER_HAS_12345"
    user_content = (
        f"---\nspark: true\nversion: 0.0.1\n---\n\n"
        f"# Body utente\n\n{user_body_marker}\n\nAltre sezioni custom.\n"
    )
    spark_file.write_text(user_content, encoding="utf-8")

    result = await bootstrap_tool(force=True)

    assert result["success"] is True
    final_content = spark_file.read_text(encoding="utf-8")
    assert user_body_marker in final_content, (
        "Il marker del body utente deve essere preservato nel file aggiornato"
    )


async def test_force_true_non_spark_file_still_gets_full_overwrite(
    workspace_root: Path,
    bootstrap_tool: Any,
) -> None:
    """GAP-Y-2: un file non-SPARK con force=True riceve sovrascrittura completa.

    Verifica che il comportamento invariato per file non-SPARK: force=True
    sovrascrive completamente, NON applica frontmatter-only.
    """
    # Crea un file non-SPARK (nessun frontmatter) al path di un file bootstrap
    target_dir = workspace_root / ".github"
    target_dir.mkdir(parents=True, exist_ok=True)
    non_spark_file = target_dir / "copilot-instructions.md"
    non_spark_file.write_text("# User custom without frontmatter\n", encoding="utf-8")

    result = await bootstrap_tool(force=True)

    assert result["success"] is True
    # NON deve essere in files_updated_frontmatter_only (non è SPARK)
    assert "files_updated_frontmatter_only" in result, (
        "Il payload deve contenere files_updated_frontmatter_only"
    )
    assert ".github/copilot-instructions.md" not in result["files_updated_frontmatter_only"], (
        "Un file non-SPARK NON deve andare in files_updated_frontmatter_only"
    )
    # Deve essere in files_written (sovrascrittura completa)
    assert ".github/copilot-instructions.md" in result["files_written"], (
        "Il file non-SPARK con force=True deve essere in files_written"
    )
    # Il contenuto deve essere sostituito da quello engine (non più user custom)
    final_content = non_spark_file.read_text(encoding="utf-8")
    assert "User custom without frontmatter" not in final_content, (
        "Il contenuto utente deve essere sostituito dal sorgente engine"
    )


async def test_force_true_spark_outdated_payload_on_clean_workspace(
    bootstrap_tool: Any,
) -> None:
    """GAP-Y-2: su workspace vergine files_updated_frontmatter_only deve essere vuoto."""
    result = await bootstrap_tool(force=True)

    assert result["success"] is True
    assert "files_updated_frontmatter_only" in result, (
        "Il payload deve sempre contenere files_updated_frontmatter_only"
    )
    assert result["files_updated_frontmatter_only"] == [], (
        "Su workspace vergine non ci sono file da aggiornare frontmatter-only"
    )


# ---------------------------------------------------------------------------
# Unit test per _apply_frontmatter_only_update
# ---------------------------------------------------------------------------


def test_apply_frontmatter_only_unit_builds_merged_content(
    tmp_path: Path,
) -> None:
    """Unit: _apply_frontmatter_only_update restituisce frontmatter engine + body utente."""
    source = tmp_path / "source.md"
    dest = tmp_path / "dest.md"
    source.write_text("---\nspark: true\nversion: 2.0\n---\n\n# Engine Body\n", encoding="utf-8")
    dest.write_text("---\nspark: true\nversion: 0.5\n---\n\n# User Body\n\nCustom section.\n", encoding="utf-8")

    result = _apply_frontmatter_only_update(source, dest)

    assert result is not None, "Deve restituire una stringa su input valido"
    # Frontmatter da source
    assert "version: 2.0" in result, "Il frontmatter del sorgente deve essere nel risultato"
    assert "version: 0.5" not in result, "Il vecchio frontmatter NON deve essere nel risultato"
    # Body da dest
    assert "# User Body" in result, "Il body utente deve essere nel risultato"
    assert "Custom section." in result, "Le sezioni custom utente devono essere nel risultato"
    # Il body engine NON deve essere nel risultato
    assert "# Engine Body" not in result, "Il body engine NON deve essere nel risultato"


def test_apply_frontmatter_only_unit_returns_none_on_malformed_source(
    tmp_path: Path,
) -> None:
    """Unit: _apply_frontmatter_only_update ritorna None se il source ha frontmatter malformato."""
    source = tmp_path / "source.md"
    dest = tmp_path / "dest.md"
    # Source senza frontmatter (nessun ---)
    source.write_text("# Engine content without frontmatter\n", encoding="utf-8")
    dest.write_text("---\nspark: true\nversion: 0.5\n---\n\n# User Body\n", encoding="utf-8")

    result = _apply_frontmatter_only_update(source, dest)

    assert result is None, "Deve restituire None se il sorgente non ha frontmatter"


def test_apply_frontmatter_only_unit_handles_empty_user_body(
    tmp_path: Path,
) -> None:
    """Unit: _apply_frontmatter_only_update gestisce correttamente un body utente vuoto."""
    source = tmp_path / "source.md"
    dest = tmp_path / "dest.md"
    source.write_text("---\nspark: true\nversion: 2.0\n---\n\n# Engine Body\n", encoding="utf-8")
    # Dest con solo frontmatter, nessun body
    dest.write_text("---\nspark: true\nversion: 0.5\n---", encoding="utf-8")

    result = _apply_frontmatter_only_update(source, dest)

    assert result is not None, "Deve restituire una stringa anche con body vuoto"
    assert result.startswith("---"), "Il risultato deve iniziare con il frontmatter"
    assert "version: 2.0" in result, "Il frontmatter sorgente deve essere presente"

