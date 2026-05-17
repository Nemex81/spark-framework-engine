# tests/test_engine_coherence.py
import re
from pathlib import Path

_ENGINE_PATH = Path(__file__).parent.parent / "spark" / "boot" / "engine.py"
_SEQUENCE_PATH = Path(__file__).parent.parent / "spark" / "boot" / "sequence.py"
_TOOLS_RESOURCES_PATH = Path(__file__).parent.parent / "spark" / "boot" / "tools_resources.py"
_TOOLS_OVERRIDE_PATH = Path(__file__).parent.parent / "spark" / "boot" / "tools_override.py"
_TOOLS_BOOTSTRAP_PATH = Path(__file__).parent.parent / "spark" / "boot" / "tools_bootstrap.py"
_TOOLS_POLICY_PATH = Path(__file__).parent.parent / "spark" / "boot" / "tools_policy.py"
_TOOLS_PACKAGES_PATH = Path(__file__).parent.parent / "spark" / "boot" / "tools_packages.py"
_TOOLS_PACKAGES_QUERY_PATH = Path(__file__).parent.parent / "spark" / "boot" / "tools_packages_query.py"
_TOOLS_PACKAGES_INSTALL_PATH = Path(__file__).parent.parent / "spark" / "boot" / "tools_packages_install.py"
_TOOLS_PACKAGES_UPDATE_PATH = Path(__file__).parent.parent / "spark" / "boot" / "tools_packages_update.py"
_TOOLS_PACKAGES_REMOVE_PATH = Path(__file__).parent.parent / "spark" / "boot" / "tools_packages_remove.py"
_TOOLS_PACKAGES_DIAGNOSTICS_PATH = Path(__file__).parent.parent / "spark" / "boot" / "tools_packages_diagnostics.py"
_TOOLS_PLUGINS_PATH = Path(__file__).parent.parent / "spark" / "boot" / "tools_plugins.py"
_CONSTANTS = Path(__file__).parent.parent / "spark" / "core" / "constants.py"
_MODELS = Path(__file__).parent.parent / "spark" / "core" / "models.py"
_CHANGELOG = Path(__file__).parent.parent / "CHANGELOG.md"


def test_tool_counter_consistency():
    """
    Conta i decorator @_register_tool( nel sorgente via regex,
    estrae il valore nel commento Tools (N) e verifica che coincida.

    AP.3: il log "Tools registered: N total" deve essere dinamico in engine.py
    (usa %d, non hardcoded) e sequence.py non deve avere il log hardcoded.

    NOTA: a partire da v3.0 il pattern di registrazione tool usa
    l'helper @_register_tool("name") invece di @self._mcp.tool diretto.
    NOTA D.1+: i tool factory (tools_resources.py e successivi) contribuiscono
    al conteggio totale; vengono inclusi nel source concatenato.
    """

    def _read(p: Path) -> str:
        return p.read_text(encoding="utf-8") if p.exists() else ""

    source = (
        _ENGINE_PATH.read_text(encoding="utf-8")
        + "\n"
        + _SEQUENCE_PATH.read_text(encoding="utf-8")
        + "\n"
        + _read(_TOOLS_RESOURCES_PATH)
        + "\n"
        + _read(_TOOLS_OVERRIDE_PATH)
        + "\n"
        + _read(_TOOLS_BOOTSTRAP_PATH)
        + "\n"
        + _read(_TOOLS_POLICY_PATH)
        + "\n"
        + _read(_TOOLS_PACKAGES_QUERY_PATH)
        + "\n"
        + _read(_TOOLS_PACKAGES_INSTALL_PATH)
        + "\n"
        + _read(_TOOLS_PACKAGES_UPDATE_PATH)
        + "\n"
        + _read(_TOOLS_PACKAGES_REMOVE_PATH)
        + "\n"
        + _read(_TOOLS_PACKAGES_DIAGNOSTICS_PATH)
        + "\n"
        + _read(_TOOLS_PLUGINS_PATH)
    )

    actual = len(re.findall(r"@_register_tool\(", source))

    comment_match = re.search(r"Tools \((\d+)\)", source)

    assert comment_match, "Commento 'Tools (N)' non trovato nel sorgente"

    comment_n = int(comment_match.group(1))

    assert actual == comment_n, f"Tool reali: {actual}, commento: {comment_n}"

    # AP.3: verifica che il log sia dinamico (usa %d, non hardcoded) in engine.py.
    engine_source = _ENGINE_PATH.read_text(encoding="utf-8")
    assert "Tools registered: %d total" in engine_source, (
        "register_tools() in engine.py deve loggare il contatore dinamico: "
        "'Tools registered: %d total'"
    )

    # AP.3: verifica che sequence.py NON abbia il log hardcoded.
    sequence_source = _SEQUENCE_PATH.read_text(encoding="utf-8")
    assert not re.search(r"Tools registered: \d+ total", sequence_source), (
        "sequence.py non deve avere il log hardcoded 'Tools registered: N total' "
        "(AP.3: il log è ora dinamico in engine.py)"
    )


