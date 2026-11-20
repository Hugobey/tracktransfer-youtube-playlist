"use client";

import { Button } from "@/components/Button";
import type { AuthStart, PlaylistJob, Privacy } from "@/types/api";

type Props = {
  title: string;
  description: string;
  privacy: Privacy;
  selected: number;
  unresolved: number;
  searching: boolean;
  creating: boolean;
  authorized: boolean;
  connect: AuthStart | null;
  result: PlaylistJob | null;
  onTitle: (value: string) => void;
  onDescription: (value: string) => void;
  onPrivacy: (value: Privacy) => void;
  onCreate: () => void;
  onReview: () => void;
  onSkipUnresolved: () => void;
  onRetry: () => void;
  onSkipFailed: () => void;
};

export function PlaylistBar(props: Props) {
  const done = props.result?.status === "complete";
  const blocked = props.result?.status === "blocked" || props.result?.status === "partial" || props.result?.status === "failed";
  const failures = (props.result?.items ?? []).filter((item) => item.status === "failed");

  return (
    <footer className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-bg/95 backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 px-4 py-3 md:px-6">
        {props.connect?.user_code ? (
          <div className="flex flex-wrap items-center justify-between gap-3 border border-border bg-panel px-3 py-2">
            <div>
              <p className="text-sm text-ink">Sign in to YouTube Music</p>
              <p className="font-plex text-lg tracking-[0.14em] text-ink">{props.connect.user_code}</p>
            </div>
            {props.connect.verification_url ? (
              <a className="text-sm text-blue-2 underline-offset-2 hover:underline" href={props.connect.verification_url} target="_blank" rel="noreferrer">
                Open Google sign-in
              </a>
            ) : null}
          </div>
        ) : null}
        {done ? (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm text-ok">Playlist created</p>
              <p className="text-ink">{props.result?.title}</p>
              <p className="text-sm text-muted">
                {props.result?.added} tracks added
                {props.result?.skipped ? `. ${props.result.skipped} skipped` : ""}.
              </p>
            </div>
            {props.result?.url ? (
              <a className="inline-flex h-9 items-center bg-blue px-3.5 text-sm font-medium text-white" href={props.result.url} target="_blank" rel="noreferrer">
                Open playlist
              </a>
            ) : null}
          </div>
        ) : (
          <>
            <div className="grid gap-2 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1.4fr)_140px]">
              <input
                value={props.title}
                onChange={(event) => props.onTitle(event.target.value)}
                aria-label="Playlist name"
                className="h-9 border border-border bg-transparent px-3 text-sm outline-none"
                disabled={Boolean(props.result?.playlist_id)}
              />
              <input
                value={props.description}
                onChange={(event) => props.onDescription(event.target.value)}
                aria-label="Playlist description"
                className="h-9 border border-border bg-transparent px-3 text-sm outline-none"
                disabled={Boolean(props.result?.playlist_id)}
              />
              <select
                value={props.privacy}
                onChange={(event) => props.onPrivacy(event.target.value as Privacy)}
                aria-label="Playlist privacy"
                className="h-9 border border-border bg-bg px-2 text-sm outline-none"
                disabled={Boolean(props.result?.playlist_id)}
              >
                <option value="PRIVATE">Private</option>
                <option value="UNLISTED">Unlisted</option>
                <option value="PUBLIC">Public</option>
              </select>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-muted">
                {props.creating && props.result
                  ? `Adding ${props.result.added} / ${props.result.track_count}`
                  : `${props.selected} tracks selected`}
                {props.unresolved > 0 ? ` · ${props.unresolved} still need a decision` : ""}
              </p>
              <div className="flex gap-2">
                {props.unresolved > 0 ? (
                  <>
                    <Button variant="secondary" onClick={props.onReview}>
                      Review {props.unresolved}
                    </Button>
                    <Button variant="quiet" disabled={props.searching || props.creating} onClick={props.onSkipUnresolved}>
                      Skip unresolved
                    </Button>
                  </>
                ) : null}
                {blocked ? (
                  <>
                    <Button variant="secondary" disabled={props.creating} onClick={props.onRetry}>
                      Retry failed
                    </Button>
                    <Button variant="quiet" disabled={props.creating} onClick={props.onSkipFailed}>
                      Skip failed and continue
                    </Button>
                  </>
                ) : null}
                <Button disabled={props.searching || props.creating || props.unresolved > 0 || props.selected === 0} onClick={props.onCreate}>
                  {props.creating ? "Working" : props.authorized ? "Create playlist" : "Connect and create"}
                </Button>
              </div>
            </div>
            {failures.length > 0 ? (
              <ul className="max-h-24 overflow-auto text-xs text-danger-text">
                {failures.map((item) => (
                  <li key={item.track_id}>{item.error || `Position ${item.position} failed.`}</li>
                ))}
              </ul>
            ) : null}
            {props.result && props.result.status !== "complete" && props.result.playlist_id ? (
              <p className="text-xs text-muted">
                Playlist started. {props.result.added} added, {props.result.failed} failed, {props.result.pending} waiting.
                {props.result.url ? (
                  <>
                    {" "}
                    <a className="text-blue-2" href={props.result.url} target="_blank" rel="noreferrer">
                      Open the partial playlist
                    </a>
                  </>
                ) : null}
              </p>
            ) : null}
          </>
        )}
      </div>
    </footer>
  );
}
