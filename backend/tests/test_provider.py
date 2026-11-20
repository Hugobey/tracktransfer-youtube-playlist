from app.services.ytmusic_provider import parse_catalog_item


def test_parser_keeps_only_metadata_the_result_actually_has() -> None:
    item = parse_catalog_item(
        {
            "resultType": "song",
            "videoId": "ZrOKjDZOtkA",
            "title": "Wonderwall",
            "artists": [{"name": "Oasis", "id": "artist"}],
            "duration": "4:19",
            "duration_seconds": 259,
        }
    )
    assert item is not None
    assert item.video_id == "ZrOKjDZOtkA"
    assert item.artists == ("Oasis",)
    assert item.album is None
    assert item.thumbnail_url is None
    assert item.channel is None
    assert item.duration_seconds == 259
    assert item.result_type == "song"


def test_parser_drops_results_without_a_video_id() -> None:
    assert parse_catalog_item({"title": "Oasis", "resultType": "artist", "browseId": "x"}) is None
    assert parse_catalog_item("nope") is None


def test_thumbnail_uses_the_last_real_url() -> None:
    item = parse_catalog_item(
        {
            "videoId": "abcdefghijk",
            "title": "Glue",
            "artists": ["Bicep"],
            "thumbnails": [{"url": "https://example.test/small.jpg"}, {"url": "https://example.test/large.jpg"}],
            "author": "Bicep",
            "resultType": "video",
            "duration": "4:00",
        }
    )
    assert item is not None
    assert item.thumbnail_url == "https://example.test/large.jpg"
    assert item.channel == "Bicep"
    assert item.duration_seconds == 240
    assert item.artists == ("Bicep",)
