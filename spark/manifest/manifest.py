# Modulo manifest — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""ManifestManager — gestione del manifest .scf-manifest.json del workspace."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spark.core.constants import (
    _MANIFEST_FILENAME,
    _MANIFEST_SCHEMA_VERSION,
    _REGISTRY_CACHE_FILENAME,
    _SUPPORTED_MANIFEST_SCHEMA_VERSIONS,
)
from spark.core.utils import _sha256_text, parse_markdown_frontmatter
from spark.merge.sections import _strip_package_section
from spark.merge.validators import validate_structural

_log: logging.Logger = logging.getLogger("spark-framework-engine")


class ManifestManager:
    """Read, write and query the SCF installation manifest (.github/.scf-manifest.json).

    ``user_modified`` is computed on-demand by comparing the stored SHA-256 against
    the current file content on disk. It is never persisted to the manifest file.
    """

    def __init__(self, github_root: Path) -> None:
        self._github_root = github_root
        self._path = github_root / _MANIFEST_FILENAME

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> list[dict[str, Any]]:
        """Return the entries array. Returns [] if absent or unreadable."""
        if not self._path.is_file():
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            schema_version = str(raw.get("schema_version", "")).strip()
            if schema_version and schema_version not in _SUPPORTED_MANIFEST_SCHEMA_VERSIONS:
                _log.warning(
                    "Manifest schema '%s' unsupported, returning empty.", schema_version
                )
                return []
            entries = raw.get("entries", [])
            if not isinstance(entries, list):
                _log.warning("Manifest entries invalid, returning empty.")
                return []
            return list(entries)
        except (OSError, json.JSONDecodeError) as exc:
            _log.warning("Manifest unreadable, returning empty: %s", exc)
            return []

    def save(self, entries: list[dict[str, Any]]) -> None:
        """Persist entries to disk.

        Schema v3.0: emits an explicit ``overrides[]`` summary derived from
        entries tagged with ``override_type`` so external readers can locate
        workspace overrides without scanning every entry.
        """
        overrides_summary = self._build_overrides_summary(entries)
        payload: dict[str, Any] = {
            "schema_version": _MANIFEST_SCHEMA_VERSION,
            "entries": entries,
            "overrides": overrides_summary,
        }
        try:
            self._path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            _log.error("Cannot write manifest: %s", exc)
            raise

    @staticmethod
    def _build_overrides_summary(
        entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return ``[{type, name, file, sha256}, ...]`` for override entries."""
        out: list[dict[str, Any]] = []
        for entry in entries:
            override_type = str(entry.get("override_type", "")).strip()
            override_name = str(entry.get("override_name", "")).strip()
            if not override_type or not override_name:
                continue
            out.append(
                {
                    "type": override_type,
                    "name": override_name,
                    "file": str(entry.get("file", "")),
                    "sha256": str(entry.get("sha256", "")),
                }
            )
        out.sort(key=lambda item: (item["type"], item["name"]))
        return out

    def upsert(
        self,
        file_rel: str,
        package: str,
        package_version: str,
        file_abs: Path,
        merge_strategy: str | None = None,
    ) -> None:
        """Add or update the manifest entry for a single installed file."""
        entries = self.load()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entries = [
            e
            for e in entries
            if not (e.get("file") == file_rel and e.get("package") == package)
        ]
        new_entry = self._build_entry(
            file_rel,
            package,
            package_version,
            file_abs,
            now,
            self._resolve_entry_merge_strategy(entries, file_rel, package, merge_strategy),
        )
        entries.append(new_entry)
        self._sync_entries_for_files(entries, {file_rel: file_abs})
        self.save(entries)

    def remove_package(self, package: str) -> list[str]:
        """Remove a package's entries and delete unmodified files on disk.

        Returns the list of relative paths preserved because the user modified them.
        For v3_store entries, skip any workspace file operation (handled by v3 orchestrator).
        """
        entries = self.load()
        preserved: list[str] = []
        remaining: list[dict[str, Any]] = []
        updated_files: dict[str, Path] = {}
        for entry in entries:
            if entry.get("package") != package:
                remaining.append(entry)
                continue
            # v3_store: skip any workspace file operation
            if str(entry.get("installation_mode", "")).strip() == "v3_store":
                continue
            file_path = self._github_root / entry["file"]
            shared_with_other_packages = any(
                other_entry.get("package") != package and other_entry.get("file") == entry.get("file")
                for other_entry in entries
            )
            user_modified = self._is_user_modified(entry, file_path)
            if shared_with_other_packages:
                if file_path.is_file():
                    try:
                        current_text = file_path.read_text(encoding="utf-8")
                        updated_text = _strip_package_section(current_text, str(entry.get("package", "")).strip())
                        if updated_text != current_text:
                            if user_modified:
                                structural_ok, _, _ = validate_structural(updated_text, current_text)
                                if not structural_ok:
                                    _log.warning(
                                        "[SPARK-ENGINE][WARNING] Structural validation failed for user-modified shared file after strip; preserving: %s",
                                        file_path,
                                    )
                                    preserved.append(entry["file"])
                                else:
                                    file_path.write_text(updated_text, encoding="utf-8")
                                    updated_files[str(entry["file"])] = file_path
                                    _log.info(
                                        "[SPARK-ENGINE][INFO] Removed package section for user-modified shared file: %s",
                                        file_path,
                                    )
                            else:
                                file_path.write_text(updated_text, encoding="utf-8")
                                updated_files[str(entry["file"])] = file_path
                                _log.info("Removed package section for shared file: %s", file_path)
                        else:
                            if user_modified:
                                _log.info(
                                    "[SPARK-ENGINE][INFO] Strip no-op on user-modified shared file; leaving unchanged: %s",
                                    file_path,
                                )
                            else:
                                _log.info("Preserved shared file owned by other packages: %s", file_path)
                    except (OSError, UnicodeDecodeError) as exc:
                        _log.warning("Cannot update shared file %s during package removal: %s", file_path, exc)
                        preserved.append(entry["file"])
            elif user_modified:
                _log.warning("Preserving user-modified file: %s", file_path)
                preserved.append(entry["file"])
            else:
                if file_path.is_file():
                    try:
                        file_path.unlink()
                        _log.info("Removed file: %s", file_path)
                    except OSError as exc:
                        _log.warning("Cannot remove %s: %s", file_path, exc)
        self._sync_entries_for_files(remaining, updated_files)
        self.save(remaining)
        return preserved

    def is_user_modified(self, file_rel: str) -> bool | None:
        """On-demand check: True if user modified the file since install, None if untracked."""
        for entry in self.load():
            if entry.get("file") == file_rel:
                return self._is_user_modified(entry, self._github_root / file_rel)
        return None

    def get_installed_versions(self) -> dict[str, str]:
        """Return installed package versions keyed by package id."""
        versions: dict[str, str] = {}
        for entry in self.load():
            package_id = str(entry.get("package", "")).strip()
            package_version = str(entry.get("package_version", "")).strip()
            if package_id and package_version:
                versions[package_id] = package_version
        return dict(sorted(versions.items()))

    def get_file_owners(self, file_rel: str) -> list[str]:
        """Return sorted package owners for a tracked file path."""
        owners = {
            str(entry.get("package", "")).strip()
            for entry in self.load()
            if str(entry.get("file", "")).strip() == file_rel
            and str(entry.get("package", "")).strip()
        }
        return sorted(owners)

    def upsert_many(
        self,
        package: str,
        package_version: str,
        files: list[tuple[str, Path]],
        merge_strategies_by_file: dict[str, str] | None = None,
        stub_files: set[str] | None = None,
    ) -> None:
        """Add or update manifest entries for many installed files in one save.

        When ``stub_files`` is provided, every file_rel listed in the set is
        persisted with ``stub: true`` in the manifest entry. Callers compute
        the set from the package manifest's ``engine_provided_skills`` and
        ``engine_provided_instructions`` fields.
        """
        entries = self.load()
        replacements = {file_rel for file_rel, _ in files}
        entries = [
            entry
            for entry in entries
            if not (
                str(entry.get("file", "")).strip() in replacements
                and str(entry.get("package", "")).strip() == package
            )
        ]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        files_by_rel = dict(files)
        stub_lookup = stub_files or set()
        for file_rel, file_abs in files:
            requested_strategy = None
            if merge_strategies_by_file is not None:
                requested_strategy = merge_strategies_by_file.get(file_rel)
            entries.append(
                self._build_entry(
                    file_rel,
                    package,
                    package_version,
                    file_abs,
                    now,
                    self._resolve_entry_merge_strategy(
                        entries,
                        file_rel,
                        package,
                        requested_strategy,
                    ),
                    stub=file_rel in stub_lookup,
                )
            )
        self._sync_entries_for_files(entries, files_by_rel)
        self.save(entries)

    def remove_owner_entries(self, package: str, files: list[str]) -> None:
        """Remove manifest ownership entries for one package on selected files."""
        targets = {file_rel for file_rel in files if file_rel}
        if not targets:
            return
        entries = [
            entry
            for entry in self.load()
            if not (
                str(entry.get("package", "")).strip() == package
                and str(entry.get("file", "")).strip() in targets
            )
        ]
        self.save(entries)

    def verify_integrity(self) -> dict[str, Any]:
        """Verify manifest integrity against files currently present under .github/.
        For v3_store entries, skip any workspace file check (handled by v3 orchestrator).
        """
        entries = self.load()
        tracked_files: set[str] = set()
        missing: list[str] = []
        modified: list[str] = []
        ok: list[str] = []
        duplicate_owners_map: dict[str, set[str]] = {}
        entries_by_file: dict[str, list[dict[str, Any]]] = {}

        for entry in entries:
            file_rel = str(entry.get("file", "")).strip()
            package_id = str(entry.get("package", "")).strip()
            if not file_rel:
                continue
            # v3_store entries: skip any workspace file check
            if str(entry.get("installation_mode", "")).strip() == "v3_store":
                continue
            tracked_files.add(file_rel)
            entries_by_file.setdefault(file_rel, []).append(entry)
            owners = duplicate_owners_map.setdefault(file_rel, set())
            if package_id:
                owners.add(package_id)

            file_path = self._github_root / file_rel
            if not file_path.is_file():
                missing.append(file_rel)
            elif self._is_user_modified(entry, file_path):
                modified.append(file_rel)
            else:
                ok.append(file_rel)

        duplicate_owners = [
            {
                "file": file_rel,
                "owners": sorted(owners),
                "entry_count": sum(1 for entry in entries if str(entry.get("file", "")).strip() == file_rel),
            }
            for file_rel, owners in sorted(duplicate_owners_map.items())
            if len(owners) > 1
            and not self._entries_allow_shared_merge_sections(entries_by_file.get(file_rel, []))
        ]

        ignored_runtime_files = {_MANIFEST_FILENAME, _REGISTRY_CACHE_FILENAME}
        user_files: list[str] = []
        untagged_spark_files: list[str] = []
        orphan_candidates: list[str] = []  # retrocompatibilità: = untagged_spark_files

        if self._github_root.is_dir():
            for path in sorted(
                candidate for candidate in self._github_root.rglob("*") if candidate.is_file()
            ):
                rel_path = path.relative_to(self._github_root).as_posix()
                if rel_path in ignored_runtime_files:
                    continue
                if rel_path in tracked_files:
                    continue

                is_spark = False
                if path.suffix == ".md":
                    try:
                        file_content = path.read_text(encoding="utf-8", errors="replace")
                        fm = parse_markdown_frontmatter(file_content)
                        is_spark = bool(fm.get("spark", False))
                    except OSError:
                        pass

                if is_spark:
                    untagged_spark_files.append(rel_path)
                    orphan_candidates.append(rel_path)
                else:
                    user_files.append(rel_path)

        missing.sort()
        modified.sort()
        ok.sort()
        summary: dict[str, Any] = {
            "tracked_entries": len(entries),
            "ok_count": len(ok),
            "issue_count": len(missing) + len(modified) + len(duplicate_owners),
            "orphan_candidate_count": len(orphan_candidates),
            "user_file_count": len(user_files),
            "untagged_spark_count": len(untagged_spark_files),
        }
        return {
            "missing": missing,
            "modified": modified,
            "ok": ok,
            "duplicate_owners": duplicate_owners,
            "orphan_candidates": orphan_candidates,
            "user_files": user_files,
            "untagged_spark_files": untagged_spark_files,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sha256(path: Path) -> str:
        if not path.is_file():
            return ""
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _is_user_modified(self, entry: dict[str, Any], file_path: Path) -> bool:
        stored = entry.get("sha256", "")
        if not stored:
            return False
        return self._sha256(file_path) != stored

    @staticmethod
    def _normalize_merge_strategy(value: Any) -> str:
        strategy = str(value).strip()
        return strategy or "replace"

    def _resolve_entry_merge_strategy(
        self,
        entries: list[dict[str, Any]],
        file_rel: str,
        package: str,
        requested_strategy: str | None,
    ) -> str:
        if requested_strategy is not None:
            return self._normalize_merge_strategy(requested_strategy)

        for entry in entries:
            if (
                str(entry.get("file", "")).strip() == file_rel
                and str(entry.get("package", "")).strip() == package
            ):
                raw_strategy = str(entry.get("scf_merge_strategy", "")).strip()
                if raw_strategy:
                    return self._normalize_merge_strategy(raw_strategy)

        for entry in entries:
            if str(entry.get("file", "")).strip() == file_rel:
                raw_strategy = str(entry.get("scf_merge_strategy", "")).strip()
                if raw_strategy:
                    return self._normalize_merge_strategy(raw_strategy)

        return "replace"

    def _build_entry(
        self,
        file_rel: str,
        package: str,
        package_version: str,
        file_abs: Path,
        installed_at: str,
        merge_strategy: str,
        stub: bool = False,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "file": file_rel,
            "package": package,
            "package_version": package_version,
            "installed_at": installed_at,
            "sha256": self._sha256(file_abs),
            "scf_merge_strategy": self._normalize_merge_strategy(merge_strategy),
        }
        if stub:
            entry["stub"] = True
        return entry

    def _sync_entries_for_files(
        self,
        entries: list[dict[str, Any]],
        files_by_rel: dict[str, Path],
    ) -> None:
        for file_rel, file_abs in files_by_rel.items():
            if not file_rel:
                continue
            sha256 = self._sha256(file_abs)
            related_entries = [
                entry
                for entry in entries
                if str(entry.get("file", "")).strip() == file_rel
            ]
            if not related_entries:
                continue

            uses_shared_merge = any(
                self._normalize_merge_strategy(entry.get("scf_merge_strategy")) == "merge_sections"
                for entry in related_entries
            )
            for entry in related_entries:
                entry["sha256"] = sha256
                if uses_shared_merge:
                    entry["scf_merge_strategy"] = "merge_sections"

    def _entries_allow_shared_merge_sections(self, entries: list[dict[str, Any]]) -> bool:
        owners = {
            str(entry.get("package", "")).strip()
            for entry in entries
            if str(entry.get("package", "")).strip()
        }
        if len(owners) < 2:
            return False
        return all(
            self._normalize_merge_strategy(entry.get("scf_merge_strategy")) == "merge_sections"
            for entry in entries
            if str(entry.get("package", "")).strip()
        )

    # ------------------------------------------------------------------
    # Override management (v3.0)
    # ------------------------------------------------------------------

    def _override_path(self, resource_type: str, name: str) -> Path:
        from_map = {
            "agents": f"{name}.agent.md",
            "prompts": f"{name}.prompt.md",
            "instructions": f"{name}.instructions.md",
            "skills": f"{name}.skill.md",
        }
        filename = from_map.get(resource_type)
        if filename is None:
            raise ValueError(f"Tipo risorsa non supportato: {resource_type}")
        return self._github_root / "overrides" / resource_type / filename

    def write_override(
        self,
        resource_type: str,
        name: str,
        content: str,
    ) -> Path:
        """Scrive un override workspace e registra l'entry nel manifest.

        Lancia ``ValueError`` se ``resource_type`` non e' supportato.
        Lancia ``OSError`` se la scrittura fallisce.
        """
        target = self._override_path(resource_type, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        rel = target.relative_to(self._github_root).as_posix()
        sha = _sha256_text(content)
        entries = self.load()
        entries = [e for e in entries if e.get("file") != rel]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entries.append({
            "file": rel,
            "package": "__workspace_override__",
            "package_version": "0.0.0",
            "installed_at": now,
            "sha256": sha,
            "scf_merge_strategy": "single_owner",
            "scf_owner": "__workspace_override__",
            "override_type": resource_type,
            "override_name": name,
        })
        self.save(entries)
        return target

    def drop_override(self, resource_type: str, name: str) -> bool:
        """Rimuove un override workspace e relativa entry manifest.

        Ritorna ``True`` se il file e' stato rimosso, ``False`` se assente.
        """
        target = self._override_path(resource_type, name)
        rel = target.relative_to(self._github_root).as_posix()
        existed = target.is_file()
        if existed:
            try:
                target.unlink()
            except OSError as exc:
                _log.warning("Impossibile rimuovere override %s: %s", target, exc)
                raise
        entries = self.load()
        new_entries = [e for e in entries if e.get("file") != rel]
        if len(new_entries) != len(entries):
            self.save(new_entries)
        return existed
