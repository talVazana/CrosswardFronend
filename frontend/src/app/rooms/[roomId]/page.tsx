"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import CrosswordGrid, {
  LiveRoomEvent,
  Puzzle,
} from "@/components/CrosswordGrid";
import ClueList from "@/components/ClueList";
import ParticipantList, { Participant } from "@/components/ParticipantList";
import Scoreboard from "@/components/Scoreboard";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import ErrorMessage from "@/components/ui/ErrorMessage";
import EmptyState from "@/components/ui/EmptyState";
import { useRoomLiveUpdates } from "@/hooks/useRoomLiveUpdates";

interface RoomState {
  roomId?: string;
  id?: string;
  title?: string;
  status?: string;
  players?: Participant[];
  participants?: Participant[];
  puzzle?: Puzzle;
  solvedClues?: { clueId: string; firstSolverColor: string }[];
}

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  lobby: "Lobby",
  active: "Active",
  paused: "Paused",
  finished: "Finished",
  closed: "Closed",
};

export default function RoomLobbyPage() {
  const params = useParams<{ roomId: string }>();
  const roomId = params.roomId;

  const [room, setRoom] = useState<RoomState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [liveEvent, setLiveEvent] = useState<LiveRoomEvent | null>(null);
  const [showOriginal, setShowOriginal] = useState(false);
  const solvedClueIdsRef = useRef<Set<string>>(new Set());

  const handleLiveEvent = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data as string) as Record<string, unknown>;
      if (event.type === "CLUE_SOLVED") {
        const clueId = data.clueId;
        const firstSolverColor = data.firstSolverColor;
        const points = data.points;
        if (
          typeof clueId !== "string" ||
          typeof firstSolverColor !== "string" ||
          typeof points !== "number"
        ) {
          return;
        }
        if (solvedClueIdsRef.current.has(clueId)) return;
        solvedClueIdsRef.current.add(clueId);
        setRoom((prev) => {
          if (!prev) return prev;
          const existing = prev.solvedClues ?? [];
          if (existing.some((entry) => entry.clueId === clueId)) return prev;
          return {
            ...prev,
            solvedClues: [...existing, { clueId, firstSolverColor }],
          };
        });
        setLiveEvent({
          type: "CLUE_SOLVED",
          clueId,
          firstSolverColor,
          points,
        });
      } else if (event.type === "ROOM_STATUS_CHANGED") {
        const status = data.status;
        if (typeof status !== "string") return;
        setRoom((prev) => (prev ? { ...prev, status } : { status }));
        setLiveEvent({ type: "ROOM_STATUS_CHANGED", status });
      }
    } catch {
      // ignore malformed events
    }
  }, []);

  const handleStateFetched = useCallback((state: unknown) => {
    if (state && typeof state === "object") {
      setRoom((prev) => ({ ...(prev ?? {}), ...(state as RoomState) }));
    }
  }, []);

  useRoomLiveUpdates({ roomId, onEvent: handleLiveEvent, onStateFetched: handleStateFetched });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
        const res = await fetch(`${base}/rooms/${roomId}/state`, {
          credentials: "include",
        });
        if (cancelled) return;
        if (res.status === 404) {
          setError("Room not found");
          return;
        }
        if (!res.ok) {
          setError(`Failed to load room (status ${res.status})`);
          return;
        }
        const body = (await res.json()) as RoomState;
        if (cancelled) return;
        setRoom(body);
      } catch {
        if (!cancelled) {
          setError("Network error. Please try again.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [roomId]);

  useEffect(() => {
    if (!showOriginal) return;
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") setShowOriginal(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [showOriginal]);

  const players = room?.players ?? room?.participants ?? [];
  const puzzle = room?.puzzle;
  const solvedCluesMap = (room?.solvedClues ?? []).reduce<Record<string, string>>(
    (acc, entry) => {
      acc[entry.clueId] = entry.firstSolverColor;
      return acc;
    },
    {},
  );
  const statusLabel = room?.status
    ? (STATUS_LABELS[room.status] ?? room.status)
    : null;
  const solvedClueIdSet = new Set(Object.keys(solvedCluesMap));

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-6 overflow-x-hidden p-6">
      {loading ? (
        <LoadingSpinner />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : room ? (
        <>
          <header className="glass flex flex-wrap items-center justify-between gap-3 px-6 py-4">
            <div className="flex flex-col gap-2">
              <h1 className="brand text-2xl">{room.title ?? "Crossword"}</h1>
              {statusLabel ? (
                <span className="inline-flex w-fit items-center gap-2 rounded-full bg-blue-100/70 px-3 py-1 text-sm font-medium text-blue-700">
                  <span className="inline-block h-2 w-2 rounded-full bg-blue-500" />
                  {statusLabel}
                </span>
              ) : null}
            </div>
            <Link href="/" className="btn-ghost shrink-0 text-sm">
              Home
            </Link>
          </header>
          <section className="glass flex flex-col gap-2 px-6 py-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-semibold text-blue-800">Puzzle</h2>
              {puzzle ? (
                <button
                  type="button"
                  onClick={() => setShowOriginal(true)}
                  className="btn-ghost text-sm"
                >
                  Show original image
                </button>
              ) : null}
            </div>
            {puzzle ? (
              <CrosswordGrid
                roomId={roomId}
                puzzle={puzzle}
                roomStatus={room.status}
                liveEvent={liveEvent}
                initialSolvedClues={solvedCluesMap}
              />
            ) : (
              <EmptyState
                title="No puzzle loaded"
                message="The host has not attached a puzzle to this room yet."
              />
            )}
          </section>
          {puzzle ? (
            <section className="glass flex flex-col gap-2 px-6 py-4">
              <h2 className="text-lg font-semibold text-blue-800">Clues</h2>
              <ClueList clues={puzzle.clues} solvedClueIds={solvedClueIdSet} />
            </section>
          ) : null}
          <div className="grid gap-6 md:grid-cols-2">
            <section className="glass flex flex-col gap-2 px-6 py-4">
              <h2 className="text-lg font-semibold text-blue-800">Participants</h2>
              {players.length === 0 ? (
                <EmptyState
                  title="No participants yet"
                  message="Players will appear here once they join the room."
                />
              ) : (
                <ParticipantList players={players} />
              )}
            </section>
            <section className="glass flex flex-col gap-2 px-6 py-4">
              <h2 className="text-lg font-semibold text-blue-800">Scoreboard</h2>
              <Scoreboard roomId={roomId} />
            </section>
          </div>
          {showOriginal ? (
            <div
              role="dialog"
              aria-modal="true"
              aria-label="Original puzzle image"
              className="fixed inset-0 z-50 flex items-center justify-center bg-blue-950/60 p-4 backdrop-blur-sm"
              onClick={() => setShowOriginal(false)}
            >
              <div
                className="glass-strong flex max-h-[92vh] w-full max-w-3xl flex-col gap-3 p-4"
                onClick={(event) => event.stopPropagation()}
              >
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-lg font-semibold text-blue-900">Original puzzle</h2>
                  <button
                    type="button"
                    onClick={() => setShowOriginal(false)}
                    className="btn-ghost text-sm"
                  >
                    Close
                  </button>
                </div>
                <div className="min-h-0 flex-1 overflow-auto">
                  <img
                    src="/puzzle-source.jpg"
                    alt="Original published crossword page for this room"
                    className="mx-auto h-auto w-full rounded-lg"
                  />
                </div>
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </main>
  );
}
