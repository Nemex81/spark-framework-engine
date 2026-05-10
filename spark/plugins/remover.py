"""Modulo spark.plugins.remover — rimozione plugin dal workspace.

Rimuove i file dichiarati in ``PluginRecord.files`` dal workspace utente
tramite ``WorkspaceWriteGateway``, preservando i file modificati dall'utente
(SHA mismatch in ManifestManager). Gestisce anche la rimozione delle
referenze ``#file:`` da ``copilot-instructions.md``.

Logica ereditata (riscritta nel nuovo contesto senza import circolari da):
- ``spark.boot.lifecycle._remove_workspace_files_v3``
"""
from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from spark.plugins.schema import PluginRecord

if TYPE_CHECKING:
    from spark.manifest.gateway import WorkspaceWriteGateway
    from spark.manifest.manifest import ManifestManager

# Sezione plugin in copilot-instructions.md (deve coincidere con installer.py).
_PLUGIN_SECTION_HEADER: str = (
    "# Plugin instructions (managed by SPARK Plugin Manager \u2014 do not edit manually)"
)


def _dedupe_preserving_order(items: list[str]) -> list[str]:
    """Deduplica una lista preservando l'ordine di prima occorrenza."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


class PluginRemover:
    """Rimuove i file di un plugin dal workspace utente.

    Applica il preservation gate: i file modificati dall'utente rispetto
    allo SHA registrato in ``ManifestManager`` vengono preservati e non
    eliminati. I file non tracciati nel manifest vengono preservati per
    sicurezza con un warning su stderr.

    Attributes:
        _workspace_root: Path assoluto alla root del workspace utente.
        _github_root: Path assoluto a ``<workspace>/.github/``.
        _manifest: Istanza di ManifestManager per i controlli SHA.
        _gateway: Istanza di WorkspaceWriteGateway per le eliminazioni.
    """

    def __init__(
        self,
        workspace_root: Path,
        manifest_manager: ManifestManager,
        gateway: WorkspaceWriteGateway,
    ) -> None:
        """Inizializza il remover con le dipendenze già istanziate.

        Args:
            workspace_root: Path assoluto alla root del workspace utente.
            manifest_manager: ManifestManager attivo per il workspace.
            gateway: WorkspaceWriteGateway per le eliminazioni da ``.github/``.
        """
        self._workspace_root = workspace_root
        self._github_root = workspace_root / ".github"
        self._manifest = manifest_manager
        self._gateway = gateway

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def remove_files(self, record: PluginRecord) -> list[str]:
        """Rimuove dal workspace i file del plugin non modificati dall'utente.

        Per ogni file in ``record.files``:
        1. Verifica che il file esista nel workspace.
        2. Controlla gli owner nel manifest: preserva se owned da altri pacchetti.
        3. Applica il preservation gate SHA via ``ManifestManager.is_user_modified``.
        4. Elimina via ``WorkspaceWriteGateway.delete``.

        I file non tracciati nel manifest vengono preservati per sicurezza
        e loggati come warning su stderr.

        Args:
            record: PluginRecord del plugin da rimuovere, con la lista
                dei file installati e il ``pkg_id``.

        Returns:
            Lista dei path relativi al workspace dei file rimossi con successo.
        """
        if not record.files:
            return []

        removed: list[str] = []

        for file_path in record.files:
            if not isinstance(file_path, str) or not file_path:
                continue

            # I path sono relativi al workspace (es. ".github/instructions/pkg.md").
            github_rel = file_path.removeprefix(".github/")
            target = self._github_root / github_rel

            # Salta i file già assenti sul disco.
            if not target.is_file():
                continue

            # Controlla gli owner del file nel manifest.
            owners = self._manifest.get_file_owners(github_rel)

            # Il file non è tracciato: preserva per sicurezza.
            if not owners:
                print(
                    f"[SPARK-PLUGINS][WARNING] File {file_path!r} non tracciato nel manifest, "
                    "preservato per sicurezza",
                    file=sys.stderr,
                )
                continue

            # Il file è posseduto da altri pacchetti: non toccare.
            other_owners = [o for o in owners if o != record.pkg_id]
            if other_owners and record.pkg_id not in owners:
                print(
                    f"[SPARK-PLUGINS][INFO] File {file_path!r} owned by {other_owners}, "
                    "preserved",
                    file=sys.stderr,
                )
                continue

            # Preservation gate: l'utente ha modificato il file dopo l'installazione.
            if self._manifest.is_user_modified(github_rel) is True:
                print(
                    f"[SPARK-PLUGINS][INFO] User-modified file preserved: {file_path!r}",
                    file=sys.stderr,
                )
                continue

            # Eliminazione tramite il gateway centralizzato.
            try:
                self._gateway.delete(github_rel, record.pkg_id)
                removed.append(file_path)
                print(
                    f"[SPARK-PLUGINS][INFO] Removed {file_path}",
                    file=sys.stderr,
                )
            except OSError as exc:
                print(
                    f"[SPARK-PLUGINS][ERROR] Cannot remove {file_path!r}: {exc}",
                    file=sys.stderr,
                )

        return removed

    def remove_workspace_files(
        self,
        package_id: str,
        pkg_manifest: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Rimuove dal workspace i file ``workspace_files`` + ``plugin_files`` del pacchetto.

        Equivalente migrato da ``spark.boot.lifecycle._remove_workspace_files_v3``.
        Opera sui file dichiarati in ``pkg_manifest["workspace_files"]`` e
        ``pkg_manifest["plugin_files"]`` (deduplicati).  Preserva i file
        modificati dall'utente o owned da altri pacchetti.

        Il manifest del pacchetto deve essere letto dallo store PRIMA che la
        directory del pacchetto venga rimossa (invariante del flusso v3 remove).

        Args:
            package_id: ID del pacchetto da rimuovere.
            pkg_manifest: package-manifest.json letto dallo store prima della rmtree.

        Returns:
            ``{"removed": [...], "preserved": [...], "errors": []}``.
        """
        workspace_files: list[str] = []
        raw_wf = pkg_manifest.get("workspace_files")
        if isinstance(raw_wf, list):
            workspace_files = list(raw_wf)

        plugin_files: list[str] = []
        raw_pf = pkg_manifest.get("plugin_files")
        if isinstance(raw_pf, list):
            plugin_files = list(raw_pf)

        all_files = _dedupe_preserving_order(workspace_files + plugin_files)

        if not all_files:
            return {"removed": [], "preserved": [], "errors": []}

        removed: list[str] = []
        preserved: list[str] = []
        errors: list[str] = []

        for entry in all_files:
            if not isinstance(entry, str):
                continue

            github_rel = entry.removeprefix(".github/")
            target = self._github_root / github_rel

            if not target.is_file():
                continue

            owners = self._manifest.get_file_owners(github_rel)

            # File non tracciato: preserva per sicurezza.
            if not owners:
                print(
                    f"[SPARK-PLUGINS][WARNING] File {entry!r} non tracciato nel manifest, "
                    "preservato per sicurezza",
                    file=sys.stderr,
                )
                preserved.append(entry)
                continue

            # File owned da altri pacchetti: non toccare.
            if package_id not in owners:
                preserved.append(entry)
                continue

            # Preservation gate: utente ha modificato il file.
            if self._manifest.is_user_modified(github_rel) is True:
                preserved.append(entry)
                continue

            try:
                self._gateway.delete(github_rel, package_id)
                removed.append(entry)
            except OSError as exc:
                errors.append(f"{entry}: delete failed ({exc})")

        return {"removed": removed, "preserved": preserved, "errors": errors}

    def _remove_instruction_reference(self, pkg_id: str) -> None:
        """Rimuove la referenza ``#file:`` del plugin da ``copilot-instructions.md``.

        Elimina la riga ``#file:.github/instructions/{pkg_id}.md`` dal file
        ``.github/copilot-instructions.md``. No-op se la riga non è presente
        o se il file non esiste nel workspace.

        Args:
            pkg_id: ID del plugin la cui referenza deve essere rimossa.
        """
        copilot_instructions = self._github_root / "copilot-instructions.md"

        if not copilot_instructions.is_file():
            return

        file_ref_line = f"#file:.github/instructions/{pkg_id}.md"
        content = copilot_instructions.read_text(encoding="utf-8")

        # La riga non è presente: nessuna azione necessaria.
        if file_ref_line not in content:
            return

        # Rimuove la riga corrispondente mantenendo il resto invariato.
        new_lines = [
            line
            for line in content.splitlines(keepends=True)
            if line.strip() != file_ref_line
        ]

        # Rimuove la sezione header se rimane vuota (nessun altro #file:).
        cleaned_lines = self._cleanup_empty_section(new_lines)

        copilot_instructions.write_text("".join(cleaned_lines), encoding="utf-8")
        print(
            f"[SPARK-PLUGINS][INFO] Removed #file: reference for {pkg_id} "
            "from copilot-instructions.md",
            file=sys.stderr,
        )

    # ------------------------------------------------------------------
    # Helper privati
    # ------------------------------------------------------------------

    def _cleanup_empty_section(self, lines: list[str]) -> list[str]:
        """Rimuove la sezione plugin se non contiene più referenze #file:.

        Args:
            lines: Lista di righe del file con keepends=True.

        Returns:
            Lista di righe ripulita dalla sezione vuota, se necessario.
        """
        # Trova la sezione header.
        section_idx: int | None = None
        for i, line in enumerate(lines):
            if line.strip() == _PLUGIN_SECTION_HEADER:
                section_idx = i
                break

        if section_idx is None:
            return lines

        # Verifica se ci sono ancora referenze #file: dopo l'header.
        has_file_refs = any(
            line.strip().startswith("#file:")
            for line in lines[section_idx + 1:]
            if line.strip()
        )

        if has_file_refs:
            # La sezione contiene ancora referenze: lasciala invariata.
            return lines

        # La sezione è vuota: rimuovi l'header e le righe vuote adiacenti.
        result = lines[:section_idx]
        # Rimuove le righe vuote finali duplicate.
        while result and result[-1].strip() == "":
            result.pop()
        result.append("\n")
        return result
