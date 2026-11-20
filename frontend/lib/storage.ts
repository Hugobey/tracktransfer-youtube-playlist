import type { ImportedTrack, PlaylistJob, Privacy, TrackMatch } from "@/types/api";

export const STORAGE_KEY = "tracktransfer.youtube.v1";

export type Selection = {
  videoId: string;
  source: "auto" | "user";
};

export type SessionState = {
  version: 1;
  filename: string;
  tracks: ImportedTrack[];
  matches: Record<string, TrackMatch>;
  selections: Record<string, Selection>;
  skipped: string[];
  playlistTitle: string;
  playlistDescription: string;
  privacy: Privacy;
  jobId: string | null;
  playlistResult: PlaylistJob | null;
};

export function emptySession(): SessionState {
  return {
    version: 1,
    filename: "",
    tracks: [],
    matches: {},
    selections: {},
    skipped: [],
    playlistTitle: "",
    playlistDescription: "Transferred from Spotify with TrackTransfer.",
    privacy: "PRIVATE",
    jobId: null,
    playlistResult: null,
  };
}

export function loadSession(): SessionState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as SessionState;
    if (parsed.version !== 1 || !Array.isArray(parsed.tracks)) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveSession(state: SessionState): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // The transfer still works in memory if the browser refuses the write.
  }
}

export function clearSession(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore a storage failure while resetting the page.
  }
}
