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
_CONSTANTS = Path(__file__).parent.parent / "spark" / "core" / "constants.py"
_CHANGELOG = Path(__file__).parent.parent / "CHANGELOG.md"


def test_tool_counter_consistency():
    """
    Conta i decorator @_register_tool( nel sorgente via regex,
    estrae il valore nel commento Tools (N) e nel log Tools registered: N total,
    e asserisce che i tre numeri coincidano.

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
        + _read(_TOOLS_PACKAGES_PATH)
    )

    actual = len(re.findall(r"@_register_tool\(", source))

    comment_match = re.search(r"Tools \((\d+)\)", source)
    log_match = re.search(r"Tools registered: (\d+) total", source)

    assert comment_match, "Commento 'Tools (N)' non trovato nel sorgente"
    assert log_match, "Log 'Tools registered: N total' non trovato nel sorgente"

    comment_n = int(comment_match.group(1))
    log_n = int(log_match.group(1))

    assert actual == comment_n, f"Tool reali: {actual}, commento: {comment_n}"
    assert actual == log_n, f"Tool reali: {actual}, log: {log_n}"


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
