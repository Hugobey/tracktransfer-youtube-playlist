"""Parse TrackTransfer Spotify exporter CSV files.

The column set is the one written by Desktop/PROJECTS/tracktransfer
(`CSV_COLUMNS` in src/shared/types.ts). This module does not import that
project and does not accept a different schema.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from app.errors import AppError

CSV_COLUMNS: tuple[str, ...] = (
    "position",
    "track_name",
    "artist",
    "artists",
    "album",
    "duration",
    "duration_ms",
    "date_added",
    "spotify_track_id",
    "spotify_url",
    "explicit",
)

EXPECTED_HEADER = ",".join(CSV_COLUMNS)


@dataclass(frozen=True)
class ParsedTrack:
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
    issues: tuple[str, ...]


@dataclass(frozen=True)
class ParsedCsv:
    delimiter: str
    tracks: tuple[ParsedTrack, ...]


def parse_csv(content: str) -> ParsedCsv:
    text = content.lstrip("\ufeff")
    if not text.strip():
        raise AppError("invalid_csv", "The file is empty.")
    if "\x00" in text:
        raise AppError("invalid_csv", "The file is not a CSV export.")

    sample = text.lstrip()
    first_line = sample.splitlines()[0] if sample.splitlines() else ""
    delimiter = _delimiter(first_line)
    reader = csv.DictReader(io.StringIO(sample), delimiter=delimiter, skipinitialspace=False)
    if reader.fieldnames is None:
        raise AppError("invalid_csv", "The file has no header row.")

    fieldnames = [name.strip() if name else "" for name in reader.fieldnames]
    missing = [column for column in CSV_COLUMNS if column not in fieldnames]
    if missing:
        raise AppError(
            "invalid_csv",
            "This CSV does not match a TrackTransfer export. "
            f"Expected header: {EXPECTED_HEADER}. Missing: {', '.join(missing)}.",
        )

    raw_rows: list[dict[str, str]] = []
    for raw in reader:
        if raw is None:
            continue
        cleaned = {key: (value if value is not None else "") for key, value in raw.items() if key}
        if not any(str(value).strip() for value in cleaned.values()):
            continue
        raw_rows.append({key: cleaned.get(key, "") or "" for key in CSV_COLUMNS})

    if not raw_rows:
        raise AppError("empty_csv", "The file has the TrackTransfer header but no tracks.")

    indexed: list[tuple[int, int, ParsedTrack]] = []
    for index, row in enumerate(raw_rows):
        position = _position(row["position"], index + 1)
        track_name = row["track_name"].strip()
        artist = row["artist"].strip()
        artists = row["artists"].strip()
        album = row["album"].strip()
        duration = row["duration"].strip()
        duration_ms = _milliseconds(row["duration_ms"])
        duration_seconds = round(duration_ms / 1000) if duration_ms is not None else _clock_seconds(duration)
        issues: list[str] = []
        if not track_name:
            issues.append("missing_title")
        if not artist and not artists:
            issues.append("missing_artist")
        if duration_seconds is None:
            issues.append("missing_duration")
        track = ParsedTrack(
            id=f"p{position}-{index}",
            position=position,
            track_name=track_name,
            artist=artist,
            artists=artists,
            album=album,
            duration=duration,
            duration_ms=duration_ms,
            duration_seconds=duration_seconds,
            date_added=row["date_added"].strip(),
            spotify_track_id=row["spotify_track_id"].strip(),
            spotify_url=row["spotify_url"].strip(),
            explicit=_explicit(row["explicit"]),
            issues=tuple(issues),
        )
        indexed.append((position, index, track))

    indexed.sort(key=lambda item: (item[0], item[1]))
    return ParsedCsv(delimiter=delimiter, tracks=tuple(item[2] for item in indexed))


def _delimiter(header_line: str) -> str:
    if header_line.count(";") > header_line.count(","):
        return ";"
    if "," in header_line:
        return ","
    raise AppError(
        "invalid_csv",
        "The header is not comma or semicolon separated. "
        f"Expected header: {EXPECTED_HEADER}.",
    )


def _position(value: str, fallback: int) -> int:
    text = value.strip()
    if text.isdigit():
        number = int(text)
        if number >= 1:
            return number
    return fallback


def _milliseconds(value: str) -> int | None:
    text = value.strip()
    if not text or not text.isdigit():
        return None
    return int(text)


def _clock_seconds(value: str) -> int | None:
    text = value.strip()
    if not text:
        return None
    parts = text.split(":")
    if not all(part.isdigit() for part in parts):
        return None
    numbers = [int(part) for part in parts]
    if len(numbers) == 2 and numbers[1] < 60:
        return numbers[0] * 60 + numbers[1]
    if len(numbers) == 3 and numbers[1] < 60 and numbers[2] < 60:
        return numbers[0] * 3600 + numbers[1] * 60 + numbers[2]
    return None


def _explicit(value: str) -> bool | None:
    text = value.strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None
