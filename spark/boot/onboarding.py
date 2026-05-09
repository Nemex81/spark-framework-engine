"""OnboardingManager — primo avvio automatico SPARK.

Eseguito da ``spark.boot.sequence`` dopo ``ensure_minimal_bootstrap``.
Garantisce che al primo avvio il workspace riceva:
- bootstrap Cat.A completato (già gestito da ensure_minimal_bootstrap)
- lo store locale dei pacchetti popolato (almeno spark-base)
- tutti i pacchetti dichiarati in ``.github/spark-packages.json`` installati

Tutte le operazioni sono idempotenti e non fatali: gli errori vengono
loggati su stderr e inclusi nel risultato, ma non interrompono il boot.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from spark.boot.engine import SparkFrameworkEngine
    from spark.core.models import WorkspaceContext
    from spark.inventory import FrameworkInventory

_log: logging.Logger = logging.getLogger("spark-framework-engine")

# Pacchetto base installato in assenza di spark-packages.json.
_DEFAULT_BASE_PACKAGE: str = "spark-base"

# Path relativo (rispetto a github_root) del file di dichiarazione pacchetti.
_SPARK_PACKAGES_FILE: str = "spark-packages.json"


class OnboardingManager:
    """Gestisce il ciclo di onboarding al primo avvio del workspace.

    Args:
        context: WorkspaceContext del workspace utente.
        inventory: FrameworkInventory corrente.
        app: istanza SparkFrameworkEngine per eseguire operazioni engine.

    Example:
        >>> manager = OnboardingManager(context, inventory, app)
        >>> if manager.is_first_run():
        ...     result = manager.run_onboarding()
    """

    def __init__(
        self,
        context: "WorkspaceContext",
        inventory: "FrameworkInventory",
        app: "SparkFrameworkEngine",
    ) -> None:
        self._ctx = context
        self._inventory = inventory
        self._app = app

    # ------------------------------------------------------------------
    # Interfaccia pubblica
    # ------------------------------------------------------------------

    def is_first_run(self) -> bool:
        """Ritorna True se il workspace ha pacchetti dichiarati non ancora installati.

        La condizione "primo avvio" è determinata confrontando la lista pacchetti
        in ``.github/spark-packages.json`` con quelli presenti nel manifest.
        Se il file non esiste, si usa la logica legacy (manifest vuoto = primo avvio).
        Idempotente: torna False non appena tutti i pacchetti dichiarati sono installati.

        Returns:
            True se almeno un pacchetto dichiarato non è ancora installato.
        """
        try:
            spark_packages_file = self._ctx.github_root / _SPARK_PACKAGES_FILE
            if spark_packages_file.is_file():
                raw = json.loads(spark_packages_file.read_text(encoding="utf-8"))
                if not raw.get("auto_install", True):
                    return False
                declared: list[str] = raw.get("packages", [])
                if not isinstance(declared, list) or not declared:
                    return False
                from spark.manifest.manifest import ManifestManager  # noqa: PLC0415
                manifest = ManifestManager(self._ctx.github_root)
                installed = set(manifest.get_installed_versions().keys())
                return any(
                    isinstance(pkg, str) and pkg.strip() and pkg.strip() not in installed
                    for pkg in declared
                )
            # Fallback legacy: nessun file dichiarativo → manifest vuoto = primo avvio.
            from spark.manifest.manifest import ManifestManager  # noqa: PLC0415
            manifest = ManifestManager(self._ctx.github_root)
            installed = manifest.get_installed_versions()
            return len(installed) == 0
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "[SPARK-ENGINE][ONBOARDING] Impossibile leggere manifest per is_first_run: %s",
                exc,
            )
            # In caso di errore di lettura, assumiamo che non sia il primo avvio
            # per evitare loop di onboarding su workspace con manifest corrotto.
            return False

    def run_onboarding(self) -> dict[str, Any]:
        """Esegue il ciclo di onboarding completo.

        Sequenza:
        1. Verifica/esegue bootstrap Cat.A (``_ensure_bootstrap``).
        2. Verifica/popola store locale (``_ensure_store_populated``).
        3. Installa pacchetti da ``.github/spark-packages.json`` se esiste
           (``_install_declared_packages``).

        Returns:
            Dict con chiavi:
            - ``status``: "completed" | "partial" | "skipped"
            - ``steps_completed``: lista nomi step completati
            - ``steps_skipped``: lista nomi step saltati
            - ``packages_installed``: lista pacchetti installati in questa sessione
            - ``errors``: lista stringhe di errore non fatali
        """
        result: dict[str, Any] = {
            "status": "completed",
            "steps_completed": [],
            "steps_skipped": [],
            "packages_installed": [],
            "errors": [],
        }

        _log.info("[SPARK-ENGINE][ONBOARDING] Avvio onboarding primo lancio.")

        # Step 1 — Bootstrap Cat.A
        try:
            bootstrap_ok = self._ensure_bootstrap()
            if bootstrap_ok:
                result["steps_completed"].append("bootstrap")
            else:
                result["steps_skipped"].append("bootstrap")
        except Exception as exc:  # noqa: BLE001
            error_msg = f"Bootstrap step error: {exc}"
            _log.warning("[SPARK-ENGINE][ONBOARDING] %s", error_msg)
            result["errors"].append(error_msg)
            result["steps_skipped"].append("bootstrap")

        # Step 2 — Store popolato
        try:
            store_ok = self._ensure_store_populated()
            if store_ok:
                result["steps_completed"].append("store_populated")
            else:
                result["steps_skipped"].append("store_populated")
        except Exception as exc:  # noqa: BLE001
            error_msg = f"Store population step error: {exc}"
            _log.warning("[SPARK-ENGINE][ONBOARDING] %s", error_msg)
            result["errors"].append(error_msg)
            result["steps_skipped"].append("store_populated")

        # Step 3 — Pacchetti dichiarati
        try:
            installed_pkgs = self._install_declared_packages()
            result["packages_installed"].extend(installed_pkgs)
            if installed_pkgs:
                result["steps_completed"].append("declared_packages")
            else:
                result["steps_skipped"].append("declared_packages")
        except Exception as exc:  # noqa: BLE001
            error_msg = f"Declared packages step error: {exc}"
            _log.warning("[SPARK-ENGINE][ONBOARDING] %s", error_msg)
            result["errors"].append(error_msg)
            result["steps_skipped"].append("declared_packages")

        # Determina status finale
        if result["errors"]:
            result["status"] = "partial"
        elif not result["steps_completed"]:
            result["status"] = "skipped"

        _log.info(
            "[SPARK-ENGINE][ONBOARDING] Onboarding completato: status=%s, "
            "steps_completed=%s, packages_installed=%s, errors=%d",
            result["status"],
            result["steps_completed"],
            result["packages_installed"],
            len(result["errors"]),
        )
        return result

    # ------------------------------------------------------------------
    # Step interni
    # ------------------------------------------------------------------

    def _ensure_bootstrap(self) -> bool:
        """Garantisce che ensure_minimal_bootstrap sia stato eseguito.

        Chiama il metodo bootstrap dell'engine solo se il workspace non risulta
        già bootstrapped (verifica i path Cat.A sentinella).

        Returns:
            True se il bootstrap è stato eseguito o era già presente.
        """
        # Verifica presenza path sentinella bootstrap
        required_paths = self._app._minimal_bootstrap_required_paths()
        if all(p.is_file() for p in required_paths):
            _log.info(
                "[SPARK-ENGINE][ONBOARDING] Bootstrap già presente, step saltato."
            )
            return False

        _log.info("[SPARK-ENGINE][ONBOARDING] Esecuzione bootstrap Cat.A...")
        bootstrap_result = self._app.ensure_minimal_bootstrap()
        success = bool(bootstrap_result.get("success", False))
        _log.info(
            "[SPARK-ENGINE][ONBOARDING] Bootstrap result: status=%s",
            bootstrap_result.get("status", "unknown"),
        )
        return success

    def _ensure_store_populated(self) -> bool:
        """Verifica e segnala se lo store locale dei pacchetti è vuoto.

        Non esegue download di rete in questa fase — rileva solo la condizione
        e la logga. L'installazione effettiva avviene in ``_install_declared_packages``.

        Returns:
            True se lo store contiene almeno un pacchetto, False se vuoto.
        """
        from spark.packages.store import PackageResourceStore  # noqa: PLC0415

        store = PackageResourceStore(self._ctx.engine_root)
        packages_root = store.packages_root

        if not packages_root.is_dir():
            _log.info(
                "[SPARK-ENGINE][ONBOARDING] Store pacchetti assente: %s",
                packages_root,
            )
            return False

        # Conta le directory che contengono un package-manifest.json
        installed_in_store = [
            d for d in packages_root.iterdir()
            if d.is_dir() and (d / "package-manifest.json").is_file()
        ]

        if not installed_in_store:
            _log.info(
                "[SPARK-ENGINE][ONBOARDING] Store pacchetti vuoto in: %s",
                packages_root,
            )
            return False

        _log.info(
            "[SPARK-ENGINE][ONBOARDING] Store pacchetti: %d pacchetti presenti.",
            len(installed_in_store),
        )
        return True

    def _install_declared_packages(self) -> list[str]:
        """Installa pacchetti da ``.github/spark-packages.json`` se il file esiste.

        Se il file non esiste, non esegue nulla (no default installs automatici —
        il bootstrap Cat.A viene gestito da ensure_minimal_bootstrap).

        Il file ``.github/spark-packages.json`` deve rispettare lo schema in
        ``spark/assets/spark-packages.schema.json``:
        ``{"packages": ["spark-base", ...], "auto_install": true}``

        Returns:
            Lista degli ID pacchetti installati con successo in questa sessione.
        """
        spark_packages_file = self._ctx.github_root / _SPARK_PACKAGES_FILE

        if not spark_packages_file.is_file():
            _log.info(
                "[SPARK-ENGINE][ONBOARDING] File spark-packages.json non presente "
                "in %s — nessuna installazione automatica.",
                self._ctx.github_root,
            )
            return []

        # Leggi la lista pacchetti dichiarati
        try:
            raw = json.loads(spark_packages_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _log.warning(
                "[SPARK-ENGINE][ONBOARDING] Impossibile leggere spark-packages.json: %s",
                exc,
            )
            return []

        # Verifica flag auto_install (default True)
        if not raw.get("auto_install", True):
            _log.info(
                "[SPARK-ENGINE][ONBOARDING] auto_install=false in spark-packages.json, skip."
            )
            return []

        packages_to_install: list[str] = raw.get("packages", [])
        if not isinstance(packages_to_install, list):
            _log.warning(
                "[SPARK-ENGINE][ONBOARDING] spark-packages.json: campo 'packages' non è una lista."
            )
            return []

        if not packages_to_install:
            _log.info(
                "[SPARK-ENGINE][ONBOARDING] spark-packages.json: lista pacchetti vuota."
            )
            return []

        # Verifica quali pacchetti sono già installati
        from spark.manifest.manifest import ManifestManager  # noqa: PLC0415
        manifest = ManifestManager(self._ctx.github_root)
        already_installed = set(manifest.get_installed_versions().keys())

        installed_this_session: list[str] = []

        for package_id in packages_to_install:
            if not isinstance(package_id, str) or not package_id.strip():
                continue

            package_id = package_id.strip()

            if package_id in already_installed:
                _log.info(
                    "[SPARK-ENGINE][ONBOARDING] Pacchetto %s già installato, skip.",
                    package_id,
                )
                continue

            # L'installazione richiede il tool scf_install_package che è async
            # e opera nella closure register_tools. Qui usiamo il metodo engine
            # diretto con asyncio.run, come fa ensure_minimal_bootstrap.
            _log.info(
                "[SPARK-ENGINE][ONBOARDING] Installazione pacchetto dichiarato: %s",
                package_id,
            )
            try:
                import asyncio  # noqa: PLC0415
                install_result = asyncio.run(
                    self._app.install_package_for_onboarding(package_id)
                )
                if install_result.get("success"):
                    installed_this_session.append(package_id)
                    _log.info(
                        "[SPARK-ENGINE][ONBOARDING] Pacchetto %s installato: %s",
                        package_id,
                        install_result.get("message", "OK"),
                    )
                else:
                    _log.warning(
                        "[SPARK-ENGINE][ONBOARDING] Installazione %s fallita: %s",
                        package_id,
                        install_result.get("error", "unknown error"),
                    )
            except RuntimeError as exc:
                # asyncio.run() lancia RuntimeError se c'è già un event loop attivo.
                _log.warning(
                    "[SPARK-ENGINE][ONBOARDING] Impossibile eseguire install per %s "
                    "(event loop attivo): %s",
                    package_id,
                    exc,
                )
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "[SPARK-ENGINE][ONBOARDING] Errore imprevisto installazione %s: %s",
                    package_id,
                    exc,
                )

        return installed_this_session
