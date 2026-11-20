from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.models.schemas import TrackQuery
from app.services.auth_service import AuthService
from app.services.container import Services, set_services
from app.services.matching import CatalogItem
from app.services.playlist_service import PlaylistService
from app.services.search_service import SearchService
from tests.test_auth import Flow
from tests.test_csv import HEADER, document, track_line
from tests.test_playlist import Auth, Gateway


class Catalog:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def search(self, query: str, *, kind: str, limit: int) -> list[CatalogItem]:
        self.calls.append((kind, query))
        if kind == "videos":
            return []
        if "Missing" in query:
            return []
        return [
            CatalogItem(
                video_id="abcdefghijk",
                title=query.split(" - ", 1)[-1],
                artists=(query.split(" - ", 1)[0],),
                album=None,
                duration_seconds=225,
                thumbnail_url=None,
                result_type="song",
                channel=None,
            )
        ][:limit]


def build(tmp_path, catalog: Catalog | None = None, auth_flow: Flow | None = None) -> TestClient:
    settings = Settings(
        client_id="client",
        client_secret="secret",
        data_dir=tmp_path,
        cors_origins=("http://localhost:3000",),
        batch_limit=2,
        add_chunk_size=10,
    )
    catalog = catalog or Catalog()
    auth = AuthService(tmp_path, auth_flow) if auth_flow is not None else Auth()
    gateway = Gateway()

    def gateway_for(_session: str) -> Gateway:
        return gateway

    services = Services(
        settings=settings,
        search=SearchService(catalog, concurrency=2, per_query=5, limit=5),
        auth=auth,  # type: ignore[arg-type]
        playlists=PlaylistService(tmp_path, auth, gateway_for, chunk_size=10),
    )
    set_services(services)
    return TestClient(app)


def test_parse_endpoint_accepts_an_export(tmp_path) -> None:
    client = build(tmp_path)
    response = client.post(
        "/api/csv/parse",
        json={"filename": "../TrackTransfer - Café.csv", "content": document([track_line(1, "Café")])},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "TrackTransfer - Café.csv"
    assert body["track_count"] == 1
    assert body["tracks"][0]["track_name"] == "Café"
    assert response.text.find("secret") == -1


def test_parse_endpoint_rejects_a_foreign_csv(tmp_path) -> None:
    client = build(tmp_path)
    response = client.post("/api/csv/parse", json={"filename": "other.csv", "content": "a,b\n1,2\n"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_csv"
    assert HEADER.split(",")[0] in response.json()["error"]["message"]


def test_batch_preserves_identity_and_limits_size(tmp_path) -> None:
    catalog = Catalog()
    client = build(tmp_path, catalog)
    tracks = [
        TrackQuery(id="p1-0", position=1, track_name="Alpha", artist="Ada", duration_seconds=225).model_dump(),
        TrackQuery(id="p2-0", position=2, track_name="Missing Song", artist="Bea", duration_seconds=225).model_dump(),
    ]
    response = client.post("/api/search/batch", json={"tracks": tracks})
    assert response.status_code == 200
    results = response.json()["results"]
    assert [row["id"] for row in results] == ["p1-0", "p2-0"]
    assert results[0]["status"] == "high"
    assert results[0]["selected_video_id"] == "abcdefghijk"
    assert results[1]["status"] == "none"
    assert catalog.calls[0][0] == "songs"
    too_many = client.post("/api/search/batch", json={"tracks": tracks + tracks})
    assert too_many.status_code == 400
    assert too_many.json()["error"]["code"] == "batch_too_large"


def test_manual_search_uses_the_typed_query(tmp_path) -> None:
    client = build(tmp_path)
    response = client.post(
        "/api/search",
        json={
            "query": "Ada - Alpha Extended Mix",
            "track": TrackQuery(id="p1-0", track_name="Alpha", artist="Ada", duration_seconds=225).model_dump(),
        },
    )
    assert response.status_code == 200
    assert response.json()["queries"] == ["Ada - Alpha Extended Mix"]


def test_auth_and_playlist_http_flow_does_not_leak_secrets(tmp_path) -> None:
    client = build(tmp_path, auth_flow=Flow())
    started = client.post("/api/auth/start")
    assert started.status_code == 200
    assert started.json()["user_code"] == "ABCD-EFGH"
    assert "device-secret" not in started.text
    assert "access-secret" not in started.text
    assert client.cookies.get("tt_session")
    pending = client.post("/api/auth/poll")
    assert pending.json()["status"] == "pending"
    authorized = client.post("/api/auth/poll")
    assert authorized.json()["status"] == "authorized"
    assert "refresh-secret" not in authorized.text
    job_id = str(uuid4())
    created = client.post(
        "/api/playlist/create",
        json={
            "job_id": job_id,
            "title": "Café — TrackTransfer",
            "description": "Transferred from Spotify with TrackTransfer.",
            "privacy": "PRIVATE",
            "tracks": [
                {"track_id": "p1-0", "position": 1, "video_id": "abcdefghijk", "title": "Café", "artist": "Ada"},
                {"track_id": "p2-0", "position": 2, "video_id": "bbcdefghijk", "title": "Beta", "artist": "Bea"},
            ],
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "complete"
    assert body["added"] == 2
    assert body["url"].endswith(body["playlist_id"])
    status = client.get(f"/api/playlist/status/{job_id}")
    assert status.json()["added"] == 2
    assert "secret" not in status.text
