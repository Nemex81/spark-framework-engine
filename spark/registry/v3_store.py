# Modulo registry/v3_store — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""Helpers per gestione store v3 dei pacchetti."""
from __future__ import annotations


_V3_STORE_INSTALLATION_MODE: str = "v3_store"


def _v3_store_sentinel_file(package_id: str) -> str:
    """Path sentinella usato come ``file`` nelle entry v3_store del manifest.

    Volutamente non corrispondente a un path reale sotto ``workspace/.github/``
    affinché ``ManifestManager.get_file_owners`` e simili non lo confondano
    con un file workspace tracciato.
    """
    return f"__store__/{package_id}"


def _build_package_raw_url_base(repo_url: str) -> str:
    """Trasforma ``https://github.com/<owner>/<repo>`` in URL raw branch main."""
    if not repo_url.startswith("https://github.com/"):
        raise ValueError(
            f"Unsupported repo URL: {repo_url!r}. Only github.com URLs supported."
        )
    return (
        repo_url.replace("https://github.com/", "https://raw.githubusercontent.com/")
        + "/main/"
    )
