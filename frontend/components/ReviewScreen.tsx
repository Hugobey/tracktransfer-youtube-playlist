"use client";

import { useEffect, useMemo, useState } from "react";
import { TrackRow } from "@/components/TrackRow";
import { Button } from "@/components/Button";
import type { ReviewFilter } from "@/hooks/useTransfer";
import type { SessionState } from "@/lib/storage";

type Props = {
  state: SessionState;
  counts: { matched: number; review: number; missing: number; skipped: number; total: number };
  searching: boolean;
  searched: number;
  onReplace: () => void;
  confirmingReplace: boolean;
  onConfirmReplace: () => void;
  onCancelReplace: () => void;
  onSelect: (trackId: string, videoId: string) => void;
  onSkip: (trackId: string) => void;
  onSearch: (trackId: string, query: string) => Promise<void>;
  onRetry: (trackId: string) => void;
  focus: ReviewFilter | null;
  focusNonce: number;
};

const FILTERS: { id: ReviewFilter; label: string }[] = [
  { id: "all", label: "All tracks" },
  { id: "high", label: "High confidence" },
  { id: "review", label: "Needs review" },
  { id: "none", label: "Not found" },
  { id: "skipped", label: "Skipped" },
];

export function ReviewScreen({
  state,
  counts,
  searching,
  searched,
  onReplace,
  confirmingReplace,
  onConfirmReplace,
  onCancelReplace,
  onSelect,
  onSkip,
  onSearch,
  onRetry,
  focus,
  focusNonce,
}: Props) {
  const [filter, setFilter] = useState<ReviewFilter>("all");
  const [query, setQuery] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  useEffect(() => {
    if (focus) setFilter(focus);
  }, [focus, focusNonce]);
  const activeFilter = filter;

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return state.tracks.filter((track) => {
      const blob = `${track.track_name} ${track.artist} ${track.artists}`.toLowerCase();
      if (needle && !blob.includes(needle)) return false;
      const skipped = state.skipped.includes(track.id);
      const status = state.matches[track.id]?.status;
      if (activeFilter === "skipped") return skipped;
      if (activeFilter !== "all" && skipped) return false;
      if (activeFilter === "high") return status === "high";
      if (activeFilter === "review") return status === "likely" || status === "review";
      if (activeFilter === "none") return status === "none" || status === "error";
      return true;
    });
  }, [activeFilter, query, state.matches, state.skipped, state.tracks]);

  return (
    <section className="mx-auto w-full max-w-6xl px-4 pt-6 pb-36 md:px-6">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line pb-4">
        <div>
          <p className="font-plex text-[11px] tracking-[0.16em] text-muted uppercase">{state.filename}</p>
          <h1 className="font-display mt-1 text-3xl tracking-[-0.04em] text-ink">
            {counts.matched} / {counts.total} tracks matched
          </h1>
          <p className="mt-1 text-sm text-muted">
            {searching ? `Finding tracks ${Math.min(searched, counts.total)} / ${counts.total}. ` : ""}
            {counts.review} need review. {counts.missing} not found. {counts.skipped} skipped.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {confirmingReplace ? (
            <>
              <span className="text-sm text-muted">Replace this playlist?</span>
              <Button variant="secondary" onClick={onConfirmReplace}>
                Replace CSV
              </Button>
              <Button variant="quiet" onClick={onCancelReplace}>
                Cancel
              </Button>
            </>
          ) : (
            <Button variant="secondary" onClick={onReplace}>
              Replace CSV
            </Button>
          )}
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {FILTERS.map((item) => (
          <button
            key={item.id}
            type="button"
            aria-pressed={activeFilter === item.id}
            onClick={() => setFilter(item.id)}
            className={`h-8 border px-2.5 text-sm ${activeFilter === item.id ? "border-blue text-ink" : "border-line text-muted hover:border-line-strong"}`}
          >
            {item.label}
          </button>
        ))}
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Find a track"
          className="ml-auto h-8 w-full border border-border bg-transparent px-3 text-sm outline-none placeholder:text-faint md:w-56"
        />
      </div>
      <div className="mt-4 border border-line">
        <div className="hidden border-b border-line px-3 py-2 font-plex text-[10px] tracking-[0.14em] text-faint uppercase md:grid md:grid-cols-[44px_minmax(0,1.2fr)_minmax(0,0.9fr)_minmax(0,1.5fr)_64px_132px_88px] md:gap-3">
          <span>#</span>
          <span>Track</span>
          <span>Artist</span>
          <span>YouTube Music</span>
          <span>Time</span>
          <span>Match</span>
          <span />
        </div>
        {visible.length === 0 ? <p className="px-3 py-8 text-sm text-muted">No tracks in this view.</p> : null}
        {visible.map((track) => (
          <TrackRow
            key={track.id}
            track={track}
            match={state.matches[track.id]}
            selection={state.selections[track.id]}
            skipped={state.skipped.includes(track.id)}
            open={openId === track.id}
            onToggle={() => setOpenId((current) => (current === track.id ? null : track.id))}
            onSelect={(videoId) => onSelect(track.id, videoId)}
            onSkip={() => onSkip(track.id)}
            onSearch={(text) => onSearch(track.id, text)}
            onRetry={() => onRetry(track.id)}
          />
        ))}
      </div>
    </section>
  );
}
