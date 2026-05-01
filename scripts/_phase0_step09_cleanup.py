"""Phase 0 — Step 09: rimuove definizioni originali dal hub.

Ogni blocco estratto nei sessioni precedenti (Steps 08-A/B/C/D) viene
sostituito con un commento-stub nella stessa posizione del file hub.

Operazioni (applicate in ordine INVERSO di posizione nel file):
  G  _build_app() + entry point  → aggiorna firma + engine_root call
  F  SparkFrameworkEngine        → spark.boot.engine
  E  build_workspace_info        → spark.inventory.framework
  D  EngineInventory             → spark.inventory.engine
  C  FrameworkInventory          → spark.inventory.framework
  B  WorkspaceLocator            → spark.workspace.locator
  A  policy helpers              → spark.workspace.policy
"""
from __future__ import annotations

from pathlib import Path

HUB = Path(__file__).resolve().parent.parent / "spark-framework-engine.py"

# ---------------------------------------------------------------------------
# Ops: (start_marker, end_marker, replacement)
# start_marker  — testo esatto che inizia il blocco da rimuovere
# end_marker    — testo esatto che SEGUE immediatamente il blocco (rimane)
# replacement   — testo da inserire al posto del blocco rimosso
#
# Le ops sono in ordine di posizione nel file (A=prima, G=ultima).
# Lo script le applica in ordine INVERSO per non spostare gli offset.
# ---------------------------------------------------------------------------

OPS: list[tuple[str, str, str]] = [
    # A — update policy helpers
    (
        "\n\ndef _default_update_policy() -> dict[str, Any]:\n",
        "\n# ---------------------------------------------------------------------------\n# WorkspaceLocator\n# ---------------------------------------------------------------------------\n",
        "\n\n# Update policy helpers (_default_update_policy, _default_update_policy_payload,\n"
        "# _update_policy_path, _normalize_update_mode, _validate_update_mode,\n"
        "# _read_update_policy_payload, _write_update_policy_payload)\n"
        "# moved to spark.workspace.policy (re-exported in header).\n",
    ),
    # B — WorkspaceLocator class
    (
        "\nclass WorkspaceLocator:\n",
        "\n# ---------------------------------------------------------------------------\n# Standalone parsers\n# ---------------------------------------------------------------------------\n",
        "\n# WorkspaceLocator moved to spark.workspace.locator (re-exported in header).\n",
    ),
    # C — FrameworkInventory class
    (
        "\nclass FrameworkInventory:\n",
        "\n# ---------------------------------------------------------------------------\n# EngineInventory (v2.4.0",
        "\n# FrameworkInventory moved to spark.inventory.framework (re-exported in header).\n",
    ),
    # D — EngineInventory class
    (
        "\nclass EngineInventory(FrameworkInventory):\n",
        "\n# ---------------------------------------------------------------------------\n# workspace-info builder\n# ---------------------------------------------------------------------------\n",
        "\n# EngineInventory moved to spark.inventory.engine (re-exported in header).\n",
    ),
    # E — build_workspace_info function
    (
        "\ndef build_workspace_info(context: WorkspaceContext, inventory: FrameworkInventory) -> dict[str, Any]:\n",
        "\n# ---------------------------------------------------------------------------\n# ManifestManager (A3",
        "\n# build_workspace_info moved to spark.inventory.framework (re-exported in header).\n",
    ),
    # F — SparkFrameworkEngine section header + class (4460+ lines)
    (
        "\n# ---------------------------------------------------------------------------\n# SparkFrameworkEngine — Resources (15) and Tools (40)\n# ---------------------------------------------------------------------------\n\n\nclass SparkFrameworkEngine:\n",
        "\n# ---------------------------------------------------------------------------\n# Entry point\n# ---------------------------------------------------------------------------\n",
        "\n# SparkFrameworkEngine moved to spark.boot.engine (re-exported in header).\n\n\n",
    ),
    # G — _build_app original + old entry point → new entry point with engine_root
    (
        "\ndef _build_app() -> FastMCP:\n",
        "\nif __name__ == \"__main__\":\n    _build_app().run(transport=\"stdio\")\n",
        "\n",
    ),
]

# Separate simple replacement for entry point (after G removes old function)
ENTRY_POINT_OLD = '\nif __name__ == "__main__":\n    _build_app().run(transport="stdio")\n'
ENTRY_POINT_NEW = (
    '\nif __name__ == "__main__":\n'
    "    _build_app(engine_root=Path(__file__).resolve().parent).run(transport=\"stdio\")\n"
)


def main() -> None:
    text = HUB.read_text(encoding="utf-8")
    original_size = len(text)

    # Locate all ops in text and sort by position DESCENDING
    located: list[tuple[int, int, str, str]] = []
    for start_marker, end_marker, replacement in OPS:
        s = text.find(start_marker)
        if s == -1:
            print(f"WARN: start marker not found: {start_marker[:60]!r}")
            continue
        e = text.find(end_marker, s + len(start_marker))
        if e == -1:
            print(f"WARN: end marker not found: {end_marker[:60]!r}")
            continue
        located.append((s, e, replacement, start_marker[:60]))

    located.sort(key=lambda x: x[0], reverse=True)

    for s, e, repl, label in located:
        removed = e - s
        print(f"  removing {removed:6d} chars at offset {s:7d}: {label!r}")
        text = text[:s] + repl + text[e:]

    # Apply entry point update (after _build_app removal the old `if __name__` is still there)
    if ENTRY_POINT_OLD in text:
        text = text.replace(ENTRY_POINT_OLD, ENTRY_POINT_NEW, 1)
        print(f"  updated entry point: added engine_root=Path(__file__).resolve().parent")
    else:
        print("WARN: entry point pattern not found — manual check required")

    HUB.write_text(text, encoding="utf-8")
    print(f"\nDone. {original_size} → {len(text)} bytes ({original_size - len(text):+d})")


if __name__ == "__main__":
    main()