def test_engine_version_changelog_alignment():
    """
    Verifica che ENGINE_VERSION nel sorgente coincida
    con la prima voce versionale di CHANGELOG.md.

    Dopo Fase 0, la costante canonica vive in ``spark/core/constants.py``;
    l'hub ``spark-framework-engine.py`` la re-esporta.
    """
    constants_source = _CONSTANTS.read_text(encoding="utf-8")
    version_match = re.search(r'ENGINE_VERSION: str = "([^"]+)"', constants_source)
    assert version_match, "ENGINE_VERSION non trovata in spark/core/constants.py"
    engine_ver = version_match.group(1)

    changelog = _CHANGELOG.read_text(encoding="utf-8")
    # Salta [Unreleased] — cerca la prima voce versionale numerica.
    entry_match = re.search(r"## \[(\d[^\]]+)\]", changelog)
    assert entry_match, "Nessuna voce versionale trovata in CHANGELOG.md"
    changelog_ver = entry_match.group(1)

    assert engine_ver == changelog_ver, (
        f"ENGINE_VERSION={engine_ver} non allineata con CHANGELOG={changelog_ver}"
    )


def test_changelog_unreleased_section_is_clean():
    """Verifica che [Unreleased] non contenga sezioni ### duplicate.

    La sezione può contenere il placeholder ``<!-- nessuna modifica pendente -->``
    oppure voci strutturate (Added, Changed, Removed, Fixed, ...), ma non
    deve mai contenere la stessa intestazione ### ripetuta due o più volte
    nella stessa entry [Unreleased] (anomalia strutturale markdownlint MD024).
    """
    changelog = _CHANGELOG.read_text(encoding="utf-8")

    # Estrae il testo della sezione [Unreleased] fino alla prossima sezione ##
    unreleased_match = re.search(
        r"## \[Unreleased\](.*?)(?=^## \[)", changelog, re.DOTALL | re.MULTILINE
    )
    assert unreleased_match, "Sezione [Unreleased] non trovata in CHANGELOG.md"

    unreleased_body = unreleased_match.group(1)

    # Non deve contenere intestazioni ### duplicate nella stessa entry
    headers = re.findall(r"^###\s+(\S.*)", unreleased_body, re.MULTILINE)
    duplicates = [h for h in headers if headers.count(h) > 1]
    assert not duplicates, (
        f"[Unreleased] contiene sezioni ### duplicate: {sorted(set(duplicates))}. "
        "Ogni sottosezione (Added, Changed, Removed, Fixed, ...) deve comparire "
        "al massimo una volta per entry [Unreleased]."
    )


def test_tool_payload_models_defined():
    """Verifica che SparkToolResult, SparkErrorResult e SparkDiagnosticResult
    siano definiti in spark/core/models.py con i campi minimi richiesti."""
    models_src = _MODELS.read_text(encoding="utf-8")

    # SparkToolResult deve avere success e status
    assert "class SparkToolResult" in models_src, (
        "SparkToolResult non trovato in spark/core/models.py"
    )
    assert "success: bool" in models_src, (
        "Campo 'success: bool' mancante in SparkToolResult"
    )

    # SparkErrorResult deve avere success ed error
    assert "class SparkErrorResult" in models_src, (
        "SparkErrorResult non trovato in spark/core/models.py — aggiungilo per TASK 2"
    )
    assert "error: str" in models_src, (
        "Campo 'error: str' mancante in SparkErrorResult"
    )

    # SparkDiagnosticResult deve avere success e checks
    assert "class SparkDiagnosticResult" in models_src, (
        "SparkDiagnosticResult non trovato in spark/core/models.py — aggiungilo per TASK 2"
    )
    assert "checks: list" in models_src, (
        "Campo 'checks: list' mancante in SparkDiagnosticResult"
    )


def test_tool_payload_success_and_error_fields():
    """Verifica che i tool MCP chiave restituiscano sempre 'success' nei path di errore."""
    # I tool che devono avere 'success' ed 'error' nei percorsi di fallimento:
    tools_to_check = [
        (_TOOLS_PACKAGES_INSTALL_PATH, "scf_install_package"),
        (_TOOLS_PACKAGES_UPDATE_PATH, "scf_update_package"),
        (_TOOLS_PACKAGES_REMOVE_PATH, "scf_remove_package"),
        (_TOOLS_BOOTSTRAP_PATH, "scf_bootstrap_workspace"),
        (_TOOLS_PACKAGES_DIAGNOSTICS_PATH, "scf_get_framework_version"),
    ]
    for tool_path, tool_name in tools_to_check:
        src = tool_path.read_text(encoding="utf-8")
        assert '"success": False' in src or '"success": True' in src, (
            f"Tool {tool_name} in {tool_path.name} non usa il campo 'success' standard"
        )
        assert '"error"' in src or "'error'" in src, (
            f"Tool {tool_name} in {tool_path.name} non usa il campo 'error' standard"
        )
