"""spark.cli.package_manager — Gestione pacchetti SPARK da CLI.

Menu testuale per listare, installare, rimuovere e aggiornare pacchetti.
Delega alle operazioni engine tramite asyncio.run() con gestione RuntimeError
(stesso pattern di OnboardingManager).
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

_log: logging.Logger = logging.getLogger("spark-framework-engine")

_MENU_TEXT = """\
Gestione pacchetti
1. Elenca pacchetti installati
2. Installa pacchetto da store locale
3. Rimuovi pacchetto
4. Reinstalla / forza aggiornamento
0. Torna al menu principale"""


class PackageManager:
    """Menu CLI per la gestione dei pacchetti SPARK installati nel workspace.

    Ogni operazione delega ai metodi dell'engine tramite un'istanza minimale
    di ``SparkFrameworkEngine`` costruita senza avviare il server MCP.
    Per le operazioni di sola lettura (list) usa direttamente ``ManifestManager``.

    Args:
        github_root: Root ``.github/`` del workspace utente.
        engine_root: Root del motore SPARK.
    """

    def __init__(self, github_root: Path, engine_root: Path) -> None:
        self._github_root = github_root
        self._engine_root = engine_root

    # ------------------------------------------------------------------
    # Interfaccia pubblica
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Avvia il sotto-menu di gestione pacchetti."""
        while True:
            print(f"\n{_MENU_TEXT}")
            choice = input("Scegli [0-4]: ").strip()
            if choice == "0":
                break
            elif choice == "1":
                self._list_installed()
            elif choice == "2":
                self._install_package()
            elif choice == "3":
                self._remove_package()
            elif choice == "4":
                self._reinstall_package()
            else:
                print("Scelta non valida. Inserisci un numero tra 0 e 4.")

    # ------------------------------------------------------------------
    # Operazioni di menu
    # ------------------------------------------------------------------

    def _list_installed(self) -> None:
        """Stampa la lista dei pacchetti installati nel workspace."""
        try:
            from spark.manifest.manifest import ManifestManager  # noqa: PLC0415

            manifest = ManifestManager(self._github_root)
            installed = manifest.get_installed_versions()
        except Exception as exc:  # noqa: BLE001
            _log.warning("[SPARK-ENGINE][CLI] Errore lettura manifest: %s", exc)
            print(f"Impossibile leggere i pacchetti installati: {exc}")
            return

        if not installed:
            print("\nNessun pacchetto installato.")
            return

        print(f"\nPacchetti installati ({len(installed)}):")
        for pkg_id, version in sorted(installed.items()):
            print(f"  - {pkg_id} ({version})")

    def _install_package(self) -> None:
        """Chiede un package_id e lo installa tramite engine."""
        pkg_id = input("ID pacchetto da installare (0=annulla): ").strip()
        if not pkg_id or pkg_id == "0":
            return

        print(f"Installazione {pkg_id} in corso ...")
        result = self._run_engine_install(pkg_id)
        if result.get("success"):
            print(f"Pacchetto {pkg_id} installato con successo.")
        else:
            print(f"Installazione fallita: {result.get('error', 'errore sconosciuto')}")

    def _remove_package(self) -> None:
        """Chiede un package_id e lo rimuove dal workspace."""
        pkg_id = input("ID pacchetto da rimuovere (0=annulla): ").strip()
        if not pkg_id or pkg_id == "0":
            return

        confirm = input(f"Confermi la rimozione di {pkg_id!r}? [s/N]: ").strip().lower()
        if confirm not in ("s", "si", "sì", "y", "yes"):
            print("Rimozione annullata.")
            return

        print(f"Rimozione {pkg_id} in corso ...")
        result = self._run_engine_remove(pkg_id)
        if result.get("success"):
            print(f"Pacchetto {pkg_id} rimosso.")
        else:
            print(f"Rimozione fallita: {result.get('error', 'errore sconosciuto')}")

    def _reinstall_package(self) -> None:
        """Rimuove e reinstalla un pacchetto (forza aggiornamento)."""
        pkg_id = input("ID pacchetto da reinstallare (0=annulla): ").strip()
        if not pkg_id or pkg_id == "0":
            return

        confirm = input(
            f"Reinstallare {pkg_id!r} (rimuovi + installa)? [s/N]: "
        ).strip().lower()
        if confirm not in ("s", "si", "sì", "y", "yes"):
            print("Reinstallazione annullata.")
            return

        print(f"Rimozione {pkg_id} ...")
        remove_result = self._run_engine_remove(pkg_id)
        if not remove_result.get("success"):
            print(
                f"Rimozione fallita: {remove_result.get('error', 'errore sconosciuto')}. "
                "Continuo con l'installazione."
            )

        print(f"Installazione {pkg_id} ...")
        install_result = self._run_engine_install(pkg_id)
        if install_result.get("success"):
            print(f"Pacchetto {pkg_id} reinstallato.")
        else:
            print(f"Installazione fallita: {install_result.get('error', 'errore sconosciuto')}")

    # ------------------------------------------------------------------
    # Helpers engine
    # ------------------------------------------------------------------

    def _build_minimal_engine(self) -> Any:
        """Costruisce un'istanza minimale di SparkFrameworkEngine senza avviare MCP.

        Returns:
            Istanza ``SparkFrameworkEngine`` pronta per le chiamate ai metodi
            di lifecycle (install, remove), senza server MCP attivo.

        Raises:
            ImportError: Se mcp o i moduli engine non sono disponibili.
            Exception: Se la costruzione del contesto workspace fallisce.
        """
        from mcp.server.fastmcp import FastMCP  # noqa: PLC0415
        from spark.boot.engine import SparkFrameworkEngine  # noqa: PLC0415
        from spark.boot.validation import (  # noqa: PLC0415
            resolve_runtime_dir,
            validate_engine_manifest,
        )
        from spark.inventory import FrameworkInventory  # noqa: PLC0415
        from spark.workspace import WorkspaceLocator  # noqa: PLC0415

        mcp = FastMCP("spark-cli-minimal")
        locator = WorkspaceLocator(engine_root=self._engine_root)
        context = locator.resolve()
        runtime_dir = resolve_runtime_dir(self._engine_root, context.workspace_root)
        engine_manifest, _, _ = validate_engine_manifest(self._engine_root)
        inventory = FrameworkInventory(context)
        inventory.populate_mcp_registry(engine_manifest=engine_manifest)
        app = SparkFrameworkEngine(mcp, context, inventory, runtime_dir=runtime_dir)
        app.register_resources()
        app.register_tools()
        return app

    def _run_engine_install(self, package_id: str) -> dict[str, Any]:
        """Esegue l'installazione di un pacchetto tramite engine.

        Args:
            package_id: ID del pacchetto da installare.

        Returns:
            Dict con ``success: bool`` e informazioni sull'operazione.
        """
        try:
            app = self._build_minimal_engine()
            return asyncio.run(app.install_package_for_onboarding(package_id))
        except RuntimeError as exc:
            _log.warning(
                "[SPARK-ENGINE][CLI] install: event loop attivo per %s: %s",
                package_id,
                exc,
            )
            return {"success": False, "error": f"Event loop attivo: {exc}"}
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "[SPARK-ENGINE][CLI] install: errore imprevisto per %s: %s",
                package_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    def _run_engine_remove(self, package_id: str) -> dict[str, Any]:
        """Esegue la rimozione di un pacchetto tramite engine.

        Legge il manifest direttamente: se il pacchetto non è installato
        ritorna errore senza costruire l'engine.

        Args:
            package_id: ID del pacchetto da rimuovere.

        Returns:
            Dict con ``success: bool`` e informazioni sull'operazione.
        """
        try:
            from spark.manifest.manifest import ManifestManager  # noqa: PLC0415

            manifest = ManifestManager(self._github_root)
            installed = manifest.get_installed_versions()
            if package_id not in installed:
                return {
                    "success": False,
                    "error": f"Pacchetto '{package_id}' non installato.",
                }

            app = self._build_minimal_engine()

            async def _do_remove() -> dict[str, Any]:
                # Recupera la funzione scf_remove_package registrata nell'engine
                remove_fn = getattr(app, "_remove_package_v3", None)
                if remove_fn is None:
                    return {"success": False, "error": "Metodo remove non disponibile."}
                entries = manifest.load()
                v3_entry = next(
                    (
                        e for e in entries
                        if str(e.get("installation_mode", "")).strip() == "v3_store"
                        and str(e.get("package", "")).strip() == package_id
                    ),
                    None,
                )
                if v3_entry is None:
                    return {"success": False, "error": f"Entry v3 non trovata per '{package_id}'."}
                return await remove_fn(
                    package_id=package_id,
                    manifest=manifest,
                    v3_entry=v3_entry,
                )

            return asyncio.run(_do_remove())

        except RuntimeError as exc:
            _log.warning(
                "[SPARK-ENGINE][CLI] remove: event loop attivo per %s: %s",
                package_id,
                exc,
            )
            return {"success": False, "error": f"Event loop attivo: {exc}"}
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "[SPARK-ENGINE][CLI] remove: errore imprevisto per %s: %s",
                package_id,
                exc,
            )
            return {"success": False, "error": str(exc)}
