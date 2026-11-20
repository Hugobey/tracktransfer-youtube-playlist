"""Score the matcher against real YouTube Music song searches.

Labels are artist, base title, and version compatibility. They do not use the
ranker's weights. The script searches the public catalog once per query and
does not retry failures, rotate accounts, or change request headers.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models.schemas import TrackQuery
from app.services.matching import CatalogItem
from app.services.search_service import SearchService
from app.services.versions import detect_version, normalize, strip_version, tokens, version_compatibility
from app.services.ytmusic_provider import YtMusicProvider

# Real releases, plus a few titles that should not resolve.
TRACKS: list[tuple[str, str]] = [
    ("Fisher", "Losing It"),
    ("Fisher", "You Little Beauty"),
    ("Fisher", "Just Feels Tight"),
    ("Chris Lake", "Turn Off The Lights"),
    ("Chris Lake", "In The Yuma"),
    ("John Summit", "Where You Are"),
    ("Fred again..", "Marea (we've lost dancing)"),
    ("Fred again..", "adore u"),
    ("Disclosure", "Latch"),
    ("Disclosure", "You & Me"),
    ("Disclosure", "White Noise"),
    ("Bicep", "Glue"),
    ("Bicep", "Apricots"),
    ("Peggy Gou", "(It Goes Like) Nanana"),
    ("Rüfüs Du Sol", "Innerbloom"),
    ("Rüfüs Du Sol", "On My Knees"),
    ("Lane 8", "Road"),
    ("Ben Böhmer", "Beyond Beliefs"),
    ("Nora En Pure", "Come With Me"),
    ("CamelPhat", "Cola"),
    ("Duke Dumont", "Ocean Drive"),
    ("Duke Dumont", "I Got U"),
    ("MK", "17"),
    ("Gorgon City", "Ready For Your Love"),
    ("Purple Disco Machine", "Hypnotized"),
    ("Purple Disco Machine", "Body Funk"),
    ("Dom Dolla", "San Frandisco"),
    ("Dom Dolla", "Miracle Maker"),
    ("Sonny Fodera", "Mind Still"),
    ("MEDUZA", "Piece of Your Heart"),
    ("Joel Corry", "Head & Heart"),
    ("David Guetta", "Titanium"),
    ("Swedish House Mafia", "Don't You Worry Child"),
    ("Avicii", "Wake Me Up"),
    ("Avicii", "Levels"),
    ("Calvin Harris", "Summer"),
    ("Calvin Harris", "Feel So Close"),
    ("Daft Punk", "One More Time"),
    ("Daft Punk", "Digital Love"),
    ("Daft Punk", "Around the World"),
    ("Justice", "D.A.N.C.E."),
    ("The Chemical Brothers", "Galvanize"),
    ("Underworld", "Born Slippy .NUXX"),
    ("Faithless", "Insomnia"),
    ("Stardust", "Music Sounds Better With You"),
    ("Modjo", "Lady (Hear Me Tonight)"),
    ("Röyksopp", "Eple"),
    ("Sébastien Tellier", "La Ritournelle"),
    ("Kölsch", "Grey"),
    ("Âme", "Rej"),
    ("Black Coffee", "Drive"),
    ("Solomun", "Home"),
    ("&ME", "The Rapture"),
    ("Adriatique", "Nude"),
    ("Boris Brejcha", "Happinezz"),
    ("Four Tet", "Baby"),
    ("Caribou", "Can't Do Without You"),
    ("Jamie xx", "Gosh"),
    ("Flume", "Never Be Like You"),
    ("ODESZA", "A Moment Apart"),
    ("Jon Hopkins", "Emerald Rush"),
    ("Moderat", "A New Error"),
    ("Maceo Plex", "Conjure Superstar"),
    ("Hot Since 82", "Knee Deep In Louise"),
    ("Mall Grab", "Liverpool Street In The Rain"),
    ("Keinemusik", "Move"),
    ("Fisher", "Losing It (Extended Mix)"),
    ("Fisher", "You Little Beauty (Extended Mix)"),
    ("Chris Lake", "Turn Off The Lights (Extended Mix)"),
    ("Dom Dolla", "San Frandisco (Extended Mix)"),
    ("Purple Disco Machine", "Hypnotized (Extended Mix)"),
    ("MEDUZA", "Piece of Your Heart (Extended Mix)"),
    ("Joel Corry", "Head & Heart (Extended Mix)"),
    ("CamelPhat", "Cola (Extended Mix)"),
    ("Duke Dumont", "Ocean Drive (Extended Mix)"),
    ("MK", "17 (Extended Mix)"),
    ("Gorgon City", "Ready For Your Love (Extended Mix)"),
    ("Peggy Gou", "(It Goes Like) Nanana (Extended Mix)"),
    ("John Summit", "Where You Are (Extended Mix)"),
    ("Avicii", "Levels (Extended Mix)"),
    ("Avicii", "Wake Me Up (Radio Edit)"),
    ("Avicii", "Levels (Radio Edit)"),
    ("Swedish House Mafia", "Don't You Worry Child (Radio Edit)"),
    ("Calvin Harris", "Summer (Radio Edit)"),
    ("David Guetta", "Titanium (Radio Edit)"),
    ("Daft Punk", "One More Time (Radio Edit)"),
    ("Disclosure", "Latch (Radio Edit)"),
    ("MEDUZA", "Piece of Your Heart (Radio Edit)"),
    ("Joel Corry", "Head & Heart (Radio Edit)"),
    ("Faithless", "Insomnia (Radio Edit)"),
    ("Fisher", "You Little Beauty (Chris Lake Remix)"),
    ("Disclosure", "Latch (TIEKS Remix)"),
    ("Rüfüs Du Sol", "Innerbloom (What So Not Remix)"),
    ("M83", "Midnight City (Eric Prydz Remix)"),
    ("Eric Prydz", "Opus (Four Tet Remix)"),
    ("Chris Lake", "After Life (Chris Lake Remix)"),
    ("Bicep", "Glue (Pablo Bozzi Remix)"),
    ("Rüfüs Du Sol", "Innerbloom (Live)"),
    ("Bicep", "Glue (Live)"),
    ("The Chemical Brothers", "Galvanize (Live)"),
    ("Fred again..", "Marea (Live)"),
    ("Hugo Blanchart", "Booth Tape 19 November"),
    ("ZZQ Qzx", "Not A Real Dance Record"),
    ("Liminal Carp", "Marble Hour (Extended Mix)"),
    ("Nobody Real", "Untitled Dubplate"),
]


def query(index: int, artist: str, title: str) -> TrackQuery:
    return TrackQuery(id=f"eval-{index}", position=index, track_name=title, artist=artist, artists=artist)


def _ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def same_recording(artist: str, title: str, item: CatalogItem) -> bool:
    source_tokens = tokens(artist)
    candidate_tokens = tokens(" ".join(item.artists))
    if not source_tokens or not candidate_tokens:
        return False
    overlap = sum(1 for token in source_tokens if token in candidate_tokens) / len(source_tokens)
    if overlap < 0.67 and _ratio(normalize(artist), normalize(" ".join(item.artists))) < 0.84:
        return False
    left = normalize(strip_version(title))
    right = normalize(strip_version(item.title))
    if not left or not right:
        return False
    if left == right or left in right or right in left:
        return True
    return _ratio(left, right) >= 0.88


def version_score(title: str, item: CatalogItem) -> float:
    return version_compatibility(detect_version(title).kind, detect_version(item.title).kind)


def correct(artist: str, title: str, item: CatalogItem) -> bool:
    return same_recording(artist, title, item) and version_score(title, item) >= 0.85


def wrong_version(artist: str, title: str, item: CatalogItem) -> bool:
    return same_recording(artist, title, item) and version_score(title, item) < 0.2


async def run(limit: int) -> dict[str, object]:
    service = SearchService(YtMusicProvider(), concurrency=2, per_query=6, limit=5)
    rows = []
    errors = 0
    semaphore = asyncio.Semaphore(2)
    selected = list(enumerate(TRACKS[:limit], start=1))

    async def one(index: int, artist: str, title: str):
        async with semaphore:
            print(f"search {index} {artist} - {title}", file=sys.stderr, flush=True)
            track = query(index, artist, title)
            return index, artist, title, await asyncio.to_thread(service.match_track, track)

    results: list[tuple[int, str, str, object]] = []
    for offset in range(0, len(selected), 10):
        wave = selected[offset : offset + 10]
        batch = await asyncio.gather(*(one(index, artist, title) for index, (artist, title) in wave))
        results.extend(batch)
        if batch and all(item[3].status == "error" for item in batch):
            break
    for index, artist, title, result in results:
        top = result.candidates[0] if result.candidates else None
        catalog = [
            CatalogItem(
                video_id=candidate.video_id,
                title=candidate.title,
                artists=tuple(candidate.artists),
                album=candidate.album,
                duration_seconds=candidate.duration_seconds,
                thumbnail_url=candidate.thumbnail_url,
                result_type=candidate.result_type,
                channel=candidate.channel,
            )
            for candidate in result.candidates
        ]
        flags = [correct(artist, title, item) for item in catalog]
        top_wrong = bool(top and wrong_version(artist, title, catalog[0]))
        if result.status == "error":
            errors += 1
        rows.append(
            {
                "artist": artist,
                "title": title,
                "status": result.status,
                "selected": result.selected_video_id,
                "correct_first": bool(flags[:1] and flags[0]),
                "correct_top3": any(flags[:3]),
                "wrong_version_first": top_wrong,
                "no_valid": not any(flags),
                "false_high": result.status == "high" and not (flags[:1] and flags[0]),
                "error": result.error,
                "top": None
                if top is None
                else {"video_id": top.video_id, "title": top.title, "artists": top.artists, "score": top.score},
            }
        )
        print(f"{index}/{min(limit, len(TRACKS))} {artist} - {title} -> {result.status}", file=sys.stderr, flush=True)
    considered = rows
    total = len(considered)
    summary = {
        "evaluated": total,
        "catalog_size": min(limit, len(TRACKS)),
        "correct_first": sum(1 for row in considered if row["correct_first"]),
        "correct_top3": sum(1 for row in considered if row["correct_top3"]),
        "wrong_version_first": sum(1 for row in considered if row["wrong_version_first"]),
        "no_valid": sum(1 for row in considered if row["no_valid"]),
        "false_high": sum(1 for row in considered if row["false_high"]),
        "search_errors": errors,
    }
    failures = [
        row
        for row in considered
        if row["false_high"] or (row["wrong_version_first"] and not row["correct_first"]) or (not row["correct_top3"] and not row["no_valid"])
    ]
    return {"summary": summary, "failures": failures[:20], "rows": considered}


def main() -> None:
    if len(TRACKS) < 100:
        raise SystemExit(f"Expected at least 100 labelled tracks, found {len(TRACKS)}.")
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Tracks to score. 0 scores the full labelled list.")
    parser.add_argument("--output", type=Path, default=Path("reports/matching-eval.json"))
    args = parser.parse_args()
    limit = len(TRACKS) if args.limit <= 0 else args.limit
    report = asyncio.run(run(limit))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    summary = report["summary"]
    if isinstance(summary, dict) and summary.get("search_errors") == summary.get("evaluated") and summary.get("evaluated"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
