"""REST routes for CSV import, search, sign-in, and playlist transfer."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response

from app.errors import AppError
from app.models.schemas import (
    AuthPollOut,
    AuthStartOut,
    AuthStatusOut,
    CsvParseRequest,
    CsvParseResponse,
    ImportedTrack,
    PlaylistAddRequest,
    PlaylistCreateRequest,
    PlaylistJobOut,
    SearchBatchRequest,
    SearchBatchResponse,
    SearchRequest,
    TrackMatchOut,
)
from app.services.container import Services, get_services
from app.services.csv_service import parse_csv

router = APIRouter()
COOKIE = "tt_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 14


def _services(services: Services = Depends(get_services)) -> Services:
    return services


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/csv/parse", response_model=CsvParseResponse)
def parse_csv_route(body: CsvParseRequest, services: Services = Depends(_services)) -> CsvParseResponse:
    if len(body.content.encode("utf-8")) > services.settings.max_csv_bytes:
        raise AppError("csv_too_large", "That CSV is larger than 2 MB.", 413)
    parsed = parse_csv(body.content)
    filename = Path(body.filename).name if body.filename.strip() else "playlist.csv"
    return CsvParseResponse(
        filename=filename,
        delimiter=parsed.delimiter,
        track_count=len(parsed.tracks),
        tracks=[
            ImportedTrack(
                id=track.id,
                position=track.position,
                track_name=track.track_name,
                artist=track.artist,
                artists=track.artists,
                album=track.album,
                duration=track.duration,
                duration_ms=track.duration_ms,
                duration_seconds=track.duration_seconds,
                date_added=track.date_added,
                spotify_track_id=track.spotify_track_id,
                spotify_url=track.spotify_url,
                explicit=track.explicit,
                issues=list(track.issues),
            )
            for track in parsed.tracks
        ],
    )


@router.post("/api/search", response_model=TrackMatchOut)
def search_one(body: SearchRequest, services: Services = Depends(_services)) -> TrackMatchOut:
    return services.search.match_query(body.track, body.query)


@router.post("/api/search/batch", response_model=SearchBatchResponse)
async def search_batch(body: SearchBatchRequest, services: Services = Depends(_services)) -> SearchBatchResponse:
    if len(body.tracks) > services.settings.batch_limit:
        raise AppError(
            "batch_too_large",
            f"Send at most {services.settings.batch_limit} tracks at a time.",
            400,
        )
    results = await services.search.match_many(body.tracks)
    return SearchBatchResponse(results=results)


@router.get("/api/auth/status", response_model=AuthStatusOut)
def auth_status(request: Request, services: Services = Depends(_services)) -> AuthStatusOut:
    return AuthStatusOut(**services.auth.status(_optional_session(request)))


@router.post("/api/auth/start", response_model=AuthStartOut)
def auth_start(request: Request, response: Response, services: Services = Depends(_services)) -> AuthStartOut:
    session_id = _optional_session(request) or str(uuid4())
    payload = services.auth.start(session_id)
    _set_cookie(response, session_id)
    return AuthStartOut(**payload)


@router.post("/api/auth/poll", response_model=AuthPollOut)
def auth_poll(request: Request, services: Services = Depends(_services)) -> AuthPollOut:
    return AuthPollOut(**services.auth.poll(_required_session(request)))


@router.post("/api/playlist/create", response_model=PlaylistJobOut)
def playlist_create(body: PlaylistCreateRequest, request: Request, services: Services = Depends(_services)) -> PlaylistJobOut:
    return services.playlists.create(
        _required_session(request),
        body.job_id,
        body.title,
        body.description,
        body.privacy,
        body.tracks,
    )


@router.post("/api/playlist/add-tracks", response_model=PlaylistJobOut)
def playlist_add(body: PlaylistAddRequest, request: Request, services: Services = Depends(_services)) -> PlaylistJobOut:
    return services.playlists.add(_required_session(request), body.job_id, body.skip_track_ids)


@router.get("/api/playlist/status/{job_id}", response_model=PlaylistJobOut)
def playlist_status(job_id: str, request: Request, services: Services = Depends(_services)) -> PlaylistJobOut:
    return services.playlists.get(_required_session(request), job_id)


def _optional_session(request: Request) -> str | None:
    raw = request.cookies.get(COOKIE)
    if not raw:
        return None
    try:
        UUID(raw)
    except ValueError:
        return None
    return raw


def _required_session(request: Request) -> str:
    session_id = _optional_session(request)
    if not session_id:
        raise AppError("auth_required", "Connect YouTube Music before creating a playlist.", 401)
    return session_id


def _set_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        COOKIE,
        session_id,
        httponly=True,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
        path="/",
    )
