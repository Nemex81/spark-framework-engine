"""Initialize a VS Code workspace file for the SPARK framework engine."""

from __future__ import annotations

import hashlib
import difflib
import json
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SERVER_ID = "sparkFrameworkEngine"
REGISTRY_URL = "https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json"
REGISTRY_CACHE_REL = Path(".github/.scf-registry-cache.json")
MANIFEST_REL = Path(".github/.scf-manifest.json")
MANIFEST_SCHEMA_VERSION = "1.0"
SUPPORTED_MANIFEST_SCHEMA_VERSIONS = {"1.0", "2.0"}
SPARK_BASE_ID = "spark-base"
MINIMUM_PYTHON_VERSION = (3, 10)
ENGINE_VENV_REL = Path(".venv")
MCP_PACKAGE = "mcp"
_BOOTSTRAP_SUPPORTED_CONFLICT_MODES = {"abort", "replace", "preserve", "integrate"}


def _resolve_package_version(manifest_version: Any, registry_version: Any) -> str:
    """Prefer the package manifest version and fall back to the registry hint."""
    manifest_value = str(manifest_version or "").strip()
    if manifest_value:
        return manifest_value
    registry_value = str(registry_version or "").strip()
    if registry_value:
        return registry_value
    return "unknown"


def _configure_stdio() -> None:
    """Prefer UTF-8 streams so the summary renders consistently on Windows."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        stream.reconfigure(encoding="utf-8", errors="replace")


def _log(level: str, message: str) -> None:
    """Write one structured diagnostic line to stderr."""
    print(f"[SPARK-INIT][{level}] {message}", file=sys.stderr)


def _engine_venv_python(engine_root: Path) -> Path:
    """Return the expected Python executable inside the engine-local virtualenv."""
    if sys.platform == "win32":
        return engine_root / ENGINE_VENV_REL / "Scripts" / "python.exe"
    return engine_root / ENGINE_VENV_REL / "bin" / "python"


def _python_version_supported(major: int, minor: int) -> bool:
    """Return True when one interpreter satisfies the minimum supported version."""
    return (major, minor) >= MINIMUM_PYTHON_VERSION


def _run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run one command and capture UTF-8 output for diagnostics."""
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _run_checked_command(args: list[str], description: str) -> None:
    """Run one command and raise a bootstrap error on failure."""
    result = _run_command(args)
    if result.returncode == 0:
        return
    detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
    raise _BootstrapError(f"{description} fallito: {detail}")


def _command_succeeds(args: list[str]) -> bool:
    """Return True when the command exits successfully."""
    try:
        return _run_command(args).returncode == 0
    except OSError:
        return False


def _python_command_supports_minimum_version(command: list[str]) -> bool:
    """Return True when one Python command exists and supports the minimum version."""
    try:
        result = _run_command(
            [
                *command,
                "-c",
                "import sys; print(sys.version_info.major, sys.version_info.minor)",
            ]
        )
    except OSError:
        return False
    if result.returncode != 0:
        return False
    parts = result.stdout.strip().split()
    if len(parts) < 2:
        return False
    try:
        major = int(parts[0])
        minor = int(parts[1])
    except ValueError:
        return False
    return _python_version_supported(major, minor)


def _resolve_bootstrap_python() -> list[str]:
    """Resolve one Python command suitable to create the engine-local virtualenv."""
    if sys.executable and _python_version_supported(sys.version_info.major, sys.version_info.minor):
        return [sys.executable]

    candidates: list[list[str]] = []
    if sys.platform == "win32":
        candidates.append(["py", "-3"])
    candidates.extend([["python3"], ["python"]])

    for candidate in candidates:
        if _python_command_supports_minimum_version(candidate):
            return candidate

    min_major, min_minor = MINIMUM_PYTHON_VERSION
    raise _BootstrapError(
        f"Python {min_major}.{min_minor}+ richiesto per creare il runtime locale di SPARK."
    )


