"""spark.cli.init_manager — Inizializzazione guidata workspace SPARK.

Sequenza testuale numerata, accessibile da tastiera (no curses, no ASCII art).
Nessuna dipendenza esterna: solo stdlib Python.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_log: logging.Logger = logging.getLogger("spark-framework-engine")

# Nome file di pacchetti dichiarati nel workspace utente.
_SPARK_PACKAGES_FILE = "spark-packages.json"

# Contenuto minimale di spark-packages.json per un nuovo workspace.
_DEFAULT_SPARK_PACKAGES: dict[str, Any] = {
    "packages": ["spark-base", "spark-ops"],
    "auto_install": True,
}

# Configurazione MCP minimale per il server SPARK.
_MCP_SERVER_KEY = "spark-framework-engine"


class InitManager:
    """Gestisce l'inizializzazione guidata di un nuovo workspace SPARK.

    Sequenza:
    1. Chiede il percorso del workspace target (default: cwd).
    2. Crea la struttura ``.github/`` nel workspace.
    3. Trasferisce i workspace_files di spark-ops.
    4. Scrive o aggiorna ``.vscode/mcp.json``.
    5. Emette il segnale di reload.

    Ogni operazione è idempotente e logga le azioni.

    Args:
        engine_root: Root del motore SPARK (calcolata da ``main.py``).
    """

    def __init__(self, engine_root: Path) -> None:
        self._engine_root = engine_root

    # ------------------------------------------------------------------
    # Interfaccia pubblica
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Esegue la sequenza di inizializzazione workspace interattiva.

        Guida l'utente passo per passo: richiede il percorso, crea la struttura,
        trasferisce i file spark-ops, scrive la configurazione MCP.
        """
        print("\n=== SPARK Init — Inizializzazione Workspace ===\n")

        target = self._ask_workspace_path()
        if target is None:
            print("[SPARK] Inizializzazione annullata.")
            return

        print(f"\nWorkspace selezionato: {target}\n")

        # Step 1 — Struttura .github/
        print("[1/4] Creazione struttura .github/ ...")
        created = self._create_workspace_structure(target)
        if created:
            print(f"      Struttura creata in: {target / '.github'}")
        else:
            print("      Struttura gia presente, nessuna modifica.")

        # Step 2 — Trasferimento spark-ops
        print("[2/4] Trasferimento file spark-ops ...")
        transfer_result = self._transfer_spark_ops(target)
        if transfer_result["success"]:
            print(f"      File copiati: {transfer_result['files_copied']}")
            if transfer_result["files_skipped"]:
                print(f"      File saltati (gia presenti): {transfer_result['files_skipped']}")
        else:
            print(f"      ATTENZIONE: trasferimento parziale. Errori: {transfer_result['errors']}")

        # Step 3 — Configurazione MCP
        print("[3/4] Scrittura configurazione MCP ...")
        mcp_written = self._write_mcp_config(target)
        if mcp_written:
            print(f"      Configurazione MCP scritta: {target / '.vscode' / 'mcp.json'}")
        else:
            print("      Configurazione MCP gia presente, nessuna modifica.")

        # Step 4 — Segnale di reload
        print("[4/4] Emissione segnale reload ...")
        self._signal_reload(target)

        # Step 5 (opzionale) — Apertura VS Code
        print("[5/5] Apertura VS Code (opzionale) ...")
        self._offer_vscode_open(target)

    # ------------------------------------------------------------------
    # Step interni
    # ------------------------------------------------------------------

    def _ask_workspace_path(self) -> Path | None:
        """Chiede all'utente il percorso del workspace target.

        Default: directory corrente. Valida che il percorso sia assoluto
        e accessibile in scrittura. Ritenta su input non valido (max 3 volte).

        Returns:
            Path assoluto del workspace scelto, oppure None se l'utente annulla
            o supera il massimo di tentativi.
        """
        default_path = Path.cwd()
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            raw = input(
                f"Percorso workspace [{default_path}] (invio per default, 0=annulla): "
            ).strip()

            if raw == "0":
                return None

            if not raw:
                return default_path

            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = candidate.resolve()

            # Verifica accessibilità in scrittura: prova a creare la dir se non esiste
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                # Test accesso in scrittura
                test_file = candidate / ".spark-write-test"
                test_file.touch()
                test_file.unlink()
                return candidate
            except (OSError, PermissionError) as exc:
                print(f"Percorso non accessibile in scrittura ({exc}). Tentativo {attempt}/{max_attempts}.")
                if attempt == max_attempts:
                    print("Numero massimo di tentativi raggiunto.")
                    return None

        return None  # mai raggiunto, ma necessario per type checker

    def _create_workspace_structure(self, target: Path) -> bool:
        """Crea la struttura base del workspace SPARK.

        Crea ``target/.github/`` e scrive ``spark-packages.json`` minimale
        se non già presente. Idempotente.

        Args:
            target: Root del workspace target.

        Returns:
            True se almeno una directory o file è stato creato; False se
            tutto era già presente.
        """
        created_something = False

        github_dir = target / ".github"
        if not github_dir.is_dir():
            github_dir.mkdir(parents=True, exist_ok=True)
            _log.info("[SPARK-ENGINE][CLI] github_dir creato: %s", github_dir)
            created_something = True

        spark_packages_file = github_dir / _SPARK_PACKAGES_FILE
        if not spark_packages_file.is_file():
            spark_packages_file.write_text(
                json.dumps(_DEFAULT_SPARK_PACKAGES, indent=2), encoding="utf-8"
            )
            _log.info(
                "[SPARK-ENGINE][CLI] spark-packages.json scritto: %s",
                spark_packages_file,
            )
            created_something = True

        return created_something

    def _transfer_spark_ops(self, target: Path) -> dict[str, Any]:
        """Trasferisce i workspace_files di spark-ops nel workspace target.

        Legge ``packages/spark-ops/package-manifest.json`` dall'engine root.
        Per ogni file in ``workspace_files``, copia la sorgente nella destinazione
        rispettando il percorso relativo (striscia il prefisso ``.github/`` se
        il dest è dentro github_root).

        In caso di errore parziale esegue rollback atomico: i file già copiati
        nella sessione vengono eliminati e l'errore viene loggato.

        Args:
            target: Root del workspace target.

        Returns:
            Dict con chiavi:
            - ``success``: True se tutti i file sono stati copiati senza errori.
            - ``files_copied``: numero di file copiati in questa sessione.
            - ``files_skipped``: numero di file già presenti (saltati).
            - ``errors``: lista stringhe di errore.
        """
        result: dict[str, Any] = {
            "success": True,
            "files_copied": 0,
            "files_skipped": 0,
            "errors": [],
        }

        ops_manifest_path = self._engine_root / "packages" / "spark-ops" / "package-manifest.json"
        if not ops_manifest_path.is_file():
            _log.warning(
                "[SPARK-ENGINE][CLI] spark-ops manifest non trovato: %s",
                ops_manifest_path,
            )
            result["errors"].append(f"spark-ops manifest non trovato: {ops_manifest_path}")
            result["success"] = False
            return result

        try:
            ops_manifest = json.loads(ops_manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            result["errors"].append(f"Errore lettura spark-ops manifest: {exc}")
            result["success"] = False
            return result

        workspace_files: list[str] = ops_manifest.get("workspace_files", [])
        if not workspace_files:
            _log.info("[SPARK-ENGINE][CLI] spark-ops non ha workspace_files, skip transfer.")
            return result

        ops_source_root = self._engine_root / "packages" / "spark-ops"
        github_root = target / ".github"
        github_root.mkdir(parents=True, exist_ok=True)

        # Tiene traccia dei file copiati per rollback atomico in caso di errore.
        copied_in_session: list[Path] = []

        try:
            for rel_path in workspace_files:
                # Il dest è dentro github_root: striscia il prefisso ".github/"
                if rel_path.startswith(".github/"):
                    within_github = rel_path[len(".github/"):]
                else:
                    within_github = rel_path

                dest = github_root / within_github
                source = ops_source_root / rel_path

                if dest.is_file():
                    _log.debug(
                        "[SPARK-ENGINE][CLI] spark-ops file già presente, skip: %s",
                        dest,
                    )
                    result["files_skipped"] += 1
                    continue

                if not source.is_file():
                    _log.warning(
                        "[SPARK-ENGINE][CLI] spark-ops source non trovato, skip: %s",
                        source,
                    )
                    result["errors"].append(f"Source non trovato: {source}")
                    continue

                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(source), str(dest))
                copied_in_session.append(dest)
                result["files_copied"] += 1
                _log.info(
                    "[SPARK-ENGINE][CLI] spark-ops file copiato: %s → %s",
                    source,
                    dest,
                )

        except (OSError, shutil.Error) as exc:
            # Rollback atomico: elimina i file copiati in questa sessione.
            _log.warning(
                "[SPARK-ENGINE][CLI] Errore durante copia spark-ops, avvio rollback: %s",
                exc,
            )
            for copied_file in copied_in_session:
                try:
                    copied_file.unlink()
                    _log.info(
                        "[SPARK-ENGINE][CLI] Rollback: file eliminato: %s",
                        copied_file,
                    )
                except OSError as rollback_exc:
                    _log.warning(
                        "[SPARK-ENGINE][CLI] Rollback: impossibile eliminare %s: %s",
                        copied_file,
                        rollback_exc,
                    )
            result["errors"].append(f"Errore copia (rollback eseguito): {exc}")
            result["success"] = False
            result["files_copied"] = 0

        if result["errors"]:
            result["success"] = False

        return result

    def _write_mcp_config(self, target: Path) -> bool:
        """Scrive o aggiorna ``.vscode/mcp.json`` con la configurazione SPARK MCP.

        Se il file esiste già, esegue un merge conservativo: preserva le
        configurazioni esistenti e aggiunge il server SPARK solo se assente.
        Il percorso di ``spark-framework-engine.py`` viene calcolato in modo
        assoluto dall'engine root.

        Args:
            target: Root del workspace target.

        Returns:
            True se il file è stato creato o modificato; False se era già
            presente e non ha richiesto modifiche.
        """
        engine_py = self._engine_root / "spark-framework-engine.py"
        vscode_dir = target / ".vscode"
        mcp_json_path = vscode_dir / "mcp.json"

        server_entry: dict[str, Any] = {
            "type": "stdio",
            "command": "python",
            "args": [str(engine_py)],
            "env": {},
        }

        if mcp_json_path.is_file():
            try:
                existing = json.loads(mcp_json_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                _log.warning(
                    "[SPARK-ENGINE][CLI] Impossibile leggere mcp.json esistente: %s",
                    exc,
                )
                existing = {}

            servers = existing.setdefault("servers", {})
            if _MCP_SERVER_KEY in servers:
                _log.info(
                    "[SPARK-ENGINE][CLI] Server SPARK già presente in mcp.json, nessuna modifica."
                )
                return False

            servers[_MCP_SERVER_KEY] = server_entry
            vscode_dir.mkdir(parents=True, exist_ok=True)
            mcp_json_path.write_text(
                json.dumps(existing, indent=2), encoding="utf-8"
            )
            _log.info(
                "[SPARK-ENGINE][CLI] Server SPARK aggiunto a mcp.json esistente: %s",
                mcp_json_path,
            )
            return True

        # File non esiste: crea struttura minimale.
        vscode_dir.mkdir(parents=True, exist_ok=True)
        mcp_config: dict[str, Any] = {
            "servers": {
                _MCP_SERVER_KEY: server_entry,
            }
        }
        mcp_json_path.write_text(
            json.dumps(mcp_config, indent=2), encoding="utf-8"
        )
        _log.info("[SPARK-ENGINE][CLI] mcp.json creato: %s", mcp_json_path)
        return True

    def _signal_reload(self, target: Path) -> None:
        """Scrive il segnale di reload e stampa il messaggio finale all'utente.

        Scrive ``target/.github/.spark-reload-requested`` con il timestamp ISO.
        Stampa su stdout (non stderr) il messaggio di completamento.

        Args:
            target: Root del workspace target.
        """
        github_root = target / ".github"
        github_root.mkdir(parents=True, exist_ok=True)

        reload_marker = github_root / ".spark-reload-requested"
        timestamp = datetime.now(timezone.utc).isoformat()
        reload_marker.write_text(timestamp, encoding="utf-8")
        _log.info(
            "[SPARK-ENGINE][CLI] Segnale reload scritto: %s",
            reload_marker,
        )
        print(
            "\nWorkspace inizializzato. Ricarica VS Code per attivare il server SPARK MCP."
        )
        print(f"Workspace: {target}\n")

    def _offer_vscode_open(self, target: Path) -> None:
        """Propone l'apertura di VS Code sul workspace appena inizializzato.

        Cerca il file .code-workspace in target/. Se trovato, chiede conferma
        e lancia subprocess.run(["code", path]). Se non trovato, propone
        apertura della cartella con subprocess.run(["code", str(target)]).
        Se subprocess fallisce o code non è nel PATH, logga WARNING su stderr
        senza propagare.

        Args:
            target: Root del workspace target.
        """
        workspaces = list(target.glob("*.code-workspace"))
        vscode_path: str = str(workspaces[0]) if workspaces else str(target)

        confirm = input("Aprire VS Code ora? [s/N]: ").strip().lower()
        if confirm not in ("s", "si", "s\u00ec", "y", "yes"):
            print("Apertura rimandata.")
            return

        try:
            subprocess.run(["code", vscode_path], check=False)
        except FileNotFoundError:
            _log.warning("[SPARK-ENGINE][WARNING] code non trovato nel PATH")
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "[SPARK-ENGINE][WARNING] Apertura VS Code fallita: %s", exc
            )
