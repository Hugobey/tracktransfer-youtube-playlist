from uuid import uuid4

import pytest

from app.errors import AppError
from app.models.schemas import PlaylistTrackIn
from app.services.playlist_service import PlaylistService


class Auth:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok

    def require(self, session_id: str) -> None:
        if not self.ok:
            raise AppError("auth_required", "Connect YouTube Music before creating a playlist.", 401)


class Gateway:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.added: list[list[str]] = []
        self.fail_ids = {"badvideo1"}
        self.fail_create = False

    def create_playlist(self, title: str, description: str, privacy: str) -> str:
        if self.fail_create:
            raise AppError("playlist_create_failed", "YouTube Music rejected the playlist name.", 502)
        playlist_id = f"PL{len(self.created) + 1}"
        self.created.append(playlist_id)
        return playlist_id

    def add_items(self, playlist_id: str, video_ids: list[str]) -> None:
        if any(video_id in self.fail_ids for video_id in video_ids):
            raise AppError("playlist_add_failed", "YouTube Music rejected a video id.", 502)
        self.added.append(list(video_ids))


def tracks(*video_ids: str) -> list[PlaylistTrackIn]:
    return [
        PlaylistTrackIn(track_id=f"p{index + 1}-0", position=index + 1, video_id=video_id, title=f"T{index + 1}", artist="Ada")
        for index, video_id in enumerate(video_ids)
    ]


def service(tmp_path, gateway: Gateway | None = None, chunk: int = 25) -> tuple[PlaylistService, Gateway]:
    gateway = gateway or Gateway()
    playlist = PlaylistService(tmp_path, Auth(), lambda _session: gateway, chunk_size=chunk)
    return playlist, gateway


def test_create_keeps_order_and_duplicate_songs(tmp_path) -> None:
    playlist, gateway = service(tmp_path)
    session = str(uuid4())
    job_id = str(uuid4())
    result = playlist.create(session, job_id, "Night — TrackTransfer", "Notes", "PRIVATE", tracks("aaaaaaaaaaa", "bbbbbbbbbbb", "aaaaaaaaaaa"))
    assert result.status == "complete"
    assert result.added == 3
    assert result.failed == 0
    assert gateway.created == ["PL1"]
    assert gateway.added == [["aaaaaaaaaaa", "bbbbbbbbbbb", "aaaaaaaaaaa"]]
    assert result.url == "https://music.youtube.com/playlist?list=PL1"


def test_partial_failure_does_not_recreate_and_retry_skips_added(tmp_path) -> None:
    gateway = Gateway()
    playlist, gateway = service(tmp_path, gateway, chunk=10)
    session = str(uuid4())
    job_id = str(uuid4())
    first = playlist.create(
        session,
        job_id,
        "Night",
        "",
        "PRIVATE",
        tracks("aaaaaaaaaaa", "badvideo1", "ccccccccccc"),
    )
    assert first.status == "blocked"
    assert first.added == 1
    assert first.failed == 1
    assert first.pending == 1
    assert gateway.created == ["PL1"]
    assert first.items[1].error
    assert "Position 2" in first.items[1].error
    assert gateway.added == [["aaaaaaaaaaa"]]

    gateway.fail_ids.clear()
    second = playlist.add(session, job_id, [])
    assert second.status == "complete"
    assert second.added == 3
    assert gateway.created == ["PL1"]
    assert gateway.added == [["aaaaaaaaaaa"], ["badvideo1", "ccccccccccc"]]
    third = playlist.create(session, job_id, "Night", "", "PRIVATE", tracks("aaaaaaaaaaa"))
    assert third.playlist_id == "PL1"
    assert gateway.created == ["PL1"]


def test_skip_failed_track_continues_in_order(tmp_path) -> None:
    gateway = Gateway()
    playlist, gateway = service(tmp_path, gateway)
    session = str(uuid4())
    job_id = str(uuid4())
    playlist.create(session, job_id, "Night", "", "PRIVATE", tracks("aaaaaaaaaaa", "badvideo1", "ccccccccccc"))
    result = playlist.add(session, job_id, ["p2-0"])
    assert result.status == "complete"
    assert result.skipped == 1
    assert result.added == 2
    assert gateway.added[-1] == ["ccccccccccc"]
    again = playlist.add(session, job_id, [])
    assert again.added == 2
    assert gateway.added == [["aaaaaaaaaaa"], ["ccccccccccc"]]


def test_create_failure_can_be_retried_without_a_playlist_id(tmp_path) -> None:
    gateway = Gateway()
    gateway.fail_create = True
    playlist, gateway = service(tmp_path, gateway)
    session = str(uuid4())
    job_id = str(uuid4())
    with pytest.raises(AppError) as caught:
        playlist.create(session, job_id, "Night", "", "PRIVATE", tracks("aaaaaaaaaaa"))
    assert caught.value.code == "playlist_create_failed"
    assert gateway.created == []
    gateway.fail_create = False
    result = playlist.create(session, job_id, "Night", "", "PRIVATE", tracks("aaaaaaaaaaa"))
    assert result.status == "complete"
    assert gateway.created == ["PL1"]


def test_authentication_failure_and_invalid_id(tmp_path) -> None:
    playlist = PlaylistService(tmp_path, Auth(ok=False), lambda _session: Gateway())
    with pytest.raises(AppError) as caught:
        playlist.create(str(uuid4()), str(uuid4()), "Night", "", "PRIVATE", tracks("aaaaaaaaaaa"))
    assert caught.value.code == "auth_required"
    playlist_ok, _gateway = service(tmp_path)
    with pytest.raises(AppError) as invalid:
        playlist_ok.create(str(uuid4()), str(uuid4()), "Night", "", "PRIVATE", tracks("not valid"))
    assert invalid.value.code == "invalid_playlist"


def test_large_playlist_is_chunked_in_order(tmp_path) -> None:
    playlist, gateway = service(tmp_path, chunk=25)
    session = str(uuid4())
    job_id = str(uuid4())
    video_ids = [f"vid{index:08d}" for index in range(60)]
    first = playlist.create(session, job_id, "Long", "", "PRIVATE", tracks(*video_ids))
    assert first.added == 25
    assert first.pending == 35
    assert first.status == "adding"
    second = playlist.add(session, job_id, [])
    third = playlist.add(session, job_id, [])
    assert third.status == "complete"
    assert third.added == 60
    assert second.added == 50
    flat = [video_id for chunk in gateway.added for video_id in chunk]
    assert flat == video_ids
    assert len(gateway.created) == 1
