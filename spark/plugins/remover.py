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
from pathlib import Path
from typing import TYPE_CHECKING

from spark.plugins.schema import PluginRecord

if TYPE_CHECKING:
    from spark.manifest.gateway import WorkspaceWriteGateway
    from spark.manifest.manifest import ManifestManager

# Sezione plugin in copilot-instructions.md (deve coincidere con installer.py).
_PLUGIN_SECTION_HEADER: str = (
    "# Plugin instructions (managed by SPARK Plugin Manager \u2014 do not edit manually)"
)


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
