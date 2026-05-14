"""spark.cli.registry_manager — Sfoglia e installa plugin dal registro remoto.

Accede a ``Nemex81/scf-registry`` via urllib.request (nessuna dipendenza esterna).
Graceful degradation se il registro non è raggiungibile.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_log: logging.Logger = logging.getLogger("spark-framework-engine")

# URL del registro remoto dei plugin SCF.
_REGISTRY_URL = (
    "https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json"
)

# Timeout HTTP in secondi.
_HTTP_TIMEOUT = 10


def _sha256_file(path: Path) -> str:
    """Calcola il digest SHA-256 esadecimale del file indicato.

    Args:
        path: Path assoluto al file da leggere.

    Returns:
        Stringa esadecimale minuscola del digest SHA-256.
    """
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65_536), b""):
            h.update(chunk)
    return h.hexdigest()


_MENU_TEXT = """\
Registro plugin remoti
1. Sfoglia plugin disponibili
2. Installa plugin dal registro
3. Verifica aggiornamenti
4. Applica aggiornamenti disponibili
0. Torna al menu principale"""


class RegistryManager:
    """Menu CLI per la gestione dei plugin remoti SPARK.

    Legge il registro remoto da ``scf-registry`` e permette di installare,
    verificare e aggiornare plugin nella directory ``.github/`` del workspace.

    Se il registro non è raggiungibile, mostra un messaggio testuale senza crash.

    Args:
        github_root: Root ``.github/`` del workspace utente.
        engine_root: Root del motore SPARK.
    """

    def __init__(self, github_root: Path, engine_root: Path) -> None:
        self._github_root = github_root
        self._engine_root = engine_root
        self._registry_cache: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Interfaccia pubblica
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Avvia il sotto-menu di gestione plugin remoti."""
        while True:
            os.system("cls" if os.name == "nt" else "clear")
            print(f"\n{_MENU_TEXT}")
            choice = input("Scegli [0-4]: ").strip()
            if choice == "0":
                break
            elif choice == "1":
                self._browse_plugins()
                input("\nPremi Invio per continuare...")
            elif choice == "2":
                self._install_plugin()
                input("\nPremi Invio per continuare...")
            elif choice == "3":
                self._check_updates()
                input("\nPremi Invio per continuare...")
            elif choice == "4":
                self._apply_updates()
                input("\nPremi Invio per continuare...")
            else:
                print("Scelta non valida. Inserisci un numero tra 0 e 4.")

    # ------------------------------------------------------------------
    # Operazioni di menu
    # ------------------------------------------------------------------

    def _browse_plugins(self) -> None:
        """Mostra la lista dei plugin disponibili nel registro remoto."""
        registry = self._load_registry()
        if registry is None:
            return

        packages = self._user_installable_packages(registry)
        if not packages:
            print("\nNessun plugin disponibile nel registro.")
            return

        print(f"\nPlugin disponibili ({len(packages)}):")
        for package in packages:
            pid = package.get("id", "?")
            version = package.get("latest_version", "?")
            desc = package.get("description", "")
            print(f"  - {pid} v{version}: {desc}")

    def _install_plugin(self) -> None:
        """Chiede un plugin_id e lo installa nel workspace."""
        registry = self._load_registry()
        if registry is None:
            return

        plugin_id = input("ID plugin da installare (0=annulla): ").strip()
        if not plugin_id or plugin_id == "0":
            return

        packages = self._user_installable_packages(registry)
        package = next((p for p in packages if p.get("id") == plugin_id), None)
        if package is None:
            print(f"Plugin '{plugin_id}' non trovato nel registro.")
            return

        print(f"Installazione plugin {plugin_id} v{package.get('latest_version', '?')} ...")
        result = self._download_and_install_plugin(package)
        if result["success"]:
            print(
                f"File installati: {result['files_copied']}, "
                f"già aggiornati: {result['preserved']}"
            )
            if result["errors"]:
                print(f"Avvisi: {'; '.join(result['errors'])}")
        else:
            errors = result.get("errors", [])
            print(
                f"Installazione fallita: "
                f"{'; '.join(errors) if errors else 'errore sconosciuto'}"
            )

    def _check_updates(self) -> None:
        """Verifica aggiornamenti per i plugin installati localmente."""
        registry = self._load_registry()
        if registry is None:
            return

        local_versions = self._read_local_plugin_versions()
        if not local_versions:
            print("\nNessun plugin installato localmente.")
            return

        packages = self._user_installable_packages(registry)
        remote_by_id = {p.get("id"): p for p in packages if p.get("id")}

        updates_available: list[tuple[str, str, str]] = []
        for plugin_id, local_version in local_versions.items():
            remote = remote_by_id.get(plugin_id)
            if remote is None:
                continue
            remote_version = remote.get("latest_version", "")
            if remote_version and remote_version != local_version:
                updates_available.append((plugin_id, local_version, remote_version))

        if not updates_available:
            print("\nTutti i plugin sono aggiornati.")
            return

        print(f"\nAggiornamenti disponibili ({len(updates_available)}):")
        for pid, local_v, remote_v in updates_available:
            print(f"  - {pid}: {local_v} → {remote_v}")

    def _apply_updates(self) -> None:
        """Scarica e applica tutti gli aggiornamenti disponibili."""
        registry = self._load_registry()
        if registry is None:
            return

        local_versions = self._read_local_plugin_versions()
        if not local_versions:
            print("\nNessun plugin installato localmente.")
            return

        packages = self._user_installable_packages(registry)
        remote_by_id = {p.get("id"): p for p in packages if p.get("id")}

        updated = 0
        failed = 0
        for plugin_id, local_version in local_versions.items():
            remote = remote_by_id.get(plugin_id)
            if remote is None:
                continue
            remote_version = remote.get("latest_version", "")
            if not remote_version or remote_version == local_version:
                continue

            print(f"Aggiornamento {plugin_id} {local_version} → {remote_version} ...")
            result = self._download_and_install_plugin(remote, force=True)
            if result["success"]:
                updated += 1
                print(f"  {plugin_id} aggiornato.")
            else:
                failed += 1
                errors = result.get("errors", [])
                print(
                    f"  {plugin_id} FALLITO: "
                    f"{'; '.join(errors) if errors else 'errore sconosciuto'}"
                )

        if updated == 0 and failed == 0:
            print("\nNessun aggiornamento applicato.")
        else:
            print(f"\nRiepilogo: {updated} aggiornati, {failed} falliti.")

    # ------------------------------------------------------------------
    # Helpers registro remoto
    # ------------------------------------------------------------------

    def _user_installable_packages(
        self, registry: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Ritorna solo i pacchetti del registro non gestiti dall'engine.

        I pacchetti con ``engine_managed_resources=True`` sono gestiti
        automaticamente durante il bootstrap e non devono essere visibili
        né installabili dall'utente tramite il CLI.

        Args:
            registry: Dizionario del registro remoto.

        Returns:
            Lista di entry pacchetto con ``engine_managed_resources != True``.
        """
        all_packages: list[dict[str, Any]] = registry.get("packages", [])
        return [
            p for p in all_packages
            if not p.get("engine_managed_resources", False)
        ]

    def _load_registry(self) -> dict[str, Any] | None:
        """Scarica e ritorna il registro remoto (con cache in sessione).

        Se il registro non è raggiungibile o il JSON non è valido, logga
        un warning e mostra un messaggio testuale senza crash.

        Returns:
            Dict del registro remoto, oppure None se non raggiungibile.
        """
        if self._registry_cache is not None:
            return self._registry_cache

        try:
            with urllib.request.urlopen(_REGISTRY_URL, timeout=_HTTP_TIMEOUT) as resp:
                raw_bytes = resp.read()
        except urllib.error.URLError as exc:
            _log.warning(
                "[SPARK-ENGINE][CLI] Registro remoto non raggiungibile: %s",
                exc,
            )
            print(
                "\nRegistro remoto non raggiungibile. "
                "Controlla la connessione di rete e riprova."
            )
            return None
        except OSError as exc:
            _log.warning("[SPARK-ENGINE][CLI] Errore HTTP registro: %s", exc)
            print(f"\nErrore accesso registro: {exc}")
            return None

        try:
            registry = json.loads(raw_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            _log.warning(
                "[SPARK-ENGINE][CLI] Errore parsing registro JSON: %s",
                exc,
            )
            print(f"\nFormato registro non valido: {exc}")
            return None

        self._registry_cache = registry
        return registry

    def _fetch_remote_manifest(self, repo: str, manifest_path: str) -> dict[str, Any] | None:
        """Scarica il manifest di un plugin dal repository remoto.

        Args:
            repo: Percorso owner/repo su GitHub (es. ``"Nemex81/my-plugin"``).
            manifest_path: Percorso del manifest nel repo (es. ``"package-manifest.json"``).

        Returns:
            Dict del manifest, oppure None se non raggiungibile o non valido.
        """
        url = (
            f"https://raw.githubusercontent.com/{repo}/main/{manifest_path}"
        )
        try:
            with urllib.request.urlopen(url, timeout=_HTTP_TIMEOUT) as resp:
                raw = resp.read()
            return json.loads(raw.decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            _log.warning(
                "[SPARK-ENGINE][CLI] Impossibile scaricare manifest %s: %s",
                url,
                exc,
            )
            return None

    def _download_and_install_plugin(
        self,
        package: dict[str, Any],
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        """Scarica e installa un pacchetto dal registro nel workspace.

        Gestisce ``workspace_files`` e ``plugin_files`` dal manifest remoto.
        Applica idempotenza SHA-based: i file con SHA invariato rispetto al
        contenuto remoto vengono preservati senza sovrascrittura.
        Aggiorna il manifest ``.scf-manifest.json`` per i file effettivamente
        scritti. Se ``delivery_mode`` è ``"mcp_only"``, il pacchetto non viene
        installato via RegistryManager; usare il menu Gestisci Pacchetti.
        Se ``force=True`` sovrascrive i file esistenti ignorando il check SHA.

        Args:
            package: Entry del pacchetto nel registro remoto (id,
                latest_version, repo_url, manifest_path).
            force: Se True, sovrascrive i file già presenti (usato per update).

        Returns:
            Dict con:
            - ``success`` (bool): True se l'operazione è completata senza
              errori fatali.
            - ``files_copied`` (int): File nuovi o aggiornati scritti su disco.
            - ``preserved`` (int): File già aggiornati (SHA invariato, skip).
            - ``errors`` (list[str]): Messaggi di errore/avviso non fatali.
        """
        result: dict[str, Any] = {
            "success": False,
            "files_copied": 0,
            "preserved": 0,
            "errors": [],
        }

        # Estrai owner/repo slug dall'URL completo per costruire URL raw GitHub.
        repo_url = package.get("repo_url", "")
        repo = repo_url.removeprefix("https://github.com/").strip("/") if repo_url else ""
        manifest_path = package.get("manifest_path", "package-manifest.json")
        plugin_id = package.get("id", "")
        version = package.get("latest_version", "")

        if not repo or not plugin_id:
            result["errors"].append("Entry registro incompleta (mancano 'repo_url' o 'id').")
            return result

        manifest = self._fetch_remote_manifest(repo, manifest_path)
        if manifest is None:
            result["errors"].append(f"Impossibile scaricare manifest per '{plugin_id}'.")
            return result

        # Fix A — Guard delivery_mode: "mcp_only".
        delivery_mode = manifest.get("delivery_mode", "managed")
        if delivery_mode == "mcp_only":
            _log.info(
                "[SPARK-ENGINE][INFO] Pacchetto '%s' è mcp_only — "
                "installazione via RegistryManager non supportata.",
                plugin_id,
            )
            print(
                "Pacchetto gestito dall'engine MCP. Usare opzione 2 — Gestisci "
                "Pacchetti per installarlo correttamente."
            )
            result["errors"].append("mcp_only: usare PackageManager")
            return result

        # Fix B — Costruisce sha_map da files_metadata del manifest remoto.
        raw_metadata = manifest.get("files_metadata", [])
        sha_map: dict[str, str] = {}
        if isinstance(raw_metadata, list):
            for meta_entry in raw_metadata:
                if isinstance(meta_entry, dict):
                    meta_path = meta_entry.get("path", "")
                    meta_sha = meta_entry.get("sha256", "")
                    if meta_path and meta_sha:
                        sha_map[meta_path] = meta_sha

        workspace_files: list[str] = manifest.get("workspace_files", [])
        plugin_files: list[str] = manifest.get("plugin_files", [])

        if not workspace_files and not plugin_files:
            result["success"] = True
            return result

        copied_in_session: list[Path] = []
        files_written: list[tuple[str, Path]] = []

        try:
            for file_group in (workspace_files, plugin_files):  # Fix C — include plugin_files.
                for rel_path in file_group:
                    if rel_path.startswith(".github/"):
                        within_github = rel_path[len(".github/"):]
                    else:
                        within_github = rel_path

                    dest = self._github_root / within_github

                    if dest.is_file():
                        if rel_path in sha_map:
                            if _sha256_file(dest) == sha_map[rel_path] and not force:
                                result["preserved"] += 1
                                continue
                            # SHA differisce oppure force=True: sovrascrive.
                        else:
                            if not force:
                                _log.warning(
                                    "[SPARK-ENGINE][WARNING] sha256 non disponibile "
                                    "per %s — skip conservativo",
                                    rel_path,
                                )
                                result["preserved"] += 1
                                continue

                    file_url = (
                        f"https://raw.githubusercontent.com/{repo}/main/{rel_path}"
                    )
                    try:
                        with urllib.request.urlopen(file_url, timeout=_HTTP_TIMEOUT) as resp:
                            file_bytes = resp.read()
                    except urllib.error.URLError as exc:
                        _log.warning(
                            "[SPARK-ENGINE][CLI] Impossibile scaricare file plugin %s: %s",
                            file_url,
                            exc,
                        )
                        result["errors"].append(f"Download fallito: {rel_path}")
                        continue

                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(file_bytes)
                    copied_in_session.append(dest)
                    result["files_copied"] += 1
                    files_written.append((within_github, dest))
                    _log.info(
                        "[SPARK-ENGINE][CLI] plugin file installato: %s",
                        dest,
                    )

            # Fix D — Aggiorna il manifest per i file effettivamente scritti.
            if result["files_copied"] > 0:
                try:
                    from spark.manifest.manifest import ManifestManager  # noqa: PLC0415

                    manifest_mgr = ManifestManager(self._github_root)
                    manifest_mgr.upsert_many(plugin_id, version, files_written)
                    _log.info(
                        "[SPARK-ENGINE][INFO] Manifest aggiornato per '%s' (%d file).",
                        plugin_id,
                        len(files_written),
                    )
                # I file sono già scritti su disco: il manifest è recuperabile
                # rieseguendo l'installazione. Non si esegue rollback dei file.
                except Exception as exc:  # noqa: BLE001
                    _log.error(
                        "[SPARK-ENGINE][ERROR] Aggiornamento manifest fallito per '%s': %s",
                        plugin_id,
                        str(exc),
                    )
                    result["errors"].append(f"Manifest non aggiornato: {exc}")

            result["success"] = True

        except (OSError, shutil.Error) as exc:
            _log.warning(
                "[SPARK-ENGINE][CLI] Errore installazione plugin %s, rollback: %s",
                plugin_id,
                exc,
            )
            for f in copied_in_session:
                try:
                    f.unlink()
                except OSError:
                    pass
            result["errors"].append(f"Errore installazione (rollback eseguito): {exc}")
            result["success"] = False
            result["files_copied"] = 0

        return result

    def _read_local_plugin_versions(self) -> dict[str, str]:
        """Legge le versioni dei plugin installati dal manifest locale.

        Returns:
            Dict ``{plugin_id: version}`` per i plugin installati.
        """
        try:
            from spark.manifest.manifest import ManifestManager  # noqa: PLC0415

            manifest = ManifestManager(self._github_root)
            return manifest.get_installed_versions()
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "[SPARK-ENGINE][CLI] Errore lettura versioni locali: %s",
                exc,
            )
            return {}
