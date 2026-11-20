"use client";

import { useState } from "react";
import { Logo } from "@/components/Logo";
import { PlaylistBar } from "@/components/PlaylistBar";
import { ReviewScreen } from "@/components/ReviewScreen";
import { UploadPanel } from "@/components/UploadPanel";
import { useTransfer, type ReviewFilter } from "@/hooks/useTransfer";

export default function HomePage() {
  const transfer = useTransfer();
  const [confirmingReplace, setConfirmingReplace] = useState(false);
  const [focus, setFocus] = useState<ReviewFilter | null>(null);
  const [focusNonce, setFocusNonce] = useState(0);

  const unresolved = transfer.state.tracks.filter(
    (track) => !transfer.state.skipped.includes(track.id) && !transfer.state.selections[track.id],
  ).length;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-line bg-bg/85 px-4 backdrop-blur-md md:px-6">
        <Logo />
        <p className="font-plex text-[11px] tracking-[0.16em] text-muted uppercase">YouTube Music</p>
      </header>
      {!transfer.ready || transfer.state.tracks.length === 0 ? (
        <main>
          <UploadPanel onFile={(file) => void transfer.importFile(file)} error={transfer.error} />
          <Disclaimer />
        </main>
      ) : (
        <main>
          {transfer.error ? (
            <p className="mx-auto mt-4 w-full max-w-6xl px-4 text-sm text-danger-text md:px-6">{transfer.error}</p>
          ) : null}
          <ReviewScreen
            state={transfer.state}
            counts={transfer.counts}
            searching={transfer.searching}
            searched={transfer.searched}
            confirmingReplace={confirmingReplace}
            onReplace={() => setConfirmingReplace(true)}
            onCancelReplace={() => setConfirmingReplace(false)}
            onConfirmReplace={() => {
              setConfirmingReplace(false);
              transfer.reset();
            }}
            onSelect={transfer.selectCandidate}
            onSkip={transfer.toggleSkip}
            onSearch={transfer.manualSearch}
            onRetry={(trackId) => void transfer.runSearch([trackId])}
            focus={focus}
            focusNonce={focusNonce}
          />
          <PlaylistBar
            title={transfer.state.playlistTitle}
            description={transfer.state.playlistDescription}
            privacy={transfer.state.privacy}
            selected={transfer.counts.matched}
            unresolved={unresolved}
            searching={transfer.searching}
            creating={transfer.creating}
            authorized={transfer.authorized}
            connect={transfer.connect}
            result={transfer.state.playlistResult}
            onTitle={transfer.setPlaylistTitle}
            onDescription={transfer.setPlaylistDescription}
            onPrivacy={transfer.setPrivacy}
            onCreate={() => void transfer.create()}
            onReview={() => {
              setFocus(transfer.counts.review > 0 ? "review" : "none");
              setFocusNonce((value) => value + 1);
            }}
            onSkipUnresolved={transfer.skipUnresolved}
            onRetry={() => void transfer.retry(false)}
            onSkipFailed={() => void transfer.retry(true)}
          />
          <Disclaimer />
        </main>
      )}
    </div>
  );
}

function Disclaimer() {
  return (
    <p className="mx-auto w-full max-w-6xl px-4 pb-28 text-xs leading-5 text-faint md:px-6">
      YouTube Music search uses ytmusicapi, an unofficial client. It is not endorsed by Google. Playlist creation uses
      YouTube&apos;s device sign-in. Tokens stay on this server.
    </p>
  );
}
