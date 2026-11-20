"""Typed request and response bodies shared by the routes and services."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MatchStatus = Literal["high", "likely", "review", "none", "error"]
Privacy = Literal["PRIVATE", "PUBLIC", "UNLISTED"]


class CsvParseRequest(BaseModel):
    filename: str = ""
    content: str


class ImportedTrack(BaseModel):
    id: str
    position: int
    track_name: str
    artist: str
    artists: str
    album: str
    duration: str
    duration_ms: int | None
    duration_seconds: int | None
    date_added: str
    spotify_track_id: str
    spotify_url: str
    explicit: bool | None
    issues: list[str] = Field(default_factory=list)


class CsvParseResponse(BaseModel):
    filename: str
    delimiter: str
    track_count: int
    tracks: list[ImportedTrack]


class TrackQuery(BaseModel):
    id: str
    position: int = 0
    track_name: str = ""
    artist: str = ""
    artists: str = ""
    album: str = ""
    duration_ms: int | None = None
    duration_seconds: int | None = None


class SearchBatchRequest(BaseModel):
    tracks: list[TrackQuery]


class SearchRequest(BaseModel):
    track: TrackQuery
    query: str


class SignalOut(BaseModel):
    artist: float
    title: float
    version: float
    duration: float
    other: float


class CandidateOut(BaseModel):
    video_id: str
    title: str
    artists: list[str]
    album: str | None = None
    duration_seconds: int | None = None
    thumbnail_url: str | None = None
    result_type: str | None = None
    channel: str | None = None
    score: float
    signals: SignalOut
    version: str | None = None
    reasons: list[str] = Field(default_factory=list)


class TrackMatchOut(BaseModel):
    id: str
    queries: list[str]
    status: MatchStatus
    selected_video_id: str | None = None
    candidates: list[CandidateOut] = Field(default_factory=list)
    error: str | None = None


class SearchBatchResponse(BaseModel):
    results: list[TrackMatchOut]


class PlaylistTrackIn(BaseModel):
    track_id: str
    position: int
    video_id: str
    title: str = ""
    artist: str = ""


class PlaylistCreateRequest(BaseModel):
    job_id: str
    title: str
    description: str = ""
    privacy: Privacy = "PRIVATE"
    tracks: list[PlaylistTrackIn]


class PlaylistAddRequest(BaseModel):
    job_id: str
    skip_track_ids: list[str] = Field(default_factory=list)


class PlaylistItemOut(BaseModel):
    track_id: str
    position: int
    video_id: str
    title: str
    artist: str
    status: Literal["pending", "added", "failed", "skipped"]
    error: str | None = None


class PlaylistJobOut(BaseModel):
    job_id: str
    status: Literal["failed", "adding", "blocked", "partial", "complete"]
    title: str
    description: str
    privacy: Privacy
    playlist_id: str | None = None
    url: str | None = None
    added: int
    failed: int
    pending: int
    skipped: int
    track_count: int
    items: list[PlaylistItemOut]
    error: str | None = None


class AuthStartOut(BaseModel):
    status: Literal["pending", "authorized"]
    verification_url: str | None = None
    user_code: str | None = None
    interval: int = 5
    expires_in: int = 0


class AuthPollOut(BaseModel):
    status: Literal["pending", "authorized", "expired", "denied"]
    interval: int = 5


class AuthStatusOut(BaseModel):
    configured: bool
    authorized: bool
