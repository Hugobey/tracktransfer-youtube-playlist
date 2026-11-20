import json
from uuid import uuid4

import pytest

from app.errors import AppError
from app.services.auth_service import TOKEN_FIELDS, AuthService


class Flow:
    def __init__(self) -> None:
        self.calls = 0

    def get_code(self) -> dict[str, object]:
        return {
            "device_code": "device-secret",
            "user_code": "ABCD-EFGH",
            "verification_url": "https://www.google.com/device",
            "expires_in": 600,
            "interval": 5,
        }

    def token_from_code(self, device_code: str) -> dict[str, object]:
        assert device_code == "device-secret"
        self.calls += 1
        if self.calls == 1:
            return {"error": "authorization_pending"}
        return {
            "access_token": "access-secret",
            "refresh_token": "refresh-secret",
            "scope": "https://www.googleapis.com/auth/youtube",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token_expires_in": 999999,
            "client_secret": "should-not-be-stored",
        }


def test_device_flow_hides_tokens_and_stores_them_on_the_server(tmp_path) -> None:
    auth = AuthService(tmp_path, Flow())
    session_id = str(uuid4())
    started = auth.start(session_id)
    assert started["user_code"] == "ABCD-EFGH"
    assert started["verification_url"] == "https://www.google.com/device?user_code=ABCD-EFGH"
    assert "device_code" not in started
    assert "access_token" not in started
    pending = auth.poll(session_id)
    assert pending["status"] == "pending"
    done = auth.poll(session_id)
    assert done == {"status": "authorized", "interval": 5}
    assert "access_token" not in done
    stored = json.loads((tmp_path / "sessions" / f"{session_id}.json").read_text(encoding="utf-8"))
    assert set(stored) == set(TOKEN_FIELDS)
    assert stored["refresh_token"] == "refresh-secret"
    assert "client_secret" not in stored
    assert "device-secret" not in json.dumps(stored)
    mode = (tmp_path / "sessions" / f"{session_id}.json").stat().st_mode & 0o777
    assert mode == 0o600
    assert auth.is_authorized(session_id)


def test_missing_oauth_client_is_reported(tmp_path) -> None:
    auth = AuthService(tmp_path, None)
    with pytest.raises(AppError) as caught:
        auth.start(str(uuid4()))
    assert caught.value.code == "auth_not_configured"
    assert "YTMUSIC_CLIENT_ID" in caught.value.message
    assert "cookie" not in caught.value.message.lower()
