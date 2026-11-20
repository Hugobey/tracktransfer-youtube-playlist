import type {
  AuthPoll,
  AuthStart,
  AuthStatus,
  CsvParseResponse,
  PlaylistJob,
  Privacy,
  TrackMatch,
} from "@/types/api";

export class ApiError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError("offline", "The TrackTransfer server is not running. Start the Python backend on port 8000.");
  }
  const data = (await response.json().catch(() => null)) as { error?: { code?: string; message?: string } } | null;
  if (!response.ok) {
    throw new ApiError(data?.error?.code ?? "request_failed", data?.error?.message ?? "The request failed.");
  }
  return data as T;
}

export function parseCsv(filename: string, content: string) {
  return request<CsvParseResponse>("/api/csv/parse", {
    method: "POST",
    body: JSON.stringify({ filename, content }),
  });
}

export function searchBatch(tracks: object[]) {
  return request<{ results: TrackMatch[] }>("/api/search/batch", {
    method: "POST",
    body: JSON.stringify({ tracks }),
  });
}

export function searchOne(track: object, query: string) {
  return request<TrackMatch>("/api/search", {
    method: "POST",
    body: JSON.stringify({ track, query }),
  });
}

export function authStatus() {
  return request<AuthStatus>("/api/auth/status");
}

export function authStart() {
  return request<AuthStart>("/api/auth/start", { method: "POST", body: "{}" });
}

export function authPoll() {
  return request<AuthPoll>("/api/auth/poll", { method: "POST", body: "{}" });
}

export function createPlaylist(body: {
  job_id: string;
  title: string;
  description: string;
  privacy: Privacy;
  tracks: { track_id: string; position: number; video_id: string; title: string; artist: string }[];
}) {
  return request<PlaylistJob>("/api/playlist/create", { method: "POST", body: JSON.stringify(body) });
}

export function addTracks(jobId: string, skipTrackIds: string[] = []) {
  return request<PlaylistJob>("/api/playlist/add-tracks", {
    method: "POST",
    body: JSON.stringify({ job_id: jobId, skip_track_ids: skipTrackIds }),
  });
}

export function playlistStatus(jobId: string) {
  return request<PlaylistJob>(`/api/playlist/status/${jobId}`);
}
