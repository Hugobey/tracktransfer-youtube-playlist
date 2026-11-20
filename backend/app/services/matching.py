"""Rank YouTube Music candidates against one imported track.

Weights are the starting point from the product brief. A mismatched version
cannot become a high-confidence or likely match on the strength of the other
signals. Thresholds are constants so a calibration run can change them in one
place after real searches, not inside the request path.
"""

from __future__ import annotations

from dataclasses import dataclass

from difflib import SequenceMatcher

from app.models.schemas import CandidateOut, SignalOut, TrackMatchOut, TrackQuery
from app.services.versions import (
    VERSION_LABEL,
    detect_version,
    normalize,
    strip_version,
    tokens,
    version_compatibility,
)

# Artist 30, title 30, version 25, duration 10, other metadata 5.
WEIGHT_ARTIST = 0.30
WEIGHT_TITLE = 0.30
WEIGHT_VERSION = 0.25
WEIGHT_DURATION = 0.10
WEIGHT_OTHER = 0.05

HIGH_SCORE = 0.84
HIGH_ARTIST = 0.78
HIGH_TITLE = 0.80
HIGH_VERSION = 0.85
LIKELY_SCORE = 0.72
LIKELY_ARTIST = 0.66
LIKELY_TITLE = 0.70
LIKELY_VERSION = 0.80
REVIEW_SCORE = 0.46
CLOSE_GAP = 0.035
VERSION_CAP = 0.58
VERSION_CAP_BELOW = 0.20


@dataclass(frozen=True)
class CatalogItem:
    video_id: str
    title: str
    artists: tuple[str, ...]
    album: str | None
    duration_seconds: int | None
    thumbnail_url: str | None
    result_type: str | None
    channel: str | None


@dataclass(frozen=True)
class _Scored:
    item: CatalogItem
    score: float
    signals: SignalOut
    version: str | None
    reasons: tuple[str, ...]


def rank_matches(track: TrackQuery, items: list[CatalogItem], *, limit: int = 5) -> TrackMatchOut:
    scored = [_score(track, item) for item in items]
    scored.sort(key=lambda row: row.score, reverse=True)
    unique: list[_Scored] = []
    seen: set[str] = set()
    for row in scored:
        if row.item.video_id in seen:
            continue
        seen.add(row.item.video_id)
        unique.append(row)
    top = unique[:limit]
    status, selected = _decide(track, top)
    return TrackMatchOut(
        id=track.id,
        queries=[],
        status=status,
        selected_video_id=selected,
        candidates=[_candidate(row) for row in top],
    )


def _score(track: TrackQuery, item: CatalogItem) -> _Scored:
    source_version = detect_version(track.track_name).kind
    candidate_version = detect_version(item.title).kind
    artist_score = _artist_similarity(track.artist, track.artists, item.artists)
    title_score = _title_similarity(track.track_name, item.title)
    version_score = version_compatibility(source_version, candidate_version)
    duration_score, delta = _duration_similarity(_source_seconds(track), item.duration_seconds)
    other_score = _other_similarity(track.album, item.album, item.result_type)
    signals = SignalOut(
        artist=round(artist_score, 4),
        title=round(title_score, 4),
        version=round(version_score, 4),
        duration=round(duration_score, 4),
        other=round(other_score, 4),
    )
    score = (
        signals.artist * WEIGHT_ARTIST
        + signals.title * WEIGHT_TITLE
        + signals.version * WEIGHT_VERSION
        + signals.duration * WEIGHT_DURATION
        + signals.other * WEIGHT_OTHER
    )
    if signals.version < VERSION_CAP_BELOW:
        score = min(score, VERSION_CAP)
    reasons = _reasons(source_version, candidate_version, signals, delta)
    return _Scored(
        item=item,
        score=round(score, 4),
        signals=signals,
        version=candidate_version,
        reasons=tuple(reasons),
    )


def _decide(track: TrackQuery, ranked: list[_Scored]) -> tuple[str, str | None]:
    if not ranked:
        return "none", None
    best = ranked[0]
    status = _status(track, best.score, best.signals)
    if status == "high" and len(ranked) > 1:
        gap = best.score - ranked[1].score
        incompatible = version_compatibility(best.version, ranked[1].version) < 0.8
        if gap < CLOSE_GAP and incompatible and ranked[1].score >= LIKELY_SCORE:
            status = "review"
    selected = best.item.video_id if status == "high" else None
    return status, selected


def _status(track: TrackQuery, score: float, signals: SignalOut) -> str:
    if _missing_identity(track):
        return "review" if score >= REVIEW_SCORE else "none"
    if (
        score >= HIGH_SCORE
        and signals.artist >= HIGH_ARTIST
        and signals.title >= HIGH_TITLE
        and signals.version >= HIGH_VERSION
    ):
        return "high"
    if (
        score >= LIKELY_SCORE
        and signals.artist >= LIKELY_ARTIST
        and signals.title >= LIKELY_TITLE
        and signals.version >= LIKELY_VERSION
    ):
        return "likely"
    if score >= REVIEW_SCORE:
        return "review"
    return "none"


