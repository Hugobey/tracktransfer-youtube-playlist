"use client";

import { useState } from "react";
import { Button } from "@/components/Button";
import { formatClock } from "@/lib/format";
import type { Candidate } from "@/types/api";

type Props = {
  candidates: Candidate[];
  selectedVideoId: string | null;
  onSelect: (videoId: string) => void;
  onSearch: (query: string) => Promise<void>;
  onRetry: () => void;
};

export function CandidateList({ candidates, selectedVideoId, onSelect, onSearch, onRetry }: Props) {
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);

  return (
    <div className="border-t border-line bg-sunken px-3 py-3 md:px-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search YouTube Music again"
          className="h-9 min-w-56 flex-1 border border-border bg-bg px-3 text-sm outline-none placeholder:text-faint"
          onKeyDown={(event) => {
            if (event.key === "Enter" && query.trim()) {
              setBusy(true);
              void onSearch(query.trim()).finally(() => setBusy(false));
            }
          }}
        />
        <Button
          variant="secondary"
          disabled={busy || !query.trim()}
          onClick={() => {
            setBusy(true);
            void onSearch(query.trim()).finally(() => setBusy(false));
          }}
        >
          Search
        </Button>
        <Button variant="quiet" onClick={onRetry}>
          Retry match
        </Button>
      </div>
      {candidates.length === 0 ? <p className="text-sm text-muted">No YouTube Music result. Try another search.</p> : null}
      <ul className="flex flex-col">
        {candidates.map((candidate) => {
          const selected = candidate.video_id === selectedVideoId;
          const artist = candidate.artists.join(", ");
          return (
            <li key={candidate.video_id} className={`flex items-center gap-3 border-t border-line py-2 ${selected ? "text-ink" : "text-muted"}`}>
              {candidate.thumbnail_url ? (
                <img src={candidate.thumbnail_url} alt="" className="h-10 w-10 object-cover" referrerPolicy="no-referrer" />
              ) : (
                <span className="h-10 w-10 bg-panel" />
              )}
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm text-ink">{candidate.title || "Untitled"}</span>
                <span className="block truncate text-xs text-muted">
                  {[artist, candidate.album, candidate.result_type].filter(Boolean).join(" · ")}
                </span>
                {candidate.reasons[0] ? <span className="mt-0.5 block text-xs text-faint">{candidate.reasons[0]}</span> : null}
              </span>
              <span className="w-12 text-right font-plex text-xs text-muted">{formatClock(candidate.duration_seconds) || "—"}</span>
              <Button variant={selected ? "primary" : "secondary"} onClick={() => onSelect(candidate.video_id)}>
                {selected ? "Selected" : "Select"}
              </Button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
