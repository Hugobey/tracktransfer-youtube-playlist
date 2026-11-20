"""Device-code OAuth for YouTube Music playlist changes.

The client id and secret stay on the server. The browser receives a user code
and a Google verification URL. Access and refresh tokens are written to a
private file and are never returned to the client or stored in localStorage.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.errors import AppError

NOT_CONFIGURED = (
    "Playlist creation needs a YouTube Data API OAuth client on the server. "
    "Set YTMUSIC_CLIENT_ID and YTMUSIC_CLIENT_SECRET. "
    "The client type must be TVs and Limited Input devices. "
    "Search and review work without it."
)

TOKEN_FIELDS = (
    "scope",
    "token_type",
    "access_token",
    "refresh_token",
    "expires_at",
    "expires_in",
)


class DeviceFlow(Protocol):
    def get_code(self) -> dict[str, object]:
        """Start a device authorization and return Google's code payload."""

    def token_from_code(self, device_code: str) -> dict[str, object]:
        """Exchange a device code. Pending attempts return an error field."""


class AuthService:
    def __init__(self, data_dir: Path, credentials: DeviceFlow | None) -> None:
        self.data_dir = data_dir
        self.credentials = credentials
        self.sessions = data_dir / "sessions"
        self.pending = data_dir / "pending"
        self.sessions.mkdir(parents=True, exist_ok=True)
        self.pending.mkdir(parents=True, exist_ok=True)

    @property
    def configured(self) -> bool:
        return self.credentials is not None

    def status(self, session_id: str | None) -> dict[str, bool]:
        return {
            "configured": self.configured,
            "authorized": bool(session_id and self.is_authorized(session_id)),
        }

    def is_authorized(self, session_id: str) -> bool:
        path = self._token_path(session_id, required=False)
        if not path.is_file():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return isinstance(payload, dict) and bool(payload.get("refresh_token")) and bool(payload.get("access_token"))

    def require(self, session_id: str) -> None:
        if not self.configured:
            raise AppError("auth_not_configured", NOT_CONFIGURED, 503)
        if not self.is_authorized(session_id):
            raise AppError("auth_required", "Connect YouTube Music before creating a playlist.", 401)

    def token_path(self, session_id: str) -> Path:
        self.require(session_id)
        return self._token_path(session_id, required=True)

    def start(self, session_id: str) -> dict[str, object]:
        self._check_id(session_id)
        if not self.configured or self.credentials is None:
            raise AppError("auth_not_configured", NOT_CONFIGURED, 503)
        if self.is_authorized(session_id):
            return {
                "status": "authorized",
                "verification_url": None,
                "user_code": None,
                "interval": 5,
                "expires_in": 0,
            }
        try:
            code = self.credentials.get_code()
        except Exception as exc:
            raise AppError("auth_failed", _oauth_message(exc), 400) from exc
        device_code = str(code.get("device_code") or "")
        user_code = str(code.get("user_code") or "")
        verification = str(code.get("verification_url") or "https://www.google.com/device")
        if not device_code or not user_code:
            raise AppError("auth_failed", "YouTube Music did not return a sign-in code.", 502)
        expires_in = _positive_int(code.get("expires_in"), 1800)
        interval = _positive_int(code.get("interval"), 5)
        pending = {
            "device_code": device_code,
            "expires_at": int(time.time()) + expires_in,
            "interval": interval,
        }
        self._write_json(self._pending_path(session_id), pending)
        url = verification
        if "user_code=" not in verification:
            joiner = "&" if "?" in verification else "?"
            url = f"{verification}{joiner}user_code={user_code}"
        return {
            "status": "pending",
            "verification_url": url,
            "user_code": user_code,
            "interval": interval,
            "expires_in": expires_in,
        }

    def poll(self, session_id: str) -> dict[str, object]:
        self._check_id(session_id)
        if not self.configured or self.credentials is None:
            raise AppError("auth_not_configured", NOT_CONFIGURED, 503)
        if self.is_authorized(session_id):
            return {"status": "authorized", "interval": 5}
        path = self._pending_path(session_id)
        if not path.is_file():
            raise AppError("auth_required", "Start the YouTube Music connection first.", 401)
        pending = json.loads(path.read_text(encoding="utf-8"))
        if int(time.time()) >= int(pending.get("expires_at") or 0):
            path.unlink(missing_ok=True)
            return {"status": "expired", "interval": 5}
        try:
            raw = self.credentials.token_from_code(str(pending["device_code"]))
        except Exception as exc:
            raise AppError("auth_failed", _oauth_message(exc), 400) from exc
        if not isinstance(raw, dict) or "access_token" not in raw:
            error = str((raw or {}).get("error") or "authorization_pending") if isinstance(raw, dict) else "authorization_pending"
            interval = int(pending.get("interval") or 5)
            if error in {"authorization_pending", "slow_down"}:
                return {"status": "pending", "interval": interval + (5 if error == "slow_down" else 0)}
            if error in {"expired_token", "expired"}:
                path.unlink(missing_ok=True)
                return {"status": "expired", "interval": interval}
            if error == "access_denied":
                path.unlink(missing_ok=True)
                return {"status": "denied", "interval": interval}
            raise AppError("auth_failed", f"YouTube Music sign-in failed ({error}).", 400)
        self._write_token(session_id, raw)
        path.unlink(missing_ok=True)
        return {"status": "authorized", "interval": 5}

    def _write_token(self, session_id: str, raw: dict[str, object]) -> None:
        expires_in = _positive_int(raw.get("expires_in"), 3600)
        payload = {
            "scope": raw.get("scope"),
            "token_type": raw.get("token_type") or "Bearer",
            "access_token": raw.get("access_token"),
            "refresh_token": raw.get("refresh_token"),
            "expires_in": expires_in,
            "expires_at": int(time.time()) + expires_in,
        }
        if not payload["access_token"] or not payload["refresh_token"]:
            raise AppError("auth_failed", "YouTube Music did not return a usable token.", 502)
        path = self._token_path(session_id, required=False)
        self._write_json(path, payload)
        os.chmod(path, 0o600)

    def _token_path(self, session_id: str, *, required: bool) -> Path:
        self._check_id(session_id)
        return self.sessions / f"{session_id}.json"

    def _pending_path(self, session_id: str) -> Path:
        self._check_id(session_id)
        return self.pending / f"{session_id}.json"

    def _check_id(self, session_id: str) -> None:
        try:
            UUID(session_id)
        except (TypeError, ValueError) as exc:
            raise AppError("auth_required", "The sign-in session is not valid. Connect again.", 401) from exc

    def _write_json(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(path)


def _positive_int(value: object, fallback: int) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
    return number if number > 0 else fallback


def _oauth_message(exc: Exception) -> str:
    text = " ".join(str(exc).split())
    lowered = text.lower()
    if "invalid_client" in lowered or "unauthorized_client" in lowered or "client" in lowered:
        return (
            "The server's YouTube Data API client was rejected. "
            "Check YTMUSIC_CLIENT_ID and YTMUSIC_CLIENT_SECRET. "
            "The OAuth client must be a TV and Limited Input devices client with the YouTube Data API enabled."
        )
    return text[:240] or "YouTube Music sign-in failed."
