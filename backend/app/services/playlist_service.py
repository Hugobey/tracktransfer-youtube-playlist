"""Create one playlist and add tracks in CSV order.

A failed track stops the walk so later tracks are not appended ahead of it.
Retry continues from that track. Skipping the failed track is explicit.
Already added positions are not sent again. The playlist is not created twice.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.errors import AppError
from app.models.schemas import PlaylistItemOut, PlaylistJobOut, PlaylistTrackIn

MAX_TRACKS = 1000
VIDEO_ID = r"^[A-Za-z0-9_-]{6,32}$"


class PlaylistGateway(Protocol):
    def create_playlist(self, title: str, description: str, privacy: str) -> str:
        """Create an empty playlist and return its id."""

    def add_items(self, playlist_id: str, video_ids: list[str]) -> None:
        """Append video ids, including repeats when the CSV contains them."""


class Authorizer(Protocol):
    def require(self, session_id: str) -> None:
        """Raise when playlist changes are not allowed for this session."""


@dataclass
class JobItem:
    track_id: str
    position: int
    video_id: str
    title: str
    artist: str
    status: str = "pending"
    error: str | None = None


@dataclass
class Job:
    id: str
    session_id: str
    title: str
    description: str
    privacy: str
    playlist_id: str | None = None
    url: str | None = None
    items: list[JobItem] = field(default_factory=list)
    error: str | None = None
    created_at: str = ""


class PlaylistService:
    def __init__(
        self,
        data_dir: Path,
        authorizer: Authorizer,
        gateway_for: Callable[[str], PlaylistGateway],
        *,
        chunk_size: int = 25,
    ) -> None:
        self.jobs_dir = data_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.authorizer = authorizer
        self.gateway_for = gateway_for
        self.chunk_size = chunk_size

    def create(
        self,
        session_id: str,
        job_id: str,
        title: str,
        description: str,
        privacy: str,
        tracks: list[PlaylistTrackIn],
    ) -> PlaylistJobOut:
        self.authorizer.require(session_id)
        self._check_id(job_id, "job_id")
        cleaned_title = " ".join(title.split())
        if not cleaned_title:
            raise AppError("invalid_playlist", "Enter a playlist name.")
        if len(cleaned_title) > 150:
            raise AppError("invalid_playlist", "The playlist name is longer than 150 characters.")
        if len(description) > 5000:
            raise AppError("invalid_playlist", "The description is too long.")
        if privacy not in {"PRIVATE", "PUBLIC", "UNLISTED"}:
            raise AppError("invalid_playlist", "Privacy must be private, unlisted, or public.")
        existing = self._load(job_id)
        if existing and existing.session_id != session_id:
            raise AppError("not_found", "No playlist job with that id.", 404)
        if existing and existing.playlist_id:
            return self._public(self._add_next(existing, set()))
        items = _validate_tracks(tracks)
        job = existing or Job(
            id=job_id,
            session_id=session_id,
            title=cleaned_title,
            description=description.strip(),
            privacy=privacy,
            items=items,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        if not job.items:
            job.items = items
        try:
            playlist_id = self.gateway_for(session_id).create_playlist(job.title, job.description, job.privacy)
        except AppError as exc:
            job.error = exc.message
            self._save(job)
            raise
        job.playlist_id = playlist_id
        job.url = f"https://music.youtube.com/playlist?list={playlist_id}"
        job.error = None
        self._save(job)
        return self._public(self._add_next(job, set()))

    def add(self, session_id: str, job_id: str, skip_track_ids: list[str]) -> PlaylistJobOut:
        job = self._owned(session_id, job_id)
        if not job.playlist_id:
            raise AppError("playlist_missing", "The playlist was not created. Start the transfer again.", 409)
        return self._public(self._add_next(job, set(skip_track_ids)))

    def get(self, session_id: str, job_id: str) -> PlaylistJobOut:
        return self._public(self._owned(session_id, job_id))

    def _owned(self, session_id: str, job_id: str) -> Job:
        self.authorizer.require(session_id)
        self._check_id(job_id, "job_id")
        job = self._load(job_id)
        if job is None or job.session_id != session_id:
            raise AppError("not_found", "No playlist job with that id.", 404)
        return job

    def _add_next(self, job: Job, skip_track_ids: set[str]) -> Job:
        if not job.playlist_id:
            self._save(job)
            return job
        for item in job.items:
            if item.track_id in skip_track_ids and item.status in {"pending", "failed"}:
                item.status = "skipped"
                item.error = None
        pending = [item for item in job.items if item.status in {"pending", "failed"}]
        if not pending:
            self._save(job)
            return job
        gateway = self.gateway_for(job.session_id)
        window = pending[: self.chunk_size]
        self._add_window(gateway, job.playlist_id, window)
        self._save(job)
        return job

    def _add_window(self, gateway: PlaylistGateway, playlist_id: str, window: list[JobItem]) -> None:
        try:
            gateway.add_items(playlist_id, [item.video_id for item in window])
        except AppError as exc:
            if len(window) == 1:
                window[0].status = "failed"
                window[0].error = _item_error(window[0], exc.message)
                return
            for item in window:
                try:
                    gateway.add_items(playlist_id, [item.video_id])
                except AppError as one:
                    item.status = "failed"
                    item.error = _item_error(item, one.message)
                    return
                item.status = "added"
                item.error = None
            return
        for item in window:
            item.status = "added"
            item.error = None

    def _load(self, job_id: str) -> Job | None:
        path = self._path(job_id)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = [JobItem(**item) for item in payload.get("items", [])]
        return Job(
            id=payload["id"],
            session_id=payload["session_id"],
            title=payload["title"],
            description=payload.get("description") or "",
            privacy=payload.get("privacy") or "PRIVATE",
            playlist_id=payload.get("playlist_id"),
            url=payload.get("url"),
            items=items,
            error=payload.get("error"),
            created_at=payload.get("created_at") or "",
        )

    def _save(self, job: Job) -> None:
        path = self._path(job.id)
        payload = {
            "id": job.id,
            "session_id": job.session_id,
            "title": job.title,
            "description": job.description,
            "privacy": job.privacy,
            "playlist_id": job.playlist_id,
            "url": job.url,
            "error": job.error,
            "created_at": job.created_at,
            "items": [item.__dict__ for item in job.items],
        }
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(path)

    def _path(self, job_id: str) -> Path:
        self._check_id(job_id, "job_id")
        return self.jobs_dir / f"{job_id}.json"

    def _public(self, job: Job) -> PlaylistJobOut:
        counts = {"added": 0, "failed": 0, "pending": 0, "skipped": 0}
        items: list[PlaylistItemOut] = []
        for item in job.items:
            counts[item.status] = counts.get(item.status, 0) + 1
            items.append(
                PlaylistItemOut(
                    track_id=item.track_id,
                    position=item.position,
                    video_id=item.video_id,
                    title=item.title,
                    artist=item.artist,
                    status=item.status,  # type: ignore[arg-type]
                    error=item.error,
                )
            )
        return PlaylistJobOut(
            job_id=job.id,
            status=_job_status(job, counts),
            title=job.title,
            description=job.description,
            privacy=job.privacy,  # type: ignore[arg-type]
            playlist_id=job.playlist_id,
            url=job.url,
            added=counts["added"],
            failed=counts["failed"],
            pending=counts["pending"],
            skipped=counts["skipped"],
            track_count=len(job.items),
            items=items,
            error=job.error,
        )

    def _check_id(self, value: str, label: str) -> None:
        try:
            UUID(value)
        except (TypeError, ValueError) as exc:
            raise AppError("invalid_request", f"{label} is not a valid id.", 400) from exc


def _validate_tracks(tracks: list[PlaylistTrackIn]) -> list[JobItem]:
    if not tracks:
        raise AppError("invalid_playlist", "Select at least one track.")
    if len(tracks) > MAX_TRACKS:
        raise AppError("invalid_playlist", f"A transfer can include at most {MAX_TRACKS} tracks.")
    seen: set[str] = set()
    ordered = sorted(enumerate(tracks), key=lambda pair: (pair[1].position, pair[0]))
    items: list[JobItem] = []
    pattern = re.compile(VIDEO_ID)
    for _, track in ordered:
        if track.track_id in seen:
            raise AppError("invalid_playlist", "Each selected track must appear once.")
        seen.add(track.track_id)
        if not pattern.fullmatch(track.video_id):
            raise AppError(
                "invalid_playlist",
                f"Position {track.position} has a video id YouTube Music will not accept.",
            )
        items.append(
            JobItem(
                track_id=track.track_id,
                position=track.position,
                video_id=track.video_id,
                title=track.title.strip(),
                artist=track.artist.strip(),
            )
        )
    return items


def _job_status(job: Job, counts: dict[str, int]) -> str:
    if not job.playlist_id:
        return "failed"
    if counts["pending"] and counts["failed"]:
        return "blocked"
    if counts["pending"]:
        return "adding"
    if counts["failed"]:
        return "partial"
    if counts["added"]:
        return "complete"
    return "failed"


def _item_error(item: JobItem, message: str) -> str:
    label = " - ".join(part for part in (item.artist, item.title) if part)
    prefix = f"Position {item.position}"
    if label:
        prefix = f"{prefix} ({label})"
    return f"{prefix}: {message}"
