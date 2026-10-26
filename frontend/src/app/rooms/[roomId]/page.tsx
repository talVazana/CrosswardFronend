"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import CrosswordGrid from "@/components/CrosswordGrid";
import ClueList from "@/components/ClueList";
import ParticipantList, { Participant } from "@/components/ParticipantList";
import Scoreboard from "@/components/Scoreboard";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import ErrorMessage from "@/components/ui/ErrorMessage";
import EmptyState from "@/components/ui/EmptyState";
import { subscribeRoom, type RoomDoc } from "@/lib/roomsStore";

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

  const [room, setRoom] = useState<RoomDoc | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showOriginal, setShowOriginal] = useState(false);
  const [playerProgress, setPlayerProgress] = useState<{
    solved: string[];
    revealed: string[];
  }>({ solved: [], revealed: [] });

  const loadPlayerProgress = useCallback(async () => {
    try {
      const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
      const res = await fetch(`${base}/rooms/${roomId}/player-progress`, {
        credentials: "include",
      });
      if (!res.ok) return;
      const body = (await res.json()) as {
        solved?: unknown;
        revealed?: unknown;
      };
      setPlayerProgress({
        solved: Array.isArray(body.solved)
          ? body.solved.filter((value): value is string => typeof value === "string")
          : [],
        revealed: Array.isArray(body.revealed)
          ? body.revealed.filter((value): value is string => typeof value === "string")
          : [],
      });
    } catch {
      // Progress is optional for visitors without a player session.
    }
  }, [roomId]);

  useEffect(() => {
    setLoading(true);
    setError(null);

    const unsubscribe = subscribeRoom(
      roomId,
      (doc) => {
        setLoading(false);
        if (!doc) {
          setRoom(null);
          setError("Room not found");
          return;
        }
        setRoom(doc);
        setError(null);
      },
      () => {
        setLoading(false);
        setError("Network error. Please try again.");
      },
    );

    return unsubscribe;
  }, [roomId]);

  useEffect(() => {
    void loadPlayerProgress();
  }, [loadPlayerProgress]);

  useEffect(() => {
    if (!showOriginal) return;
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") setShowOriginal(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [showOriginal]);

  const handleClueSolved = useCallback((clueId: string) => {
    setPlayerProgress((prev) =>
      prev.solved.includes(clueId)
        ? prev
        : { ...prev, solved: [...prev.solved, clueId] },
    );
  }, []);

  const handleClueRevealed = useCallback((clueId: string) => {
    setPlayerProgress((prev) =>
      prev.revealed.includes(clueId)
        ? prev
        : { ...prev, revealed: [...prev.revealed, clueId] },
    );
  }, []);

  const players: Participant[] = room?.players ?? [];
  const puzzle = room?.puzzle;
  const displayClues =
    puzzle?.displayClues && puzzle.displayClues.length > 0
      ? puzzle.displayClues
      : puzzle?.clues;
  const solvedCluesMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const entry of room?.solvedClues ?? []) {
      map[entry.clueId] = entry.firstSolverColor;
    }
    return map;
  }, [room?.solvedClues]);
  const statusLabel = room?.status
    ? (STATUS_LABELS[room.status] ?? room.status)
    : null;
  const playerSolvedClueIds = new Set(playerProgress.solved);
  const playerRevealedClueIds = new Set(playerProgress.revealed);

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
                initialSolvedClues={solvedCluesMap}
                onClueSolved={handleClueSolved}
                onClueRevealed={handleClueRevealed}
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
              <ClueList
                clues={displayClues ?? puzzle.clues}
                playerSolvedClueIds={playerSolvedClueIds}
                playerRevealedClueIds={playerRevealedClueIds}
              />
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
              <Scoreboard scores={room.scores} loading={loading} />
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
