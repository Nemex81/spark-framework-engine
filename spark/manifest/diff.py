# Modulo manifest/diff — SPARK Framework Engine
# Estratto durante Fase 0 refactoring modulare
"""Workspace diff helpers used during package install/update."""
from __future__ import annotations

from typing import Any

from spark.core.utils import (
    _infer_scf_file_role,
    _normalize_manifest_relative_path,
    _sha256_text,
)
from spark.manifest.manifest import ManifestManager


def _normalize_remote_file_record(
    package_id: str,
    version: str,
    remote_file: dict[str, Any],
) -> dict[str, Any] | None:
    """Normalize one incoming package file record for diff classification."""
    raw_path = str(remote_file.get("path", remote_file.get("file", ""))).strip()
    manifest_rel = _normalize_manifest_relative_path(raw_path)
    if manifest_rel is None:
        return None

    incoming_sha256 = str(remote_file.get("sha256", "")).strip()
    if not incoming_sha256 and isinstance(remote_file.get("content"), str):
        incoming_sha256 = _sha256_text(remote_file["content"])

    public_file = f".github/{manifest_rel}"
    return {
        "file": public_file,
        "manifest_rel": manifest_rel,
        "package": package_id,
        "package_version": version,
        "scf_owner": str(remote_file.get("scf_owner", package_id)).strip() or package_id,
        "scf_version": str(remote_file.get("scf_version", version)).strip() or version,
        "scf_file_role": str(
            remote_file.get("scf_file_role", _infer_scf_file_role(manifest_rel))
        ).strip()
        or _infer_scf_file_role(manifest_rel),
        "scf_merge_strategy": str(remote_file.get("scf_merge_strategy", "replace")).strip()
        or "replace",
        "scf_merge_priority": int(remote_file.get("scf_merge_priority", 0) or 0),
        "scf_protected": bool(remote_file.get("scf_protected", False)),
        "incoming_sha256": incoming_sha256,
    }


def _scf_diff_workspace(
    package_id: str,
    version: str,
    remote_files: list[dict[str, Any]],
    manifest: ManifestManager,
) -> list[dict[str, Any]]:
    """Classify incoming package files against the current workspace state."""
    diff_records: list[dict[str, Any]] = []
    for remote_file in remote_files:
        normalized_record = _normalize_remote_file_record(package_id, version, remote_file)
        if normalized_record is None:
            continue

        manifest_rel = str(normalized_record["manifest_rel"])
        file_abs = manifest._github_root / manifest_rel
        exists = file_abs.is_file()
        current_sha256 = manifest._sha256(file_abs) if exists else ""
        incoming_sha256 = str(normalized_record.get("incoming_sha256", ""))
        tracked_state = manifest.is_user_modified(manifest_rel) if exists else None

        if not exists:
            status = "new"
        elif incoming_sha256 and current_sha256 == incoming_sha256:
            status = "unchanged"
        elif tracked_state is False:
            status = "updated_clean"
        else:
            status = "updated_user_modified"

        diff_records.append(
            {
                **normalized_record,
                "status": status,
                "exists": exists,
                "tracked": tracked_state is not None,
                "user_modified": tracked_state is True,
                "current_sha256": current_sha256,
            }
        )

    return diff_records
