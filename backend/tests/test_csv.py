import csv
import io

import pytest

from app.errors import AppError
from app.services.csv_service import CSV_COLUMNS, parse_csv

HEADER = ",".join(CSV_COLUMNS)


def track_line(
    position: int,
    title: str,
    artist: str = "Ada",
    artists: str | None = None,
    album: str = "Night",
    duration: str = "3:45",
    duration_ms: str = "225000",
    date_added: str = "2026-01-01",
    track_id: str = "abc",
    url: str | None = None,
    explicit: str = "false",
    delimiter: str = ",",
) -> str:
    url = url if url is not None else (f"https://open.spotify.com/track/{track_id}" if track_id else "")
    artists = artist if artists is None else artists
    row = [
        str(position),
        title,
        artist,
        artists,
        album,
        duration,
        duration_ms,
        date_added,
        track_id,
        url,
        explicit,
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="")
    writer.writerow(row)
    return buffer.getvalue()


def document(rows: list[str], delimiter: str = ",") -> str:
    header = delimiter.join(CSV_COLUMNS)
    return "\ufeff" + header + "\r\n" + "\r\n".join(rows) + "\r\n"


def test_valid_export_keeps_order_accents_and_duplicates() -> None:
    csv_text = document(
        [
            track_line(2, "Café", artist="Béla", artists="Béla, 坂本", track_id="same"),
            track_line(1, 'Say "Hello"', artist="Tyler, The Creator", track_id="same"),
            track_line(3, "Café", artist="Béla", artists="Béla, 坂本", track_id="same"),
        ]
    )
    parsed = parse_csv(csv_text)
    assert parsed.delimiter == ","
    assert [track.position for track in parsed.tracks] == [1, 2, 3]
    assert parsed.tracks[0].track_name == 'Say "Hello"'
    assert parsed.tracks[0].artist == "Tyler, The Creator"
    assert parsed.tracks[1].track_name == "Café"
    assert parsed.tracks[1].artists == "Béla, 坂本"
    assert parsed.tracks[1].id != parsed.tracks[2].id
    assert parsed.tracks[1].spotify_track_id == parsed.tracks[2].spotify_track_id == "same"
    assert len(parsed.tracks) == 3


def test_semicolon_delimiter_and_missing_metadata() -> None:
    csv_text = document(
        [
            track_line(
                1,
                "A;B",
                artist="Ada",
                artists="Ada, Béla",
                album="",
                duration="",
                duration_ms="",
                date_added="",
                track_id="",
                url="",
                explicit="",
                delimiter=";",
            )
        ],
        delimiter=";",
    )
    parsed = parse_csv(csv_text)
    track = parsed.tracks[0]
    assert parsed.delimiter == ";"
    assert track.track_name == "A;B"
    assert track.artists == "Ada, Béla"
    assert track.album == ""
    assert track.duration_ms is None
    assert track.duration_seconds is None
    assert track.explicit is None
    assert "missing_duration" in track.issues


def test_clock_duration_is_used_when_milliseconds_are_blank() -> None:
    parsed = parse_csv(document([track_line(1, "Hour", duration="1:02:03", duration_ms="")]))
    assert parsed.tracks[0].duration_ms is None
    assert parsed.tracks[0].duration_seconds == 3723


def test_invalid_header_names_the_expected_export() -> None:
    with pytest.raises(AppError) as caught:
        parse_csv("song,artist\nA,B\n")
    assert caught.value.code == "invalid_csv"
    assert HEADER in caught.value.message


def test_empty_file_and_header_only() -> None:
    with pytest.raises(AppError) as empty:
        parse_csv("   ")
    assert empty.value.code == "invalid_csv"
    with pytest.raises(AppError) as header_only:
        parse_csv("\ufeff" + HEADER + "\r\n")
    assert header_only.value.code == "empty_csv"


def test_missing_title_and_artist_are_kept() -> None:
    parsed = parse_csv(document([track_line(1, "", artist="", artists="")]))
    track = parsed.tracks[0]
    assert track.track_name == ""
    assert "missing_title" in track.issues
    assert "missing_artist" in track.issues


@pytest.mark.parametrize("count", [10, 50, 100, 300])
def test_playlist_sizes(count: int) -> None:
    rows = [
        track_line(position, f"Track {position}", artist=f"Artist {position}", track_id=f"id{position}")
        for position in range(count, 0, -1)
    ]
    rows[-1] = track_line(1, "Café déjà vu", artist="坂本", track_id="dup")
    rows.append(track_line(1, "Café déjà vu", artist="坂本", track_id="dup"))
    parsed = parse_csv(document(rows))
    assert len(parsed.tracks) == count + 1
    assert parsed.tracks[0].position == 1
    assert parsed.tracks[-1].position == count
    assert parsed.tracks[0].track_name == "Café déjà vu"
    assert sum(1 for track in parsed.tracks if track.spotify_track_id == "dup") == 2
