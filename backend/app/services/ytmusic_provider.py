"""ytmusicapi adapter.

Search uses an unauthenticated client. Playlist changes use the documented
device OAuth token stored on the server. Browser cookies and pasted session
headers are not accepted.
"""

from __future__ import annotations

import threading
from pathlib import Path

from ytmusicapi import OAuthCredentials, YTMusic

from app.errors import AppError
from app.services.matching import CatalogItem


class _Cache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[tuple[str, str], tuple[list[CatalogItem], bool]] = {}

    def get(self, key: tuple[str, str], minimum: int) -> list[CatalogItem] | None:
        with self._lock:
            hit = self._items.get(key)
            if hit is None:
                return None
            rows, exhausted = hit
            if len(rows) >= minimum or exhausted:
                return list(rows[:minimum])
            return None

    def put(self, key: tuple[str, str], rows: list[CatalogItem], requested: int) -> None:
        with self._lock:
            self._items[key] = (list(rows), len(rows) < requested)


class YtMusicProvider:
    def __init__(self, client_id: str = "", client_secret: str = "") -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._cache = _Cache()
        self._pool: list[YTMusic] = []
        self._pool_lock = threading.Lock()

    def search(self, query: str, *, kind: str, limit: int) -> list[CatalogItem]:
        key = (kind, query.casefold())
        cached = self._cache.get(key, limit)
        if cached is not None:
            return cached
        client = self._borrow()
        try:
            raw = client.search(query, filter="songs" if kind == "songs" else "videos", limit=limit)
        except Exception as exc:
            raise AppError("search_failed", _clean(exc)) from exc
        finally:
            self._release(client)
        items = [item for row in raw or [] if (item := parse_catalog_item(row)) is not None]
        self._cache.put(key, items, limit)
        return items

    def create_playlist(self, token_path: Path, title: str, description: str, privacy: str) -> str:
        client = self._authenticated(token_path)
        try:
            result = client.create_playlist(title, description, privacy_status=privacy)
        except Exception as exc:
            raise _playlist_error(exc) from exc
        if isinstance(result, str) and result.strip():
            return result.strip()
        if isinstance(result, dict):
            for field in ("playlistId", "id"):
                value = result.get(field)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            message = result.get("error") or result.get("status") or "YouTube Music did not return a playlist id."
            raise AppError("playlist_create_failed", _clean_text(str(message)), 502)
        raise AppError("playlist_create_failed", "YouTube Music did not return a playlist id.", 502)

    def add_items(self, token_path: Path, playlist_id: str, video_ids: list[str]) -> None:
        if not video_ids:
            return
        client = self._authenticated(token_path)
        try:
            result = client.add_playlist_items(playlist_id, video_ids, duplicates=True)
        except Exception as exc:
            raise _playlist_error(exc) from exc
        if isinstance(result, dict):
            status = str(result.get("status") or "")
            if "SUCCEEDED" in status.upper() or result.get("playlistId"):
                return
            if result.get("error") or "FAIL" in status.upper():
                message = result.get("error") or status or "YouTube Music rejected these tracks."
                raise AppError("playlist_add_failed", _clean_text(str(message)), 502)
            if not status and "error" not in result:
                return
            raise AppError("playlist_add_failed", _clean_text(status or "YouTube Music rejected these tracks."), 502)
        if isinstance(result, str) and "FAIL" in result.upper():
            raise AppError("playlist_add_failed", _clean_text(result), 502)

    def _borrow(self) -> YTMusic:
        with self._pool_lock:
            if self._pool:
                return self._pool.pop()
        try:
            return YTMusic()
        except Exception as exc:
            raise AppError("search_failed", _clean(exc)) from exc

    def _release(self, client: YTMusic) -> None:
        with self._pool_lock:
            if len(self._pool) < 3:
                self._pool.append(client)

    def _authenticated(self, token_path: Path) -> YTMusic:
        if not self.client_id or not self.client_secret:
            raise AppError(
                "auth_not_configured",
                "Playlist creation needs a YouTube Data API OAuth client on the server.",
                503,
            )
        try:
            return YTMusic(
                str(token_path),
                oauth_credentials=OAuthCredentials(self.client_id, self.client_secret),
            )
        except Exception as exc:
            raise AppError(
                "auth_required",
                "YouTube Music declined the saved sign-in. Connect again.",
                401,
            ) from exc


def parse_catalog_item(raw: object) -> CatalogItem | None:
    if not isinstance(raw, dict):
        return None
    video_id = raw.get("videoId")
    if not isinstance(video_id, str) or not video_id.strip():
        return None
    title = raw.get("title") if isinstance(raw.get("title"), str) else ""
    artists: list[str] = []
    raw_artists = raw.get("artists")
    if isinstance(raw_artists, list):
        for artist in raw_artists:
            if isinstance(artist, dict) and isinstance(artist.get("name"), str) and artist["name"].strip():
                artists.append(artist["name"].strip())
            elif isinstance(artist, str) and artist.strip():
                artists.append(artist.strip())
    if not artists and isinstance(raw.get("artist"), str) and raw["artist"].strip():
        artists.append(raw["artist"].strip())
    album = _album(raw.get("album"))
    duration = raw.get("duration_seconds")
    duration_seconds = duration if isinstance(duration, int) else _clock(raw.get("duration"))
    thumbnail = _thumbnail(raw.get("thumbnails"))
    result_type = raw.get("resultType") if isinstance(raw.get("resultType"), str) else None
    channel = raw.get("author") if isinstance(raw.get("author"), str) and raw["author"].strip() else None
    return CatalogItem(
        video_id=video_id.strip(),
        title=title.strip(),
        artists=tuple(artists),
        album=album,
        duration_seconds=duration_seconds,
        thumbnail_url=thumbnail,
        result_type=result_type,
        channel=channel,
    )


def _album(value: object) -> str | None:
    if isinstance(value, dict):
        name = value.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _thumbnail(value: object) -> str | None:
    if not isinstance(value, list) or not value:
        return None
    last = value[-1]
    if isinstance(last, dict) and isinstance(last.get("url"), str) and last["url"].strip():
        return last["url"].strip()
    return None


def _clock(value: object) -> int | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parts = value.strip().split(":")
    if not all(part.isdigit() for part in parts):
        return None
    numbers = [int(part) for part in parts]
    if len(numbers) == 2:
        return numbers[0] * 60 + numbers[1]
    if len(numbers) == 3:
        return numbers[0] * 3600 + numbers[1] * 60 + numbers[2]
    return None


def _playlist_error(exc: Exception) -> AppError:
    text = _clean(exc)
    lowered = text.lower()
    if "authentication" in lowered or "oauth" in lowered or "unauthorized" in lowered:
        return AppError("auth_required", "YouTube Music declined the sign-in. Connect again.", 401)
    return AppError("youtube_music_error", text or "YouTube Music could not update the playlist.", 502)


def _clean(exc: Exception) -> str:
    return _clean_text(str(exc))


def _clean_text(text: str) -> str:
    compact = " ".join(text.split())
    return compact[:240]