def _missing_identity(track: TrackQuery) -> bool:
    return not normalize(track.track_name) or not (normalize(track.artist) or normalize(track.artists))


def _source_seconds(track: TrackQuery) -> int | None:
    if track.duration_seconds is not None:
        return track.duration_seconds
    if track.duration_ms is None:
        return None
    return round(track.duration_ms / 1000)


def _artist_similarity(artist: str, artists: str, candidate_artists: tuple[str, ...]) -> float:
    names = [name for name in _source_artists(artist, artists) if normalize(name)]
    candidates = [name for name in candidate_artists if normalize(name)]
    if not names or not candidates:
        return 0.0
    primary = names[0]
    best = 0.0
    candidate_blob = normalize(" ".join(candidates))
    primary_tokens = tokens(primary)
    for candidate in candidates:
        best = max(best, _ratio(normalize(primary), normalize(candidate)))
        best = max(best, _token_f1(primary_tokens, tokens(candidate)))
    if primary_tokens and all(token in tokens(candidate_blob) for token in primary_tokens):
        best = max(best, 0.95)
    if len(names) == 1:
        return best
    extras = names[1:]
    hits = 0
    for extra in extras:
        extra_norm = normalize(extra)
        if extra_norm and (extra_norm in candidate_blob or _ratio(extra_norm, candidate_blob) >= 0.84):
            hits += 1
    return min(1.0, best * 0.85 + (hits / len(extras)) * 0.15)


def _source_artists(artist: str, artists: str) -> list[str]:
    """Use the exporter's first-artist column before splitting the joined list.

    A single artist such as ``Tyler, The Creator`` is stored in both columns.
    Splitting that on every comma would invent a second artist.
    """
    primary = artist.strip()
    joined = artists.strip()
    if not primary and not joined:
        return []
    if not joined or joined == primary:
        return [primary or joined]
    if primary and joined.startswith(primary + ", "):
        extras = [part.strip() for part in joined[len(primary) + 2 :].split(", ") if part.strip()]
        return [primary, *extras]
    if not primary:
        return [part.strip() for part in joined.split(", ") if part.strip()]
    return [primary]


def _title_similarity(source: str, candidate: str) -> float:
    left = normalize(strip_version(source))
    right = normalize(strip_version(candidate))
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    score = _ratio(left, right)
    if left in right or right in left:
        shorter = min(len(left), len(right))
        longer = max(len(left), len(right))
        if shorter >= 4 and shorter / longer >= 0.55:
            score = max(score, 0.93)
    return score


def _duration_similarity(source: int | None, candidate: int | None) -> tuple[float, int | None]:
    if source is None or candidate is None:
        return 0.6, None
    delta = abs(source - candidate)
    if delta <= 2:
        return 1.0, delta
    if delta <= 5:
        return 0.92, delta
    if delta <= 12:
        return 0.7, delta
    if delta <= 25:
        return 0.35, delta
    if delta <= 45:
        return 0.15, delta
    return 0.0, delta


def _other_similarity(source_album: str, candidate_album: str | None, result_type: str | None) -> float:
    if result_type == "song":
        type_score = 1.0
    elif result_type == "video":
        type_score = 0.55
    else:
        type_score = 0.35
    if source_album.strip() and candidate_album:
        album_score = _ratio(normalize(source_album), normalize(candidate_album))
    else:
        album_score = 0.6
    return type_score * 0.7 + album_score * 0.3


def _reasons(
    source_version: str | None,
    candidate_version: str | None,
    signals: SignalOut,
    delta: int | None,
) -> list[str]:
    notes: list[str] = []
    if signals.version < VERSION_CAP_BELOW and source_version != candidate_version:
        notes.append(
            f"This is {VERSION_LABEL.get(candidate_version, 'a different version')}, "
            f"not {VERSION_LABEL.get(source_version, 'the requested version')}."
        )
    elif signals.artist >= 0.85 and signals.title >= 0.85:
        notes.append("Artist and title agree.")
    if signals.artist < 0.55:
        notes.append("The artist does not match closely.")
    elif signals.title < 0.55:
        notes.append("The title does not match closely.")
    if delta is not None and delta > 15:
        notes.append(f"Duration differs by {delta}s.")
    if not notes and signals.artist >= 0.85 and signals.title >= 0.85:
        notes.append("Artist and title agree.")
    return notes[:3]


def _candidate(row: _Scored) -> CandidateOut:
    item = row.item
    return CandidateOut(
        video_id=item.video_id,
        title=item.title,
        artists=list(item.artists),
        album=item.album,
        duration_seconds=item.duration_seconds,
        thumbnail_url=item.thumbnail_url,
        result_type=item.result_type,
        channel=item.channel,
        score=row.score,
        signals=row.signals,
        version=row.version,
        reasons=list(row.reasons),
    )


def _ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _token_f1(left: list[str], right: list[str]) -> float:
    if not left or not right:
        return 0.0
    from collections import Counter

    shared = sum((Counter(left) & Counter(right)).values())
    if shared == 0:
        return 0.0
    precision = shared / sum(Counter(right).values())
    recall = shared / sum(Counter(left).values())
    return 2 * precision * recall / (precision + recall)
