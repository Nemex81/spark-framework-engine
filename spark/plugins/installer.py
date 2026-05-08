"""Modulo spark.plugins.installer — download e installazione plugin nel workspace.

Scarica i file dichiarati in ``PluginManifest.plugin_files`` dai repository
GitHub dei plugin e li scrive nel workspace utente tramite ``WorkspaceWriteGateway``.
Gestisce anche le referenze ``#file:`` in ``copilot-instructions.md``.

Logica ereditata (riscritta nel nuovo contesto senza import circolari da):
- ``spark.boot.lifecycle._install_workspace_files_v3``
- ``spark.boot.lifecycle._install_standalone_files_v3``
"""
from __future__ import annotations

import sys
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from spark.core.utils import _sha256_text
from spark.plugins.schema import PluginInstallError, PluginManifest

if TYPE_CHECKING:
    from spark.manifest.gateway import WorkspaceWriteGateway
    from spark.manifest.manifest import ManifestManager

# Timeout in secondi per i download HTTP dei file plugin.
_DOWNLOAD_TIMEOUT_SECONDS: int = 10

# Sezione dedicata ai plugin in copilot-instructions.md.
_PLUGIN_SECTION_HEADER: str = (
    "# Plugin instructions (managed by SPARK Plugin Manager \u2014 do not edit manually)"
)


