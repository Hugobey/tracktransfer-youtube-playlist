export type MatchStatus = "pending" | "searching" | "high" | "likely" | "review" | "none" | "error";

export type ImportedTrack = {
  id: string;
  position: number;
  track_name: string;
  artist: string;
  artists: string;
  album: string;
  duration: string;
  duration_ms: number | null;
  duration_seconds: number | null;
  date_added: string;
  spotify_track_id: string;
  spotify_url: string;
  explicit: boolean | null;
  issues: string[];
};

export type CsvParseResponse = {
  filename: string;
  delimiter: string;
  track_count: number;
  tracks: ImportedTrack[];
};

export type Signal = {
  artist: number;
  title: number;
  version: number;
  duration: number;
  other: number;
};

export type Candidate = {
  video_id: string;
  title: string;
  artists: string[];
  album: string | null;
  duration_seconds: number | null;
  thumbnail_url: string | null;
  result_type: string | null;
  channel: string | null;
  score: number;
  signals: Signal;
  version: string | null;
  reasons: string[];
};

export type TrackMatch = {
  id: string;
  queries: string[];
  status: MatchStatus;
  selected_video_id: string | null;
  candidates: Candidate[];
  error: string | null;
};

export type Privacy = "PRIVATE" | "PUBLIC" | "UNLISTED";

export type PlaylistItem = {
  track_id: string;
  position: number;
  video_id: string;
  title: string;
  artist: string;
  status: "pending" | "added" | "failed" | "skipped";
  error: string | null;
};

export type PlaylistJob = {
  job_id: string;
  status: "failed" | "adding" | "blocked" | "partial" | "complete";
  title: string;
  description: string;
  privacy: Privacy;
  playlist_id: string | null;
  url: string | null;
  added: number;
  failed: number;
  pending: number;
  skipped: number;
  track_count: number;
  items: PlaylistItem[];
  error: string | null;
};

export type AuthStart = {
  status: "pending" | "authorized";
  verification_url: string | null;
  user_code: string | null;
  interval: number;
  expires_in: number;
};

export type AuthPoll = {
  status: "pending" | "authorized" | "expired" | "denied";
  interval: number;
};

export type AuthStatus = {
  configured: boolean;
  authorized: boolean;
};
