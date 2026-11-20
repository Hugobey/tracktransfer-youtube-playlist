"""Build YouTube Music search queries from exporter metadata.

Version words already present on the title are kept. Original Mix, Extended
Mix, and Official Audio are not appended unless the source title says so.
"""

from __future__ import annotations

from app.models.schemas import TrackQuery
from app.services.versions import detect_version, strip_version


def build_queries(track: TrackQuery) -> list[str]:
    artist = _artist(track)
    title = " ".join((track.track_name or "").split())
    queries: list[str] = []

    def add(value: str) -> None:
        cleaned = " ".join(value.split()).strip(" -")
        if not cleaned:
            return
        if cleaned.casefold() in {item.casefold() for item in queries}:
            return
        queries.append(cleaned)

    if artist and title:
        add(f"{artist} - {title}")
    elif title:
        add(title)

    info = detect_version(title)
    base = " ".join(strip_version(title).split())
    if artist and base and base.casefold() != title.casefold():
        if info.phrase and info.kind not in {None, "original"}:
            add(f"{artist} - {base} {info.phrase}")
        else:
            add(f"{artist} - {base}")
    elif artist and not title:
        add(artist)

    return queries[:3]


def _artist(track: TrackQuery) -> str:
    primary = " ".join((track.artist or "").split())
    if primary:
        return primary
    artists = track.artists or ""
    first = artists.split(",")[0].strip()
    return " ".join(first.split())
