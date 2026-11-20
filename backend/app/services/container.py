"""Wires the process-wide services. Tests replace this with fakes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ytmusicapi import OAuthCredentials

from app.config import Settings, load_settings
from app.services.auth_service import AuthService
from app.services.playlist_service import PlaylistGateway, PlaylistService
from app.services.search_service import SearchService
from app.services.ytmusic_provider import YtMusicProvider


@dataclass
class Services:
    settings: Settings
    search: SearchService
    auth: AuthService
    playlists: PlaylistService


class YtGateway:
    def __init__(self, provider: YtMusicProvider, token_path: Path) -> None:
        self.provider = provider
        self.token_path = token_path

    def create_playlist(self, title: str, description: str, privacy: str) -> str:
        return self.provider.create_playlist(self.token_path, title, description, privacy)

    def add_items(self, playlist_id: str, video_ids: list[str]) -> None:
        self.provider.add_items(self.token_path, playlist_id, video_ids)


def build_services(settings: Settings | None = None) -> Services:
    settings = settings or load_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    provider = YtMusicProvider(settings.client_id, settings.client_secret)
    credentials = OAuthCredentials(settings.client_id, settings.client_secret) if settings.auth_configured else None
    auth = AuthService(settings.data_dir, credentials)
    search = SearchService(
        provider,
        concurrency=settings.search_concurrency,
        per_query=settings.search_limit,
        limit=settings.candidate_limit,
    )

    def gateway_for(session_id: str) -> PlaylistGateway:
        return YtGateway(provider, auth.token_path(session_id))

    playlists = PlaylistService(
        settings.data_dir,
        auth,
        gateway_for,
        chunk_size=settings.add_chunk_size,
    )
    return Services(settings=settings, search=search, auth=auth, playlists=playlists)


_services: Services | None = None


def get_services() -> Services:
    global _services
    if _services is None:
        _services = build_services()
    return _services


def set_services(services: Services) -> None:
    global _services
    _services = services
