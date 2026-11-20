from app.models.schemas import TrackQuery
from app.services.matching import (
    WEIGHT_ARTIST,
    WEIGHT_DURATION,
    WEIGHT_OTHER,
    WEIGHT_TITLE,
    WEIGHT_VERSION,
    CatalogItem,
    rank_matches,
)


def track(title: str, artist: str, seconds: int = 248, album: str = "Night") -> TrackQuery:
    return TrackQuery(
        id="t1",
        position=1,
        track_name=title,
        artist=artist,
        artists=artist,
        album=album,
        duration_seconds=seconds,
    )


def song(
    video_id: str,
    title: str,
    artists: list[str],
    seconds: int = 248,
    album: str | None = "Night",
    result_type: str = "song",
) -> CatalogItem:
    return CatalogItem(
        video_id=video_id,
        title=title,
        artists=tuple(artists),
        album=album,
        duration_seconds=seconds,
        thumbnail_url="https://i.ytimg.com/vi/example/hqdefault.jpg" if video_id == "orig" else None,
        result_type=result_type,
        channel=None,
    )


def test_weights_match_the_brief() -> None:
    assert round(WEIGHT_ARTIST + WEIGHT_TITLE + WEIGHT_VERSION + WEIGHT_DURATION + WEIGHT_OTHER, 2) == 1.0


def test_exact_match_is_high_confidence_and_selected() -> None:
    result = rank_matches(
        track("Losing It", "Fisher"),
        [song("orig", "Losing It", ["Fisher"])],
    )
    assert result.status == "high"
    assert result.selected_video_id == "orig"
    assert result.candidates[0].score >= 0.84
    assert result.candidates[0].album == "Night"


def test_original_mix_beats_extended_and_radio() -> None:
    result = rank_matches(
        track("Losing It (Original Mix)", "Fisher", 248),
        [
            song("radio", "Losing It (Radio Edit)", ["Fisher"], 192),
            song("ext", "Losing It (Extended Mix)", ["Fisher"], 390),
            song("orig", "Losing It (Original Mix)", ["Fisher"], 248),
        ],
    )
    assert result.candidates[0].video_id == "orig"
    assert result.status == "high"
    assert result.selected_video_id == "orig"
    assert result.candidates[0].version == "original"
    versions = {candidate.video_id: candidate.version for candidate in result.candidates}
    assert versions["ext"] == "extended"
    assert versions["radio"] == "radio"


def test_extended_mix_is_not_treated_as_the_radio_edit() -> None:
    result = rank_matches(
        track("Levels (Extended Mix)", "Avicii", 360),
        [song("radio", "Levels (Radio Edit)", ["Avicii"], 180)],
    )
    assert result.selected_video_id is None
    assert result.status in {"review", "none"}
    assert result.candidates[0].signals.version < 0.2
    assert any("radio edit" in reason.lower() for reason in result.candidates[0].reasons)


def test_extended_mix_selects_the_extended_recording() -> None:
    result = rank_matches(
        track("Levels (Extended Mix)", "Avicii", 360),
        [
            song("radio", "Levels (Radio Edit)", ["Avicii"], 180),
            song("ext", "Levels (Extended Mix)", ["Avicii"], 360),
        ],
    )
    assert result.selected_video_id == "ext"
    assert result.status == "high"


def test_remix_is_not_the_original() -> None:
    result = rank_matches(
        track("Cola (CamelPhat Remix)", "CamelPhat", 210),
        [
            song("orig", "Cola", ["CamelPhat", "Elderbrook"], 210),
            song("remix", "Cola (CamelPhat Remix)", ["CamelPhat"], 210),
        ],
    )
    assert result.candidates[0].video_id == "remix"
    assert result.selected_video_id == "remix"
    remix_score = next(candidate.score for candidate in result.candidates if candidate.video_id == "orig")
    assert remix_score < 0.6


def test_live_version_is_penalized_for_a_studio_source() -> None:
    result = rank_matches(
        track("Innerbloom", "Rüfüs Du Sol", 248),
        [
            song("live", "Innerbloom (Live at the Forum)", ["RÜFÜS DU SOL"], 480),
            song("studio", "Innerbloom", ["Rufus Du Sol"], 248),
        ],
    )
    assert result.selected_video_id == "studio"
    assert result.status == "high"
    live = next(candidate for candidate in result.candidates if candidate.video_id == "live")
    assert live.signals.version < 0.2
    assert result.selected_video_id != "live"


def test_accent_and_spelling_differences_still_match() -> None:
    result = rank_matches(
        track("Eple", "Röyksopp", 180, album="Melody A.M."),
        [song("eple", "Eple", ["Royksopp"], 180, album="Melody A.M.")],
    )
    assert result.status == "high"
    assert result.selected_video_id == "eple"


def test_comma_in_a_single_artist_name_is_not_split() -> None:
    result = rank_matches(
        track("Earfquake", "Tyler, The Creator", 190),
        [song("earf", "Earfquake", ["Tyler, The Creator"], 190)],
    )
    assert result.status == "high"
    assert result.candidates[0].signals.artist >= 0.9


def test_first_result_is_not_accepted_when_it_is_the_wrong_version() -> None:
    result = rank_matches(
        track("Losing It", "Fisher", 248),
        [
            song("ext", "Losing It (Extended Mix)", ["Fisher"], 390),
            song("orig", "Losing It", ["Fisher"], 248),
        ],
    )
    assert result.candidates[0].video_id == "orig"
    assert result.selected_video_id == "orig"


def test_missing_artist_is_not_auto_selected() -> None:
    result = rank_matches(
        TrackQuery(id="t", track_name="Losing It", artist="", artists="", duration_seconds=248),
        [song("orig", "Losing It", ["Fisher"], 248)],
    )
    assert result.selected_video_id is None
    assert result.status in {"review", "none"}


def test_no_results_and_unrelated_results() -> None:
    empty = rank_matches(track("Losing It", "Fisher"), [])
    assert empty.status == "none"
    assert empty.selected_video_id is None
    unrelated = rank_matches(
        track("Losing It", "Fisher"),
        [song("other", "A Different Record", ["Someone Else"], 90, album="Other")],
    )
    assert unrelated.selected_video_id is None
    assert unrelated.status in {"none", "review"}


def test_several_candidates_are_returned_in_score_order() -> None:
    result = rank_matches(
        track("Latch", "Disclosure", 255),
        [
            song("a", "Latch", ["Disclosure"], 255),
            song("b", "Latch (Radio Edit)", ["Disclosure"], 200),
            song("c", "Latch", ["Someone Else"], 255),
            song("d", "Latch (Live)", ["Disclosure"], 400),
            song("e", "Latch (Extended Mix)", ["Disclosure"], 360),
            song("f", "Latch (Disclosure VIP)", ["Disclosure"], 300),
        ],
        limit=5,
    )
    assert len(result.candidates) == 5
    scores = [candidate.score for candidate in result.candidates]
    assert scores == sorted(scores, reverse=True)
    assert result.candidates[0].video_id == "a"
    assert result.selected_video_id == "a"


def test_missing_metadata_is_left_empty() -> None:
    result = rank_matches(
        track("Glue", "Bicep", 240, album=""),
        [
            CatalogItem(
                video_id="glue",
                title="Glue",
                artists=("Bicep",),
                album=None,
                duration_seconds=None,
                thumbnail_url=None,
                result_type="song",
                channel=None,
            )
        ],
    )
    candidate = result.candidates[0]
    assert candidate.album is None
    assert candidate.duration_seconds is None
    assert candidate.thumbnail_url is None
    assert candidate.channel is None