def _venv_has_mcp(venv_python: Path) -> bool:
    """Return True when the engine-local virtualenv already provides the mcp package."""
    if not venv_python.is_file():
        return False
    return _command_succeeds(
        [
            str(venv_python),
            "-c",
            (
                "import importlib.util, sys; "
                f"sys.exit(0 if importlib.util.find_spec('{MCP_PACKAGE}') else 1)"
            ),
        ]
    )


def _ensure_engine_runtime(engine_root: Path) -> Path:
    """Create and prepare the engine-local virtualenv when it is missing or incomplete."""
    venv_dir = engine_root / ENGINE_VENV_REL
    venv_python = _engine_venv_python(engine_root)

    if not venv_python.is_file():
        bootstrap_python = _resolve_bootstrap_python()
        _log("INFO", f"Runtime locale assente; creo la virtualenv in {venv_dir}")
        _run_checked_command(
            [*bootstrap_python, "-m", "venv", str(venv_dir)],
            "Creazione virtualenv locale SPARK",
        )

    if not venv_python.is_file():
        raise _BootstrapError(
            f"Virtualenv locale creata ma interprete non trovato in {venv_python}"
        )

    if not _venv_has_mcp(venv_python):
        _log("INFO", "Dipendenza 'mcp' assente nel runtime locale; installazione in corso.")
        _run_checked_command(
            [str(venv_python), "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
            "Aggiornamento pip nel runtime locale SPARK",
        )
        _run_checked_command(
            [str(venv_python), "-m", "pip", "install", "--quiet", "--upgrade", MCP_PACKAGE],
            "Installazione dipendenza mcp nel runtime locale SPARK",
        )

    return venv_python


def _build_server_config(project_root: Path, engine_script: Path) -> dict[str, Any]:
    """Build the MCP server configuration for the current project."""
    engine_root = engine_script.parent
    python_cmd = _engine_venv_python(engine_root)
    return {
        "type": "stdio",
        "command": str(python_cmd),
        "args": [str(engine_script)],
        "env": {
            "WORKSPACE_FOLDER": str(project_root),
        },
    }


def _build_workspace_template(project_root: Path, engine_script: Path) -> dict[str, Any]:
    """Return the default .code-workspace payload for a new project."""
    return {
        "folders": [{"path": "."}],
        "settings": {},
        "mcp": {
            "servers": {
                SERVER_ID: _build_server_config(project_root, engine_script)
            }
        },
    }


def _workspace_candidates(project_root: Path) -> list[Path]:
    """Return existing .code-workspace files in the project root."""
    return sorted(path for path in project_root.glob("*.code-workspace") if path.is_file())


def _update_existing_workspace(
    workspace_path: Path,
    project_root: Path,
    engine_script: Path,
) -> tuple[bool, str]:
    """Update an existing workspace file with the SPARK MCP server."""
    try:
        workspace_data = json.loads(workspace_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"JSON workspace non valido in {workspace_path}: {exc}"

    if not isinstance(workspace_data, dict):
        return False, f"Il file workspace deve contenere un oggetto JSON: {workspace_path}"

    settings = workspace_data.get("settings")
    if settings is None:
        settings = {}
        workspace_data["settings"] = settings
    elif not isinstance(settings, dict):
        return False, f"La chiave 'settings' deve essere un oggetto JSON: {workspace_path}"

    settings.pop("mcp", None)

    mcp_settings = workspace_data.get("mcp")
    if mcp_settings is None:
        mcp_settings = {}
        workspace_data["mcp"] = mcp_settings
    elif not isinstance(mcp_settings, dict):
        return False, f"La chiave 'mcp' deve essere un oggetto JSON: {workspace_path}"

    servers = mcp_settings.get("servers")
    if servers is None:
        servers = {}
        mcp_settings["servers"] = servers
    elif not isinstance(servers, dict):
        return False, f"La chiave 'mcp.servers' deve essere un oggetto JSON: {workspace_path}"

    servers[SERVER_ID] = _build_server_config(project_root, engine_script)
    workspace_path.write_text(
        json.dumps(workspace_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return True, f"Workspace aggiornato: {workspace_path.name}"


def _create_workspace_file(
    workspace_path: Path,
    project_root: Path,
    engine_script: Path,
) -> str:
    """Create a new .code-workspace file for the project."""
    workspace_data = _build_workspace_template(project_root, engine_script)
    workspace_path.write_text(
        json.dumps(workspace_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return f"Workspace creato: {workspace_path.name}"


def _write_vscode_mcp_json(
    project_root: Path,
    engine_script: Path,
) -> tuple[bool, str]:
    """Create or update .vscode/mcp.json preserving non-SPARK servers."""
    mcp_config_path = project_root / ".vscode" / "mcp.json"
    file_exists = mcp_config_path.exists()
    mcp_config_path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, Any] = {}
    if mcp_config_path.exists():
        try:
            raw = json.loads(mcp_config_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                _log(
                    "ERROR",
                    ".vscode/mcp.json non contiene un oggetto JSON valido; verra ricreato.",
                )
            else:
                existing = raw
        except json.JSONDecodeError as exc:
            _log("ERROR", f".vscode/mcp.json JSON corrotto ({exc}); verra ricreato.")

    servers = existing.get("servers", {})
    if not isinstance(servers, dict):
        _log(
            "ERROR",
            "La chiave 'servers' in .vscode/mcp.json non e un oggetto JSON; verra ricostruita.",
        )
        servers = {}

    servers[SERVER_ID] = _build_server_config(project_root, engine_script)
    existing["servers"] = servers
    mcp_config_path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _log("INFO", f"Configurazione MCP aggiornata: {mcp_config_path}")
    return True, "creato" if not file_exists else "aggiornato"


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(content: str) -> str:
    """Return the SHA-256 hex digest of one UTF-8 text payload."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _utc_timestamp() -> str:
    """Return the current UTC timestamp serialized for the SCF manifest."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class _RegistryPackage:
    """Describe one package entry resolved from the SCF registry."""

    package_id: str
    repo_url: str
    latest_version: str


@dataclass(frozen=True)
class _InstallPlanItem:
    """Describe one file action for the embedded spark-base bootstrap."""

    file_path: str
    rel_path: str
    content: str
    sha256: str
    action: str


@dataclass(frozen=True)
class _BootstrapConflict:
    """Describe one conflicting file encountered during standalone bootstrap."""

    file_path: str
    reason: str


class _BootstrapError(RuntimeError):
    """Raised when spark-base bootstrap cannot complete safely."""


class _BootstrapConflictError(_BootstrapError):
    """Raised when bootstrap needs an explicit user decision for conflicting files."""

    def __init__(self, message: str, conflicts: list[_BootstrapConflict]) -> None:
        super().__init__(message)
        self.conflicts = conflicts


def _read_text_if_possible(path: Path) -> str | None:
    """Read one UTF-8 text file, returning None for binary or invalid payloads."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _normalize_newlines(text: str) -> str:
    """Normalize line endings before comparing text payloads."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Split YAML frontmatter from markdown body when present."""
    normalized = _normalize_newlines(text)
    if not normalized.startswith("---\n"):
        return "", normalized
    end = normalized.find("\n---\n", 4)
    if end == -1:
        return "", normalized
    return normalized[: end + 5], normalized[end + 5 :]


def _merge_bootstrap_text(existing_text: str, incoming_text: str) -> str | None:
    """Create a conservative integrated text for first-time bootstrap conflicts."""
    normalized_existing = _normalize_newlines(existing_text)
    normalized_incoming = _normalize_newlines(incoming_text)

    if normalized_existing == normalized_incoming:
        return normalized_existing
    if normalized_existing in normalized_incoming:
        return normalized_incoming
    if normalized_incoming in normalized_existing:
        return normalized_existing

    existing_frontmatter, existing_body = _split_frontmatter(normalized_existing)
    incoming_frontmatter, incoming_body = _split_frontmatter(normalized_incoming)
    frontmatter = incoming_frontmatter or existing_frontmatter

    merged_body_lines = list(existing_body.splitlines())
    existing_keys = {line.strip() for line in merged_body_lines if line.strip()}
    remote_lines = incoming_body.splitlines()
    sequence = difflib.SequenceMatcher(a=merged_body_lines, b=remote_lines)
    for opcode, _a0, _a1, b0, b1 in sequence.get_opcodes():
        if opcode == "equal":
            continue
        for line in remote_lines[b0:b1]:
            key = line.strip()
            if key and key in existing_keys:
                continue
            merged_body_lines.append(line)
            if key:
                existing_keys.add(key)

    merged_body = "\n".join(merged_body_lines).strip("\n")
    if not merged_body and not frontmatter:
        return None
    if frontmatter:
        return f"{frontmatter}\n{merged_body}\n"
    return f"{merged_body}\n"


def _prompt_bootstrap_conflict_mode(conflicts: list[_BootstrapConflict]) -> str:
    """Ask the user how standalone bootstrap should handle conflicting files."""
    print("[SPARK-INIT] Trovati file gia presenti in conflitto con spark-base:", file=sys.stderr)
    for conflict in conflicts:
        print(f"[SPARK-INIT] - {conflict.file_path}: {conflict.reason}", file=sys.stderr)
    print(
        "[SPARK-INIT] Scegli: [r] replace, [p] preserve, [i] integrate, [a] annulla",
        file=sys.stderr,
    )
    response = input().strip().lower()
    if response in {"r", "replace"}:
        return "replace"
    if response in {"p", "preserve", "keep", "mantieni"}:
        return "preserve"
    if response in {"i", "integrate", "merge", "integra"}:
        return "integrate"
    return "abort"


class _BootstrapInstaller:
    """Install spark-base directly from the public registry into the workspace."""

    def __init__(self, project_root: Path, engine_root: Path) -> None:
        self._project_root = project_root
        self._engine_root = engine_root
        self._manifest_path = project_root / MANIFEST_REL
        self._registry_cache_path = engine_root / REGISTRY_CACHE_REL

    def ensure_spark_base(self, conflict_mode: str = "abort") -> str:
        """Install spark-base once, or return that it is already present."""
        if conflict_mode not in _BOOTSTRAP_SUPPORTED_CONFLICT_MODES:
            raise _BootstrapError(
                f"Unsupported bootstrap conflict_mode '{conflict_mode}'. "
                "Supported modes: abort, replace, preserve, integrate."
            )
        entries = self._load_manifest_entries()
        if self._has_existing_install(entries):
            _log(
                "INFO",
                "spark-base e gia tracciato nel manifest; bootstrap pacchetto saltato.",
            )
            return "già presente"

        package_info = self._resolve_spark_base_package()
        package_manifest = self._fetch_package_manifest(package_info.repo_url)
        package_version = _resolve_package_version(
            package_manifest.get("version", ""),
            package_info.latest_version,
        )

        registry_version = package_info.latest_version.strip()
        if registry_version and registry_version != package_version:
            _log(
                "WARNING",
                "Il registry pubblica spark-base "
                f"{registry_version}, ma il manifest remoto dichiara {package_version}.",
            )

        files = package_manifest.get("files")
        if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
            raise _BootstrapError("Il package-manifest di spark-base non contiene una lista 'files' valida.")

        plan = self._build_install_plan(
            files,
            package_info.repo_url,
            entries,
            conflict_mode=conflict_mode,
        )
        self._apply_install_plan(plan, package_version)
        _log("INFO", "spark-base installato correttamente nel workspace.")
        return "installato"

    def _build_install_plan(
        self,
        files: list[str],
        repo_url: str,
        entries: list[dict[str, Any]],
        conflict_mode: str = "abort",
    ) -> list[_InstallPlanItem]:
        """Prepare a safe write/adopt plan before touching the workspace."""
        tracked_entries = {
            str(entry.get("file", "")).strip(): entry
            for entry in entries
            if str(entry.get("file", "")).strip()
        }
        plan: list[_InstallPlanItem] = []
        blocking_conflicts: list[_BootstrapConflict] = []

        for file_path in files:
            if not file_path.startswith(".github/"):
                blocking_conflicts.append(
                    _BootstrapConflict(file_path, "Percorso non supportato fuori da .github/")
                )
                continue

            rel_path = file_path.removeprefix(".github/")
            dest_path = self._project_root / file_path
            content = self._fetch_raw_text(self._build_raw_url(repo_url, file_path))
            content_sha256 = _sha256_text(content)
            tracked_entry = tracked_entries.get(rel_path)

            if tracked_entry is not None:
                tracked_package = str(tracked_entry.get("package", "")).strip()
                if tracked_package != SPARK_BASE_ID:
                    blocking_conflicts.append(
                        _BootstrapConflict(file_path, f"gia tracciato dal pacchetto {tracked_package}")
                    )
                    continue
                if dest_path.exists() and _sha256_file(dest_path) != str(tracked_entry.get("sha256", "")):
                    if conflict_mode == "replace":
                        plan.append(
                            _InstallPlanItem(file_path, rel_path, content, content_sha256, "write")
                        )
                    else:
                        _log("INFO", f"Preservato file modificato dall'utente: {file_path}")
                    continue
                action = "write"
                if dest_path.exists() and _sha256_file(dest_path) == content_sha256:
                    action = "adopt"
                plan.append(
                    _InstallPlanItem(file_path, rel_path, content, content_sha256, action)
                )
                continue

            if dest_path.exists():
                current_sha256 = _sha256_file(dest_path)
                if current_sha256 == content_sha256:
                    plan.append(
                        _InstallPlanItem(file_path, rel_path, content, content_sha256, "adopt")
                    )
                elif conflict_mode == "replace":
                    _log("WARNING", f"Sostituisco file esistente non tracciato: {file_path}")
                    plan.append(
                        _InstallPlanItem(file_path, rel_path, content, content_sha256, "write")
                    )
                elif conflict_mode == "preserve":
                    existing_text = _read_text_if_possible(dest_path)
                    if existing_text is None:
                        blocking_conflicts.append(
                            _BootstrapConflict(file_path, "file esistente non testuale: preserve non supportato")
                        )
                    else:
                        _log("INFO", f"Mantengo file esistente come baseline locale: {file_path}")
                        plan.append(
                            _InstallPlanItem(file_path, rel_path, existing_text, current_sha256, "preserve")
                        )
                elif conflict_mode == "integrate":
                    existing_text = _read_text_if_possible(dest_path)
                    if existing_text is None:
                        blocking_conflicts.append(
                            _BootstrapConflict(file_path, "file esistente non testuale: integrazione non disponibile")
                        )
                    else:
                        merged_text = _merge_bootstrap_text(existing_text, content)
                        if merged_text is None:
                            blocking_conflicts.append(
                                _BootstrapConflict(file_path, "integrazione non sicura")
                            )
                        else:
                            merged_sha256 = _sha256_text(merged_text)
                            action = "adopt" if current_sha256 == merged_sha256 else "write"
                            _log("INFO", f"Integrazione best-effort pianificata: {file_path}")
                            plan.append(
                                _InstallPlanItem(file_path, rel_path, merged_text, merged_sha256, action)
                            )
                else:
                    blocking_conflicts.append(
                        _BootstrapConflict(file_path, "esiste gia ma non e tracciato nel manifest")
                    )
                continue

            plan.append(_InstallPlanItem(file_path, rel_path, content, content_sha256, "write"))

        if blocking_conflicts:
            for conflict in blocking_conflicts:
                _log("ERROR", f"{conflict.file_path}: {conflict.reason}")
            raise _BootstrapConflictError(
                "Bootstrap spark-base annullato per evitare overwrite su file esistenti.",
                blocking_conflicts,
            )

        return plan

    def _apply_install_plan(
        self,
        plan: list[_InstallPlanItem],
        package_version: str,
    ) -> None:
        """Apply the prepared plan and persist manifest ownership for spark-base."""
        if not plan:
            raise _BootstrapError("Nessun file installabile per spark-base dopo il preflight.")

        for item in plan:
            if item.action != "write":
                if item.action == "preserve":
                    _log("INFO", f"Preservato e tracciato come baseline locale: {item.file_path}")
                continue
            dest_path = self._project_root / item.file_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(item.content.encode("utf-8"))
            _log("INFO", f"Installato: {item.file_path}")

        existing_entries = self._load_manifest_entries()
        touched_files = {item.rel_path for item in plan}
        retained_entries = [
            entry
            for entry in existing_entries
            if not (
                str(entry.get("package", "")).strip() == SPARK_BASE_ID
                and str(entry.get("file", "")).strip() in touched_files
            )
        ]
        timestamp = _utc_timestamp()

        for item in plan:
            dest_path = self._project_root / item.file_path
            retained_entries.append(
                {
                    "file": item.rel_path,
                    "package": SPARK_BASE_ID,
                    "package_version": package_version,
                    "installed_at": timestamp,
                    "sha256": _sha256_file(dest_path),
                }
            )
            if item.action == "adopt":
                _log("INFO", f"Adottato nel manifest senza riscrittura: {item.file_path}")

        retained_entries.sort(key=lambda entry: (str(entry.get("file", "")), str(entry.get("package", ""))))
        self._save_manifest_entries(retained_entries)

        if not self._has_existing_install(retained_entries):
            raise _BootstrapError(
                "Manifest aggiornato senza ownership spark-base; bootstrap non considerato valido."
            )

    def _has_existing_install(self, entries: list[dict[str, Any]]) -> bool:
        """Return True when the manifest already tracks at least one spark-base file."""
        return any(
            str(entry.get("package", "")).strip() == SPARK_BASE_ID for entry in entries
        )

    def _resolve_spark_base_package(self) -> _RegistryPackage:
        """Resolve the spark-base registry entry from remote or local cache."""
        packages = self._fetch_registry().get("packages", [])
        if not isinstance(packages, list):
            raise _BootstrapError("Il registry non contiene una lista 'packages' valida.")

        for package in packages:
            if not isinstance(package, dict):
                continue
            if str(package.get("id", "")).strip() != SPARK_BASE_ID:
                continue
            repo_url = str(package.get("repo_url", "")).strip()
            if not repo_url:
                raise _BootstrapError("spark-base non definisce repo_url nel registry.")
            return _RegistryPackage(
                package_id=SPARK_BASE_ID,
                repo_url=repo_url,
                latest_version=str(package.get("latest_version", "")).strip(),
            )

        raise _BootstrapError("spark-base non trovato nel registry SCF.")

    def _fetch_registry(self) -> dict[str, Any]:
        """Fetch registry.json, falling back to the bundled cache on failure."""
        try:
            return self._fetch_json(REGISTRY_URL)
        except _BootstrapError as exc:
            _log("WARNING", f"Fetch registry fallita, uso la cache locale: {exc}")
            if not self._registry_cache_path.is_file():
                raise _BootstrapError("Registry remoto non disponibile e cache locale assente.") from exc
            try:
                return json.loads(self._registry_cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as cache_exc:
                raise _BootstrapError(f"Cache registry corrotta: {cache_exc}") from cache_exc

    def _fetch_package_manifest(self, repo_url: str) -> dict[str, Any]:
        """Fetch package-manifest.json from the public package repository."""
        return self._fetch_json(self._build_raw_url(repo_url, "package-manifest.json"))

    def _fetch_json(self, url: str) -> dict[str, Any]:
        """Fetch and decode one JSON document from a public raw GitHub URL."""
        raw_text = self._fetch_raw_text(url)
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise _BootstrapError(f"JSON remoto non valido da {url}: {exc}") from exc
        if not isinstance(payload, dict):
            raise _BootstrapError(f"Payload remoto non valido da {url}: atteso oggetto JSON.")
        return payload

    def _fetch_raw_text(self, url: str) -> str:
        """Fetch one UTF-8 text payload from a public raw GitHub URL."""
        request = urllib.request.Request(url, headers={"User-Agent": "spark-init"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                return response.read().decode("utf-8")
        except (urllib.error.URLError, OSError) as exc:
            raise _BootstrapError(f"Download fallito da {url}: {exc}") from exc

    def _build_raw_url(self, repo_url: str, file_path: str) -> str:
        """Convert a GitHub repository URL to the corresponding raw main URL."""
        if not repo_url.startswith("https://github.com/"):
            raise _BootstrapError(f"Repo URL non supportato: {repo_url}")
        base_url = repo_url.replace(
            "https://github.com/",
            "https://raw.githubusercontent.com/",
        )
        return f"{base_url}/main/{file_path}"

    def _load_manifest_entries(self) -> list[dict[str, Any]]:
        """Load manifest entries, failing closed when the file is corrupted."""
        if not self._manifest_path.is_file():
            return []
        try:
            raw = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise _BootstrapError(f"Manifest non leggibile: {exc}") from exc
        schema_version = str(raw.get("schema_version", "")).strip()
        if schema_version and schema_version not in SUPPORTED_MANIFEST_SCHEMA_VERSIONS:
            raise _BootstrapError(f"Schema manifest locale non supportata: {schema_version}")
        entries = raw.get("entries", [])
        if not isinstance(entries, list):
            raise _BootstrapError("Il manifest locale non contiene una lista 'entries' valida.")
        valid_entries = [entry for entry in entries if isinstance(entry, dict)]
        if len(valid_entries) != len(entries):
            raise _BootstrapError("Il manifest locale contiene entry non valide.")
        return valid_entries

    def _save_manifest_entries(self, entries: list[dict[str, Any]]) -> None:
        """Persist the manifest in the canonical entries[] format."""
        self._manifest_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "entries": entries,
        }
        self._manifest_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def main() -> int:
    """Entry point for standalone workspace initialization."""
    _configure_stdio()
    project_root = Path.cwd().resolve()
    engine_root = Path(__file__).resolve().parent
    engine_script = engine_root / "spark-framework-engine.py"

    if not engine_script.is_file():
        _log("ERROR", f"Server non trovato: {engine_script}")
        return 1

    try:
        _ensure_engine_runtime(engine_root)
    except _BootstrapError as exc:
        _log("ERROR", str(exc))
        return 1

    workspace_candidates = _workspace_candidates(project_root)
    workspace_path = (
        workspace_candidates[0]
        if workspace_candidates
        else project_root / f"{project_root.name}.code-workspace"
    )

    if workspace_candidates:
        workspace_action = "aggiornato"
        success, message = _update_existing_workspace(
            workspace_path,
            project_root,
            engine_script,
        )
        if not success:
            _log("ERROR", message)
            return 1
        _log("INFO", message)
        if len(workspace_candidates) > 1:
            _log(
                "WARNING",
                f"Trovati piu file .code-workspace. Uso: {workspace_path.name}",
            )
    else:
        workspace_action = "creato"
        message = _create_workspace_file(workspace_path, project_root, engine_script)
        _log("INFO", message)

    _settings_success, settings_action = _write_vscode_mcp_json(project_root, engine_script)

    try:
        bootstrap_action = _BootstrapInstaller(project_root, engine_root).ensure_spark_base()
    except _BootstrapConflictError as exc:
        selected_mode = _prompt_bootstrap_conflict_mode(exc.conflicts)
        if selected_mode == "abort":
            _log("ERROR", "Bootstrap annullato dall'utente dopo il rilevamento dei conflitti.")
            return 1
        try:
            bootstrap_action = _BootstrapInstaller(project_root, engine_root).ensure_spark_base(
                conflict_mode=selected_mode
            )
        except _BootstrapError as retry_exc:
            _log("ERROR", str(retry_exc))
            return 1
    except _BootstrapError as exc:
        _log("ERROR", str(exc))
        return 1

    print(f"[SPARK] .code-workspace → {workspace_action}: {workspace_path.name}")
    print(f"[SPARK] .vscode/mcp.json → {settings_action}")
    print(f"[SPARK] spark-base → {bootstrap_action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())