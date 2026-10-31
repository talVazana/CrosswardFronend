"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import CrosswordGrid, {
  type ClueSelectionRequest,
} from "@/components/CrosswordGrid";
import ClueList from "@/components/ClueList";
import Scoreboard from "@/components/Scoreboard";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import ErrorMessage from "@/components/ui/ErrorMessage";
import EmptyState from "@/components/ui/EmptyState";
import { subscribeRoom, type RoomDoc } from "@/lib/roomsStore";
import { roomFetch } from "@/lib/roomSession";

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
  const [clueSelection, setClueSelection] =
    useState<ClueSelectionRequest | null>(null);
  const [activeClueId, setActiveClueId] = useState<string | null>(null);
  const [needsJoin, setNeedsJoin] = useState(false);
  const [playerProgress, setPlayerProgress] = useState<{
    solved: string[];
    revealed: string[];
    answers: Record<string, string>;
    pending: string[];
    rejected: { clueId: string; submissionId: string }[];
  }>({ solved: [], revealed: [], answers: {}, pending: [], rejected: [] });
  const [me, setMe] = useState<{
    playerId: string;
    displayName: string;
    color: string;
  } | null>(null);

  const loadPlayerProgress = useCallback(async () => {
    try {
      const res = await roomFetch(roomId, `/rooms/${roomId}/player-progress`);
      if (!res.ok) return;
      const body = (await res.json()) as {
        solved?: unknown;
        revealed?: unknown;
        answers?: unknown;
        pending?: unknown;
        rejected?: unknown;
      };
      const rejected: { clueId: string; submissionId: string }[] = Array.isArray(
        body.rejected,
      )
        ? body.rejected.flatMap((entry) => {
            if (
              entry &&
              typeof entry === "object" &&
              typeof (entry as { clueId?: unknown }).clueId === "string" &&
              typeof (entry as { submissionId?: unknown }).submissionId === "string"
            ) {
              return [
                {
                  clueId: (entry as { clueId: string }).clueId,
                  submissionId: (entry as { submissionId: string }).submissionId,
                },
              ];
            }
            return [];
          })
        : [];
      setPlayerProgress({
        solved: Array.isArray(body.solved)
          ? body.solved.filter((value): value is string => typeof value === "string")
          : [],
        revealed: Array.isArray(body.revealed)
          ? body.revealed.filter((value): value is string => typeof value === "string")
          : [],
        answers:
          body.answers && typeof body.answers === "object"
            ? Object.fromEntries(
                Object.entries(body.answers as Record<string, unknown>).filter(
                  (entry): entry is [string, string] => typeof entry[1] === "string",
                ),
              )
            : {},
        pending: Array.isArray(body.pending)
          ? body.pending.filter((value): value is string => typeof value === "string")
          : [],
        rejected,
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
    const interval = window.setInterval(() => {
      if (document.visibilityState === "visible") void loadPlayerProgress();
    }, 5000);
    return () => window.clearInterval(interval);
  }, [loadPlayerProgress]);

  useEffect(() => {
    let cancelled = false;
    const loadMe = async () => {
      try {
        const res = await roomFetch(roomId, `/rooms/${roomId}/me`);
        if (cancelled) return;
        if (res.status === 401) {
          setMe(null);
          setNeedsJoin(true);
          return;
        }
        if (!res.ok) return;
        const body = (await res.json()) as {
          playerId?: unknown;
          displayName?: unknown;
          color?: unknown;
        };
        if (cancelled) return;
        if (
          typeof body.playerId === "string" &&
          typeof body.displayName === "string" &&
          typeof body.color === "string"
        ) {
          setMe({
            playerId: body.playerId,
            displayName: body.displayName,
            color: body.color,
          });
          setNeedsJoin(false);
        }
      } catch {
        // Visitors without a player session have no identity to show.
      }
    };
    void loadMe();
    const refresh = () => void loadMe();
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      cancelled = true;
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
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

  const handleSelectClue = useCallback((clue: { clueId: string }) => {
    setClueSelection((prev) => ({
      clueId: clue.clueId,
      nonce: (prev?.nonce ?? 0) + 1,
    }));
  }, []);

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
  const playerScores = useMemo(() => {
    const scoresByKey = new Map(
      (room?.scores ?? []).map((entry) => [entry.playerId, entry.totalPoints]),
    );
    const result: {
      playerId: string;
      displayName: string;
      color: string;
      totalPoints: number;
    }[] = [];
    const seen = new Set<string>();
    for (const player of room?.players ?? []) {
      seen.add(player.id);
      result.push({
        playerId: player.id,
        displayName: player.displayName,
        color: player.color,
        totalPoints: scoresByKey.get(player.id) ?? 0,
      });
    }
    for (const score of room?.scores ?? []) {
      if (!seen.has(score.playerId)) result.push(score);
    }
    return result;
  }, [room?.players, room?.scores]);
  const statusLabel = room?.status
    ? (STATUS_LABELS[room.status] ?? room.status)
    : null;
  const playerSolvedClueIds = new Set(playerProgress.solved);
  const playerRevealedClueIds = new Set(playerProgress.revealed);
  const myColor = me
    ? (room?.players ?? []).find((player) => player.id === me.playerId)?.color ??
      me.color
    : null;

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
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="brand text-2xl">{room.title ?? "Crossword"}</h1>
                {me ? (
                  <span
                    data-testid="player-identity"
                    className="inline-flex items-center gap-2 rounded-full bg-white/70 px-3 py-1 text-sm font-medium text-blue-900"
                  >
                    <span
                      data-testid="player-identity-color"
                      className="inline-block h-3 w-3 rounded-full border border-blue-900/20"
                      style={{ backgroundColor: myColor ?? me.color }}
                    />
                    {me.displayName}
                  </span>
                ) : null}
              </div>
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
          {needsJoin ? (
            <section className="glass-soft flex flex-wrap items-center gap-2 px-4 py-3 text-sm text-blue-900">
              <span>You are viewing as a guest.</span>
              <Link
                href={`/rooms/${roomId}/join`}
                className="btn-ghost text-sm"
              >
                Join the room
              </Link>
              <span>to submit answers.</span>
            </section>
          ) : null}
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
                initialAnswers={playerProgress.answers}
                playerSolvedClues={playerProgress.solved}
                playerPendingClues={playerProgress.pending}
                playerRejected={playerProgress.rejected}
                selectionRequest={clueSelection}
                onActiveClueChange={setActiveClueId}
                onUnauthorized={() => setNeedsJoin(true)}
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
                activeClueId={activeClueId}
                playerSolvedClueIds={playerSolvedClueIds}
                playerRevealedClueIds={playerRevealedClueIds}
                onSelectClue={handleSelectClue}
              />
            </section>
          ) : null}
          <section className="glass flex flex-col gap-2 px-6 py-4">
            <h2 className="text-lg font-semibold text-blue-800">Players</h2>
            {playerScores.length === 0 ? (
              <EmptyState
                title="No participants yet"
                message="Players will appear here once they join the room."
              />
            ) : (
              <Scoreboard scores={playerScores} loading={loading} />
            )}
          </section>
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
                    src={`${process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"}/rooms/${roomId}/image`}
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
