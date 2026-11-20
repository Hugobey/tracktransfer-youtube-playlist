"use client";

import { CandidateList } from "@/components/CandidateList";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/Button";
import { formatClock, statusLabel } from "@/lib/format";
import type { ImportedTrack, TrackMatch } from "@/types/api";
import type { Selection } from "@/lib/storage";

type Props = {
  track: ImportedTrack;
  match: TrackMatch | undefined;
  selection: Selection | undefined;
  skipped: boolean;
  open: boolean;
  onToggle: () => void;
  onSelect: (videoId: string) => void;
  onSkip: () => void;
  onSearch: (query: string) => Promise<void>;
  onRetry: () => void;
};

export function TrackRow({ track, match, selection, skipped, open, onToggle, onSelect, onSkip, onSearch, onRetry }: Props) {
  const candidate = match?.candidates.find((item) => item.video_id === selection?.videoId) ?? null;
  const status = match?.status ?? "pending";
  const label = statusLabel(status, skipped, selection?.source === "user");
  const tone = skipped ? "skipped" : selection?.source === "user" ? "selected" : status;
  const duration = candidate ? formatClock(candidate.duration_seconds) : track.duration;

  return (
    <article className={`border-b border-line ${skipped ? "opacity-50" : ""}`}>
      <div className="grid grid-cols-1 gap-2 px-3 py-3 md:grid-cols-[44px_minmax(0,1.2fr)_minmax(0,0.9fr)_minmax(0,1.5fr)_64px_132px_88px] md:items-center md:gap-3">
        <span className="font-plex text-xs text-faint">{track.position}</span>
        <span className="min-w-0">
          <span className="block truncate text-sm text-ink">{track.track_name || "Untitled"}</span>
          {track.issues.length > 0 ? <span className="text-xs text-warn">Missing metadata</span> : null}
        </span>
        <span className="truncate text-sm text-muted">{track.artist || track.artists || "Unknown artist"}</span>
        <button type="button" onClick={onToggle} className="flex min-w-0 items-center gap-2 text-left">
          {candidate?.thumbnail_url ? (
            <img src={candidate.thumbnail_url} alt="" className="h-8 w-8 object-cover" referrerPolicy="no-referrer" />
          ) : (
            <span className="h-8 w-8 bg-sunken" />
          )}
          <span className="min-w-0">
            <span className={`block truncate text-sm ${candidate ? "text-ink" : "text-faint"}`}>
              {candidate?.title || (status === "searching" ? "Searching" : "Choose a result")}
            </span>
            <span className="block truncate text-xs text-muted">{candidate?.artists.join(", ")}</span>
          </span>
        </button>
        <span className="font-plex text-xs text-muted">{duration || "—"}</span>
        <StatusBadge label={label} tone={tone} />
        <span className="flex gap-1">
          <Button variant="quiet" onClick={onToggle}>
            {open ? "Close" : "Change"}
          </Button>
          <Button variant="quiet" onClick={onSkip}>
            {skipped ? "Undo" : "Skip"}
          </Button>
        </span>
      </div>
      {open ? (
        <CandidateList
          candidates={match?.candidates ?? []}
          selectedVideoId={selection?.videoId ?? null}
          onSelect={onSelect}
          onSearch={onSearch}
          onRetry={onRetry}
        />
      ) : null}
      {match?.error ? <p className="px-3 pb-3 text-xs text-danger-text">{match.error}</p> : null}
    </article>
  );
}
