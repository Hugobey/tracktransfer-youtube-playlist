"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/Button";

type Props = {
  onFile: (file: File) => void;
  error: string | null;
};

export function UploadPanel({ onFile, error }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  function take(file: File | undefined) {
    if (!file) return;
    const name = file.name.toLowerCase();
    if (!name.endsWith(".csv") && file.type && file.type !== "text/csv" && file.type !== "application/vnd.ms-excel") {
      setLocalError("Choose a .csv file from the TrackTransfer exporter.");
      return;
    }
    setLocalError(null);
    onFile(file);
  }

  return (
    <section className="mx-auto flex w-full max-w-3xl flex-col px-6 pt-16 pb-20 md:pt-24">
      <p className="font-plex text-[11px] tracking-[0.18em] text-muted uppercase">TrackTransfer</p>
      <h1 className="font-display mt-3 max-w-2xl text-[44px] leading-[0.98] tracking-[-0.045em] text-ink md:text-[64px]">
        Move your Spotify playlist to YouTube Music.
      </h1>
      <p className="mt-5 max-w-xl text-base text-muted">
        Import your playlist, find the matching tracks and recreate it on YouTube Music.
      </p>
      <div
        className={`mt-10 flex min-h-56 flex-col items-center justify-center border px-6 py-10 text-center ${
          dragging ? "border-blue bg-panel" : "border-border bg-panel/40"
        }`}
        onDragEnter={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          take(event.dataTransfer.files?.[0]);
        }}
      >
        <p className="text-ink">Drop a TrackTransfer CSV</p>
        <p className="mt-1 text-sm text-muted">or browse for the file exported from Spotify.</p>
        <Button className="mt-5" onClick={() => inputRef.current?.click()}>
          Upload CSV
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          onChange={(event) => {
            take(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
      </div>
      {localError || error ? <p className="mt-4 text-sm text-danger-text">{localError || error}</p> : null}
      <p className="mt-6 max-w-2xl font-plex text-[11px] leading-5 text-faint">
        position, track_name, artist, artists, album, duration, duration_ms, date_added, spotify_track_id, spotify_url, explicit
      </p>
    </section>
  );
}
