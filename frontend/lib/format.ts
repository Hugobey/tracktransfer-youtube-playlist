export function formatClock(seconds: number | null | undefined): string {
  if (seconds == null || seconds < 0 || Number.isNaN(seconds)) return "";
  const whole = Math.round(seconds);
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const secs = whole % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

export function playlistTitleFromFilename(filename: string): string {
  const base = filename.replace(/\.csv$/i, "").trim() || "Playlist";
  return `${base} — TrackTransfer`;
}

export function statusLabel(status: string, skipped: boolean, chosen: boolean): string {
  if (skipped) return "Skipped";
  if (chosen) return "Selected";
  if (status === "high") return "High confidence";
  if (status === "likely") return "Likely match";
  if (status === "review") return "Needs review";
  if (status === "none") return "No match";
  if (status === "error") return "Search failed";
  if (status === "searching") return "Searching";
  return "Waiting";
}
