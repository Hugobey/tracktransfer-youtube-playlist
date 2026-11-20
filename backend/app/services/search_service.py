"""Search orchestration. The catalog implementation can be replaced."""

from __future__ import annotations

import asyncio
from typing import Protocol

from app.errors import AppError
from app.models.schemas import TrackMatchOut, TrackQuery
from app.services.matching import CatalogItem, rank_matches
from app.services.queries import build_queries


class MusicCatalog(Protocol):
    def search(self, query: str, *, kind: str, limit: int) -> list[CatalogItem]:
        """Return song or video results. `kind` is `songs` or `videos`."""


class SearchService:
    def __init__(self, catalog: MusicCatalog, *, concurrency: int = 3, per_query: int = 8, limit: int = 5) -> None:
        self.catalog = catalog
        self.concurrency = concurrency
        self.per_query = per_query
        self.limit = limit

    async def match_many(self, tracks: list[TrackQuery]) -> list[TrackMatchOut]:
        semaphore = asyncio.Semaphore(self.concurrency)

        async def run(track: TrackQuery) -> TrackMatchOut:
            async with semaphore:
                return await asyncio.to_thread(self.match_track, track)

        return list(await asyncio.gather(*(run(track) for track in tracks)))

    def match_track(self, track: TrackQuery) -> TrackMatchOut:
        queries = build_queries(track)
        return self._search(track, queries)

    def match_query(self, track: TrackQuery, query: str) -> TrackMatchOut:
        cleaned = " ".join(query.split())
        if not cleaned:
            raise AppError("empty_query", "Enter a search.")
        if len(cleaned) > 200:
            raise AppError("empty_query", "That search is too long.")
        return self._search(track, [cleaned])

    def _search(self, track: TrackQuery, queries: list[str]) -> TrackMatchOut:
        if not queries:
            result = rank_matches(track, [], limit=self.limit)
            return result.model_copy(update={"queries": []})
        try:
            items = self._collect(queries)
        except AppError as exc:
            return TrackMatchOut(id=track.id, queries=queries, status="error", error=exc.message)
        except Exception as exc:  # noqa: BLE001 - one track must not fail the batch
            return TrackMatchOut(
                id=track.id,
                queries=queries,
                status="error",
                error=_public_error(exc),
            )
        result = rank_matches(track, items, limit=self.limit)
        return result.model_copy(update={"queries": queries})

    def _collect(self, queries: list[str]) -> list[CatalogItem]:
        found: list[CatalogItem] = []
        seen: set[str] = set()
        for query in queries:
            for item in self.catalog.search(query, kind="songs", limit=self.per_query):
                if item.video_id in seen:
                    continue
                seen.add(item.video_id)
                found.append(item)
        if found:
            return found
        for item in self.catalog.search(queries[0], kind="videos", limit=self.per_query):
            if item.video_id in seen:
                continue
            seen.add(item.video_id)
            found.append(item)
        return found


def _public_error(exc: Exception) -> str:
    text = " ".join(str(exc).split())
    if not text:
        return "YouTube Music search failed."
    return text[:240]
