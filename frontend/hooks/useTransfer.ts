"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  addTracks,
  ApiError,
  authPoll,
  authStart,
  authStatus,
  createPlaylist,
  parseCsv,
  playlistStatus,
  searchBatch,
  searchOne,
} from "@/lib/api";
import { playlistTitleFromFilename } from "@/lib/format";
import { clearSession, emptySession, loadSession, saveSession, type Selection, type SessionState } from "@/lib/storage";
import type { AuthStart, ImportedTrack, PlaylistJob, Privacy, TrackMatch } from "@/types/api";

export type ReviewFilter = "all" | "high" | "review" | "none" | "skipped";

function trackQuery(track: ImportedTrack) {
  return {
    id: track.id,
    position: track.position,
    track_name: track.track_name,
    artist: track.artist,
    artists: track.artists,
    album: track.album,
    duration_ms: track.duration_ms,
    duration_seconds: track.duration_seconds,
  };
}

function chunks<T>(items: T[], size: number): T[][] {
  const groups: T[][] = [];
  for (let index = 0; index < items.length; index += size) groups.push(items.slice(index, index + size));
  return groups;
}

export function useTransfer() {
  const [ready, setReady] = useState(false);
  const [state, setState] = useState<SessionState>(emptySession);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [authorized, setAuthorized] = useState(false);
  const [authConfigured, setAuthConfigured] = useState(true);
  const [connect, setConnect] = useState<AuthStart | null>(null);
  const [creating, setCreating] = useState(false);
  const stateRef = useRef(state);
  const generation = useRef(0);
  const startedKey = useRef<string | null>(null);

  const commit = useCallback((next: SessionState) => {
    stateRef.current = next;
    setState(next);
    saveSession(next);
  }, []);

  const patch = useCallback(
    (recipe: (current: SessionState) => SessionState) => {
      commit(recipe(stateRef.current));
    },
    [commit],
  );

  const applyMatch = useCallback(
    (result: TrackMatch, preserveUser: boolean) => {
      patch((current) => {
        const selections = { ...current.selections };
        const existing = selections[result.id];
        if (result.selected_video_id && (!existing || (existing.source === "auto" && !preserveUser))) {
          selections[result.id] = { videoId: result.selected_video_id, source: "auto" };
        } else if (!result.selected_video_id && existing?.source === "auto" && !preserveUser) {
          delete selections[result.id];
        }
        return { ...current, matches: { ...current.matches, [result.id]: result }, selections };
      });
    },
    [patch],
  );

  const runSearch = useCallback(
    async (ids?: string[]) => {
      if (!ids) generation.current += 1;
      const runId = generation.current;
      const current = stateRef.current;
      const wanted = new Set(ids);
      const targets = current.tracks.filter((track) => {
        if (ids && !wanted.has(track.id)) return false;
        const match = current.matches[track.id];
        if (ids) return true;
        return !match || match.status === "pending" || match.status === "searching" || match.status === "error";
      });
      if (targets.length === 0) return;
      setSearching(true);
      setSearched(current.tracks.length - targets.length);
      setError(null);
      let done = current.tracks.length - targets.length;
      try {
        for (const group of chunks(targets, 20)) {
          if (generation.current !== runId) return;
          patch((snapshot) => {
            const matches = { ...snapshot.matches };
            for (const track of group) {
              matches[track.id] = {
                id: track.id,
                queries: [],
                status: "searching",
                selected_video_id: null,
                candidates: matches[track.id]?.candidates ?? [],
                error: null,
              };
            }
            return { ...snapshot, matches };
          });
          const response = await searchBatch(group.map(trackQuery));
          if (generation.current !== runId) return;
          for (const result of response.results) applyMatch(result, false);
          done += group.length;
          setSearched(done);
        }
      } catch (caught) {
        if (generation.current !== runId) return;
        const message = caught instanceof ApiError ? caught.message : "Search failed.";
        setError(message);
        patch((snapshot) => {
          const matches = { ...snapshot.matches };
          for (const track of targets) {
            if (matches[track.id]?.status === "searching") {
              matches[track.id] = { ...matches[track.id], status: "error", error: message };
            }
          }
          return { ...snapshot, matches };
        });
      } finally {
        if (generation.current === runId) setSearching(false);
      }
    },
    [applyMatch, patch],
  );

  useEffect(() => {
    const saved = loadSession();
    if (saved && stateRef.current.tracks.length === 0 && !stateRef.current.filename) {
      stateRef.current = saved;
      setState(saved);
    }
    setReady(true);
    void authStatus()
      .then((status) => {
        setAuthorized(status.authorized);
        setAuthConfigured(status.configured);
      })
      .catch(() => setAuthConfigured(true));
  }, []);

  useEffect(() => {
    if (!ready || state.tracks.length === 0) return;
    const key = `${state.filename}:${state.tracks.length}:${state.tracks[0]?.id ?? ""}`;
    if (startedKey.current === key) return;
    startedKey.current = key;
    const needs = stateRef.current.tracks.some((track) => {
      const match = stateRef.current.matches[track.id];
      return !match || match.status === "pending" || match.status === "searching";
    });
    if (needs) void runSearch();
  }, [ready, state.filename, state.tracks, runSearch]);

  useEffect(() => () => {
    generation.current += 1;
  }, []);

  useEffect(() => {
    if (!ready || !state.jobId) return;
    void playlistStatus(state.jobId)
      .then((job) => patch((current) => ({ ...current, playlistResult: job })))
      .catch(() => undefined);
  }, [ready, state.jobId, patch]);

  const importFile = useCallback(
    async (file: File) => {
      setError(null);
      if (file.size > 2_000_000) {
        setError("That CSV is larger than 2 MB.");
        return;
      }
      const content = await file.text();
      try {
        const parsed = await parseCsv(file.name, content);
        generation.current += 1;
        const next: SessionState = {
          ...emptySession(),
          filename: parsed.filename || file.name,
          tracks: parsed.tracks,
          playlistTitle: playlistTitleFromFilename(parsed.filename || file.name),
        };
        startedKey.current = null;
        commit(next);
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : "The CSV could not be read.");
      }
    },
    [commit],
  );

  const reset = useCallback(() => {
    generation.current += 1;
    startedKey.current = null;
    clearSession();
    const next = emptySession();
    stateRef.current = next;
    setState(next);
    setError(null);
    setConnect(null);
    setCreating(false);
    setSearching(false);
  }, []);

  const selectCandidate = useCallback(
    (trackId: string, videoId: string) => {
      patch((current) => ({
        ...current,
        skipped: current.skipped.filter((id) => id !== trackId),
        selections: { ...current.selections, [trackId]: { videoId, source: "user" } satisfies Selection },
      }));
    },
    [patch],
  );

  const toggleSkip = useCallback(
    (trackId: string) => {
      patch((current) => {
        const skipped = current.skipped.includes(trackId)
          ? current.skipped.filter((id) => id !== trackId)
          : [...current.skipped, trackId];
        return { ...current, skipped };
      });
    },
    [patch],
  );

  const skipUnresolved = useCallback(() => {
    patch((current) => {
      const skipped = new Set(current.skipped);
      for (const track of current.tracks) {
        if (skipped.has(track.id) || current.selections[track.id]) continue;
        const status = current.matches[track.id]?.status;
        if (status === "likely" || status === "review" || status === "none" || status === "error") {
          skipped.add(track.id);
        }
      }
      return { ...current, skipped: current.tracks.map((track) => track.id).filter((id) => skipped.has(id)) };
    });
  }, [patch]);

  const manualSearch = useCallback(
    async (trackId: string, text: string) => {
      const track = stateRef.current.tracks.find((item) => item.id === trackId);
      if (!track) return;
      setError(null);
      try {
        const result = await searchOne(trackQuery(track), text);
        applyMatch(result, true);
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : "Search failed.");
      }
    },
    [applyMatch],
  );

  const connectAccount = useCallback(async () => {
    setError(null);
    try {
      const started = await authStart();
      if (started.status === "authorized") {
        setAuthorized(true);
        setConnect(null);
        setAuthConfigured(true);
        return true;
      }
      setConnect(started);
      let interval = started.interval || 5;
      for (let attempt = 0; attempt < 40; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, interval * 1000));
        const polled = await authPoll();
        if (polled.status === "authorized") {
          setAuthorized(true);
          setConnect(null);
          return true;
        }
        if (polled.status === "expired") {
          setError("The sign-in code expired. Connect again.");
          setConnect(null);
          return false;
        }
        if (polled.status === "denied") {
          setError("YouTube Music sign-in was declined.");
          setConnect(null);
          return false;
        }
        interval = polled.interval || interval;
      }
      setError("YouTube Music sign-in is still waiting. Connect again if the code expired.");
      return false;
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "YouTube Music sign-in failed.";
      if (caught instanceof ApiError && caught.code === "auth_not_configured") setAuthConfigured(false);
      setError(message);
      setConnect(null);
      return false;
    }
  }, []);

  const pushUntilSettled = useCallback(
    async (job: PlaylistJob) => {
      let current = job;
      while (current.status === "adding") {
        current = await addTracks(current.job_id);
        patch((snapshot) => ({ ...snapshot, playlistResult: current, jobId: current.job_id }));
      }
      return current;
    },
    [patch],
  );

  const create = useCallback(async () => {
    const current = stateRef.current;
    const chosen = current.tracks.filter((track) => !current.skipped.includes(track.id) && current.selections[track.id]);
    if (chosen.length === 0) {
      setError("Select at least one track.");
      return;
    }
    setCreating(true);
    setError(null);
    try {
      const status = await authStatus();
      setAuthConfigured(status.configured);
      setAuthorized(status.authorized);
      if (!status.configured || !status.authorized) {
        const ok = await connectAccount();
        if (!ok) return;
      }
      const jobId = current.jobId ?? crypto.randomUUID();
      patch((snapshot) => ({ ...snapshot, jobId }));
      const created = await createPlaylist({
        job_id: jobId,
        title: current.playlistTitle.trim(),
        description: current.playlistDescription,
        privacy: current.privacy,
        tracks: chosen.flatMap((track) => {
          const selection = current.selections[track.id];
          if (!selection) return [];
          return [
            {
              track_id: track.id,
              position: track.position,
              video_id: selection.videoId,
              title: track.track_name,
              artist: track.artist,
            },
          ];
        }),
      });
      patch((snapshot) => ({ ...snapshot, jobId, playlistResult: created }));
      await pushUntilSettled(created);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The playlist could not be created.");
    } finally {
      setCreating(false);
    }
  }, [connectAccount, patch, pushUntilSettled]);

  const retry = useCallback(
    async (skipFailed: boolean) => {
      const current = stateRef.current;
      if (!current.jobId) return;
      setCreating(true);
      setError(null);
      try {
        const skip = skipFailed
          ? (current.playlistResult?.items ?? []).filter((item) => item.status === "failed").map((item) => item.track_id)
          : [];
        const job = await addTracks(current.jobId, skip);
        patch((snapshot) => ({ ...snapshot, playlistResult: job }));
        await pushUntilSettled(job);
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : "The retry failed.");
      } finally {
        setCreating(false);
      }
    },
    [patch, pushUntilSettled],
  );

  const counts = useMemo(() => {
    const skipped = new Set(state.skipped);
    let matched = 0;
    let review = 0;
    let missing = 0;
    for (const track of state.tracks) {
      if (skipped.has(track.id)) continue;
      if (state.selections[track.id]) matched += 1;
      const status = state.matches[track.id]?.status;
      if (!state.selections[track.id] && (status === "likely" || status === "review")) review += 1;
      if (!state.selections[track.id] && (status === "none" || status === "error")) missing += 1;
    }
    return { matched, review, missing, skipped: skipped.size, total: state.tracks.length };
  }, [state]);

  return {
    ready,
    state,
    searching,
    searched,
    error,
    authorized,
    authConfigured,
    connect,
    creating,
    counts,
    importFile,
    reset,
    runSearch,
    selectCandidate,
    toggleSkip,
    skipUnresolved,
    manualSearch,
    create,
    retry,
    setPlaylistTitle: (playlistTitle: string) => patch((current) => ({ ...current, playlistTitle })),
    setPlaylistDescription: (playlistDescription: string) => patch((current) => ({ ...current, playlistDescription })),
    setPrivacy: (privacy: Privacy) => patch((current) => ({ ...current, privacy })),
    dismissError: () => setError(null),
  };
}
