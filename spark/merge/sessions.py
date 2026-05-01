"""Manual merge session manager — estratto da spark-framework-engine.py durante Fase 0.

Persistenza atomica delle sessioni di merge manuale sotto
``.github/runtime/merge-sessions/`` con scadenza TTL.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from spark.core.utils import _format_utc_timestamp, _parse_utc_timestamp, _utc_now

_log: logging.Logger = logging.getLogger("spark-framework-engine")


class MergeSessionManager:
    """Manage manual merge sessions persisted under .github/runtime/merge-sessions/."""

    SESSION_TTL_HOURS: int = 24

    def __init__(self, sessions_root: Path) -> None:
        self._sessions_root = sessions_root

    def create_session(
        self,
        package_id: str,
        package_version: str,
        files: list[dict[str, Any]],
        conflict_mode: str = "manual",
    ) -> dict[str, Any]:
        """Create and persist a new active manual merge session."""
        created_at = _utc_now()
        expires_at = created_at + timedelta(hours=self.SESSION_TTL_HOURS)
        payload: dict[str, Any] = {
            "session_id": str(uuid.uuid4()),
            "package": package_id,
            "package_version": package_version,
            "conflict_mode": conflict_mode,
            "status": "active",
            "created_at": _format_utc_timestamp(created_at),
            "expires_at": _format_utc_timestamp(expires_at),
            "files": [self._normalize_session_file_entry(file_entry) for file_entry in files],
        }
        self._write_session(payload)
        return payload

    def load_session(self, session_id: str) -> dict[str, Any] | None:
        """Return a persisted session payload or None when unavailable."""
        session_path = self._session_path(session_id)
        if session_path is None or not session_path.is_file():
            return None
        try:
            raw = json.loads(session_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _log.warning("Cannot read merge session %s: %s", session_id, exc)
            return None
        return self._normalize_session_payload(raw) if isinstance(raw, dict) else None

    def load_active_session(self, session_id: str) -> dict[str, Any] | None:
        """Return an active session, expiring it automatically when overdue."""
        session = self.load_session(session_id)
        if session is None:
            return None
        if str(session.get("status", "")).strip() != "active":
            return session

        expires_at = _parse_utc_timestamp(str(session.get("expires_at", "")).strip())
        if expires_at is not None and expires_at <= _utc_now():
            expired_session = dict(session)
            expired_session["status"] = "expired"
            self._write_session(expired_session)
            return expired_session
        return session

    def mark_finalized(self, session_id: str) -> dict[str, Any] | None:
        """Mark a session as finalized and persist the updated payload."""
        return self.mark_status(session_id, "finalized")

    def mark_status(
        self,
        session_id: str,
        status: str,
        session: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Update the persisted status for a merge session."""
        current = self.load_session(session_id) if session is None else self._normalize_session_payload(session)
        if current is None:
            return None
        current["status"] = status
        self._write_session(current)
        return current

    def save_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist a normalized session payload and return the stored result."""
        normalized = self._normalize_session_payload(payload)
        self._write_session(normalized)
        return normalized

    def cleanup_expired_sessions(self) -> list[str]:
        """Mark overdue active sessions as expired and return their ids."""
        if not self._sessions_root.is_dir():
            return []

        expired: list[str] = []
        for session_file in sorted(self._sessions_root.glob("*.json")):
            session_id = session_file.stem
            session = self.load_session(session_id)
            if session is None:
                continue
            if str(session.get("status", "")).strip() != "active":
                continue
            expires_at = _parse_utc_timestamp(str(session.get("expires_at", "")).strip())
            if expires_at is None or expires_at > _utc_now():
                continue
            updated = dict(session)
            updated["status"] = "expired"
            self._write_session(updated)
            expired.append(session_id)
        return expired

    @staticmethod
    def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
        """Persist JSON atomically using a .tmp file in the target directory."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, path)
        except OSError:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise

    def _write_session(self, payload: dict[str, Any]) -> None:
        session_id = str(payload.get("session_id", "")).strip()
        session_path = self._session_path(session_id)
        if session_path is None:
            raise ValueError(f"Invalid merge session id: {session_id!r}")
        self._atomic_write_json(session_path, self._normalize_session_payload(payload))

    def _session_path(self, session_id: str) -> Path | None:
        normalized = session_id.strip()
        if not re.fullmatch(r"[A-Za-z0-9-]+", normalized):
            return None
        return self._sessions_root / f"{normalized}.json"

    def _normalize_session_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        normalized["conflict_mode"] = str(payload.get("conflict_mode", "manual")).strip() or "manual"
        normalized["status"] = str(payload.get("status", "active")).strip() or "active"
        files = payload.get("files", [])
        if isinstance(files, list):
            normalized["files"] = [
                self._normalize_session_file_entry(file_entry)
                for file_entry in files
                if isinstance(file_entry, dict)
            ]
        else:
            normalized["files"] = []
        return normalized

    @staticmethod
    def _normalize_session_file_entry(entry: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(entry)
        manifest_rel = str(entry.get("manifest_rel", "")).strip()
        public_file = str(entry.get("file", "")).strip()
        workspace_path = str(entry.get("workspace_path", public_file)).strip()

        if not public_file and manifest_rel:
            public_file = f".github/{manifest_rel}"
        if not workspace_path:
            workspace_path = public_file
        if not manifest_rel and public_file.startswith(".github/"):
            manifest_rel = public_file.removeprefix(".github/")

        proposed_text = entry.get("proposed_text")
        validator_results = entry.get("validator_results")
        marker_text = entry.get("marker_text")

        normalized.update(
            {
                "file": public_file,
                "workspace_path": workspace_path,
                "manifest_rel": manifest_rel,
                "conflict_id": str(entry.get("conflict_id", manifest_rel or public_file)).strip()
                or manifest_rel
                or public_file,
                "base_text": str(entry.get("base_text", "") or ""),
                "ours_text": str(entry.get("ours_text", "") or ""),
                "theirs_text": str(entry.get("theirs_text", "") or ""),
                "proposed_text": proposed_text if isinstance(proposed_text, str) else None,
                "resolution_status": str(entry.get("resolution_status", "pending")).strip()
                or "pending",
                "validator_results": validator_results if isinstance(validator_results, dict) else None,
                "marker_text": marker_text if isinstance(marker_text, str) else None,
            }
        )
        return normalized
