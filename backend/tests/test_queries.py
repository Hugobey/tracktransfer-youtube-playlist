from app.models.schemas import TrackQuery
from app.services.queries import build_queries
from app.services.versions import detect_version


def query_for(title: str, artist: str = "Fisher") -> list[str]:
    return build_queries(TrackQuery(id="t", track_name=title, artist=artist, artists=artist))


def test_plain_title_does_not_grow_mix_or_audio_suffixes() -> None:
    queries = query_for("Losing It")
    assert queries == ["Fisher - Losing It"]
    assert all("Original Mix" not in query for query in queries)
    assert all("Official Audio" not in query for query in queries)
    assert all("Extended Mix" not in query for query in queries)


def test_extended_mix_is_searched_as_extended_not_rewritten_to_original() -> None:
    queries = query_for("Losing It (Extended Mix)")
    assert queries[0] == "Fisher - Losing It (Extended Mix)"
    assert any("Extended Mix" in query for query in queries)
    assert all("Original Mix" not in query for query in queries)
    assert all("Radio Edit" not in query for query in queries)


def test_original_mix_is_kept_when_the_source_says_so() -> None:
    queries = query_for("Losing It (Original Mix)")
    assert queries[0] == "Fisher - Losing It (Original Mix)"
    assert all("Extended Mix" not in query for query in queries)
    assert all("Official Audio" not in query for query in queries)


def test_radio_edit_and_remix_keep_their_words() -> None:
    radio = query_for("Levels (Radio Edit)", "Avicii")
    remix = query_for("Cola (CamelPhat Remix)", "CamelPhat")
    assert radio[0] == "Avicii - Levels (Radio Edit)"
    assert any("Radio Edit" in query for query in radio)
    assert remix[0] == "CamelPhat - Cola (CamelPhat Remix)"
    assert all("Original Mix" not in query for query in remix)


def test_accents_and_featured_artists_stay_in_the_query() -> None:
    queries = build_queries(
        TrackQuery(
            id="t",
            track_name="Eple (feat. Béla)",
            artist="Röyksopp",
            artists="Röyksopp, Béla",
        )
    )
    assert queries[0] == "Röyksopp - Eple (feat. Béla)"
    assert "Röyksopp - Eple" in queries


def test_version_priority_prefers_live_and_radio_over_a_generic_edit() -> None:
    assert detect_version("Innerbloom (Live at the Forum)").kind == "live"
    assert detect_version("Levels (Radio Edit)").kind == "radio"
    assert detect_version("Losing It (Extended Mix)").kind == "extended"
    assert detect_version("Losing It (Original Mix)").kind == "original"
    assert detect_version("Cola (CamelPhat Remix)").kind == "remix"
    assert detect_version("Losing It").kind is None
    assert detect_version("Paper").kind is None