class PluginInstaller:
    """Scarica e installa i file di un plugin nel workspace utente.

    Utilizza ``WorkspaceWriteGateway`` per tutte le scritture su filesystem,
    garantendo che ogni file sia tracciato in ``.github/.scf-manifest.json``
    con il relativo SHA-256 per il preservation gate.

    Attributes:
        _workspace_root: Path assoluto alla root del workspace utente.
        _github_root: Path assoluto a ``<workspace>/.github/``.
        _manifest: Istanza di ManifestManager per il tracking dei file.
        _gateway: Istanza di WorkspaceWriteGateway per le scritture.
    """

    def __init__(
        self,
        workspace_root: Path,
        manifest_manager: ManifestManager,
        gateway: WorkspaceWriteGateway,
    ) -> None:
        """Inizializza l'installer con le dipendenze già istanziate.

        Args:
            workspace_root: Path assoluto alla root del workspace utente.
            manifest_manager: ManifestManager attivo per il workspace.
            gateway: WorkspaceWriteGateway per le scritture su ``.github/``.
        """
        self._workspace_root = workspace_root
        self._github_root = workspace_root / ".github"
        self._manifest = manifest_manager
        self._gateway = gateway

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def install_files(self, plugin_manifest: PluginManifest) -> list[str]:
        """Scarica e installa i file del plugin nel workspace.

        Per ogni file dichiarato in ``plugin_manifest.plugin_files``:
        1. Costruisce la URL raw GitHub via ``_build_raw_url``.
        2. Scarica il contenuto via ``urllib.request.urlopen``.
        3. Scrive nel workspace tramite ``WorkspaceWriteGateway``.

        Se un singolo file fallisce il download, logga l'errore su stderr
        e continua con gli altri. Al termine, se ci sono fallimenti,
        solleva ``PluginInstallError`` con la lista dei file falliti.

        Args:
            plugin_manifest: Manifest del plugin con la lista dei file
                da installare e il repo sorgente.

        Returns:
            Lista dei path relativi al workspace dei file scritti con successo.

        Raises:
            PluginInstallError: Se uno o più file non possono essere scaricati
                o scritti.
        """
        if not plugin_manifest.plugin_files:
            print(
                f"[SPARK-PLUGINS][INFO] No plugin_files declared for "
                f"{plugin_manifest.pkg_id} — nothing to install",
                file=sys.stderr,
            )
            return []

        written: list[str] = []
        failed: list[str] = []

        for file_path in plugin_manifest.plugin_files:
            if not isinstance(file_path, str) or not file_path:
                print(
                    f"[SPARK-PLUGINS][WARNING] Skipping invalid file entry: {file_path!r}",
                    file=sys.stderr,
                )
                continue

            raw_url = self._build_raw_url(plugin_manifest.source_repo, file_path)

            # Tentativo di download del file dal repo GitHub.
            try:
                content = self._download_file(raw_url)
            except (urllib.error.URLError, OSError, ValueError) as exc:
                print(
                    f"[SPARK-PLUGINS][ERROR] Download failed for {file_path!r} "
                    f"({raw_url}): {exc}",
                    file=sys.stderr,
                )
                failed.append(file_path)
                continue

            # I file plugin sono nella struttura .github/ del repo sorgente.
            # Ricaviamo il path relativo a .github/ per il gateway.
            github_rel = file_path.removeprefix(".github/")

            # Path traversal guard: rifiuta path con componenti "..".
            if ".." in Path(github_rel).parts:
                print(
                    f"[SPARK-PLUGINS][ERROR] Unsafe path rejected: {file_path!r}",
                    file=sys.stderr,
                )
                failed.append(file_path)
                continue

            # Scrittura nel workspace tramite il gateway centralizzato.
            try:
                self._gateway.write(
                    github_rel=github_rel,
                    content=content,
                    owner=plugin_manifest.pkg_id,
                    version=plugin_manifest.version,
                )
                written.append(file_path)
                print(
                    f"[SPARK-PLUGINS][INFO] Installed {file_path}",
                    file=sys.stderr,
                )
            except OSError as exc:
                print(
                    f"[SPARK-PLUGINS][ERROR] Write failed for {file_path!r}: {exc}",
                    file=sys.stderr,
                )
                failed.append(file_path)

        if failed:
            raise PluginInstallError(
                pkg_id=plugin_manifest.pkg_id,
                failed_files=failed,
            )

        return written

    def install_from_store(
        self,
        package_id: str,
        pkg_version: str,
        pkg_manifest: Mapping[str, Any],
        engine_root: Path,
    ) -> dict[str, Any]:
        """Copia nel workspace i file ``workspace_files`` dallo store engine locale.

        Equivalente migrato da ``spark.boot.lifecycle._install_workspace_files_v3``.
        Legge il contenuto dall'engine store locale (non da HTTP) e scrive nel
        workspace tramite ``WorkspaceWriteGateway`` con batch write (OPT-8).

        Applica il preservation gate: se il file è tracciato come modificato
        dall'utente (SHA mismatch), non sovrascrive.  Idempotente: se SHA
        sorgente == SHA tracciato e il file esiste su disco, salta la scrittura.

        Args:
            package_id: ID del pacchetto.
            pkg_version: Versione del pacchetto installata.
            pkg_manifest: package-manifest.json (deve contenere ``workspace_files``
                e opzionalmente ``file_policies``).
            engine_root: Path assoluto alla root del motore (contiene ``packages/``).

        Returns:
            ``{"success": bool, "files_written": [...], "preserved": [...], "errors": []}``.
        """
        from spark.registry.store import PackageResourceStore  # noqa: PLC0415

        workspace_files: list[str] = []
        raw = pkg_manifest.get("workspace_files")
        if isinstance(raw, list):
            workspace_files = raw

        if not workspace_files:
            return {"success": True, "files_written": [], "preserved": [], "errors": []}

        store = PackageResourceStore(engine_root)
        package_root = store.packages_root / package_id

        file_policies: dict[str, Any] = {}
        raw_policies = pkg_manifest.get("file_policies")
        if isinstance(raw_policies, dict):
            file_policies = raw_policies

        # Snapshot SHA per preservation gate / idempotenza (OPT-5).
        entries_snapshot = self._manifest.load()
        sha_map: dict[str, str] = {}
        for entry in entries_snapshot:
            fk = str(entry.get("file", "")).strip()
            sha = str(entry.get("sha256", "")).strip()
            if fk and sha and fk not in sha_map:
                sha_map[fk] = sha

        preserved: list[str] = []
        errors: list[str] = []
        pending_writes: list[tuple[str, str]] = []   # (github_rel, content)
        pending_entries: list[str] = []              # original entry strings
        pending_strategies: dict[str, str] = {}

        for entry in workspace_files:
            if not isinstance(entry, str):
                errors.append(f"invalid workspace_files entry: {entry!r}")
                continue

            github_rel = entry.removeprefix(".github/")

            # Path traversal guard.
            if ".." in Path(github_rel).parts:
                errors.append(f"unsafe workspace_files path: {entry}")
                continue

            source_path = package_root / entry
            if not source_path.is_file():
                errors.append(f"workspace_files source missing in store: {entry}")
                continue

            # Preservation gate: file owned e modificato da un altro pacchetto.
            existing_owners = self._manifest.get_file_owners(github_rel)
            other_owner_modified = any(
                owner != package_id
                and owner != "scf-engine-bootstrap"
                and self._manifest.is_user_modified(github_rel) is True
                for owner in existing_owners
            )
            if other_owner_modified:
                preserved.append(entry)
                continue

            try:
                content = source_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"{entry}: cannot read source ({exc})")
                continue

            # Idempotency: skip se SHA invariato e file presente su disco (OPT-5).
            if (
                _sha256_text(content) == sha_map.get(github_rel, "")
                and (self._github_root / github_rel).is_file()
            ):
                preserved.append(entry)
                continue

            policy_meta = file_policies.get(entry)
            merge_strategy: str | None = None
            if isinstance(policy_meta, dict):
                merge_strategy = policy_meta.get("merge_strategy")

            pending_writes.append((github_rel, content))
            pending_entries.append(entry)
            if merge_strategy is not None:
                pending_strategies[github_rel] = merge_strategy

        if errors:
            return {
                "success": False,
                "files_written": [],
                "preserved": preserved,
                "errors": errors,
            }

        if not pending_writes:
            return {
                "success": True,
                "files_written": [],
                "preserved": preserved,
                "errors": [],
            }

        # Batch write tramite gateway (OPT-8).
        try:
            self._gateway.write_many(
                writes=pending_writes,
                owner=package_id,
                version=pkg_version,
                merge_strategies=pending_strategies or None,
            )
        except OSError as exc:
            return {
                "success": False,
                "files_written": [],
                "preserved": preserved,
                "errors": [f"batch write failed: {exc}"],
            }

        return {
            "success": True,
            "files_written": pending_entries,
            "preserved": preserved,
            "errors": [],
        }

    def _add_instruction_reference(self, pkg_id: str) -> None:
        """Aggiunge la referenza ``#file:`` del plugin in ``copilot-instructions.md``.

        Aggiunge la riga ``#file:.github/instructions/{pkg_id}.md`` nella
        sezione plugin di ``.github/copilot-instructions.md``. Se la sezione
        non esiste ancora, la crea in fondo al file. No-op se il file di
        istruzioni del plugin non esiste nel workspace o la riga è già presente.

        Args:
            pkg_id: ID del plugin (corrisponde al nome del file istruzioni).
        """
        # Path del file istruzioni specifico del plugin.
        plugin_instruction_rel = f".github/instructions/{pkg_id}.md"
        plugin_instruction_abs = self._workspace_root / plugin_instruction_rel

        # Salta se il file di istruzioni non è stato installato.
        if not plugin_instruction_abs.is_file():
            print(
                f"[SPARK-PLUGINS][DEBUG] No instruction file found for {pkg_id!r}, "
                "skipping #file: reference",
                file=sys.stderr,
            )
            return

        copilot_instructions = self._github_root / "copilot-instructions.md"

        if not copilot_instructions.is_file():
            print(
                "[SPARK-PLUGINS][DEBUG] copilot-instructions.md not found, "
                "skipping #file: reference",
                file=sys.stderr,
            )
            return

        content = copilot_instructions.read_text(encoding="utf-8")
        file_ref_line = f"#file:{plugin_instruction_rel}"

        # La referenza è già presente: nessuna azione necessaria.
        if file_ref_line in content:
            return

        lines = content.splitlines(keepends=True)

        # Cerca la sezione plugin per inserire la nuova riga in modo ordinato.
        section_idx: int | None = None
        for i, line in enumerate(lines):
            if line.strip() == _PLUGIN_SECTION_HEADER:
                section_idx = i
                break

        if section_idx is not None:
            # Trova l'ultima riga #file: già presente nella sezione.
            insert_after = section_idx
            for i in range(section_idx + 1, len(lines)):
                stripped = lines[i].strip()
                if stripped.startswith("#file:"):
                    insert_after = i
                elif stripped and not stripped.startswith("#"):
                    # Fine della sezione plugin.
                    break
            # Inserisce la nuova referenza subito dopo l'ultima esistente.
            lines.insert(insert_after + 1, file_ref_line + "\n")
        else:
            # La sezione non esiste: la aggiunge in fondo al file.
            if lines and not lines[-1].endswith("\n"):
                lines.append("\n")
            lines.append("\n")
            lines.append(_PLUGIN_SECTION_HEADER + "\n")
            lines.append(file_ref_line + "\n")

        copilot_instructions.write_text("".join(lines), encoding="utf-8")
        print(
            f"[SPARK-PLUGINS][INFO] Added #file: reference for {pkg_id} "
            "in copilot-instructions.md",
            file=sys.stderr,
        )

    # ------------------------------------------------------------------
    # Helper privati
    # ------------------------------------------------------------------

    def _build_raw_url(self, source_repo: str, file_path: str) -> str:
        """Costruisce la URL raw GitHub per scaricare un file del plugin.

        Args:
            source_repo: Percorso GitHub nel formato "owner/repo"
                (es. "Nemex81/scf-master-codecrafter").
            file_path: Path relativo del file nel repository
                (es. ".github/instructions/scf-master-codecrafter.md").

        Returns:
            URL raw GitHub completa per il download diretto.
        """
        return f"https://raw.githubusercontent.com/{source_repo}/main/{file_path}"

    def _download_file(self, raw_url: str) -> str:
        """Scarica un file testuale dalla URL raw GitHub.

        Args:
            raw_url: URL raw GitHub del file da scaricare.

        Returns:
            Contenuto del file come stringa UTF-8.

        Raises:
            urllib.error.URLError: Se la richiesta HTTP fallisce.
            OSError: Se il download non può completarsi.
            ValueError: Se l'URL non è valida o il contenuto non è decodificabile.
        """
        # Validazione minima: solo URL pubbliche raw.githubusercontent.com.
        if not raw_url.startswith("https://raw.githubusercontent.com/"):
            raise ValueError(
                f"Unsupported URL scheme: {raw_url!r}. "
                "Only https://raw.githubusercontent.com/ URLs are accepted."
            )

        req = urllib.request.Request(
            raw_url,
            headers={"User-Agent": "spark-framework-engine/PluginInstaller"},
        )
        with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as resp:  # noqa: S310
            return resp.read().decode("utf-8")
