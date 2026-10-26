"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import AdminCrossword from "@/components/AdminCrossword";
import ClueList from "@/components/ClueList";
import ParticipantList, { Participant } from "@/components/ParticipantList";
import Scoreboard from "@/components/Scoreboard";
import type { Puzzle } from "@/components/CrosswordGrid";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import ErrorMessage from "@/components/ui/ErrorMessage";
import EmptyState from "@/components/ui/EmptyState";

type RoomStatus = "draft" | "lobby" | "active" | "paused" | "finished" | "closed";

type LifecycleAction = "start" | "pause" | "resume" | "finish" | "close";

interface PendingSubmission {
  clueId?: string;
  playerId?: string;
  answer?: string;
}

interface ScoreEntry {
  playerId?: string;
  score?: number;
}

interface AdminRoomState {
  roomId?: string;
  id?: string;
  title?: string;
  status?: RoomStatus | string;
  puzzleId?: string;
  puzzle?: Puzzle;
  officialAnswers?: Record<string, string>;
  solvedClues?: { clueId: string; firstSolverColor: string }[];
  players?: Participant[];
  participants?: Participant[];
  pendingSubmissions?: PendingSubmission[];
  pending?: PendingSubmission[];
  scores?: ScoreEntry[];
}

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  lobby: "Lobby",
  active: "Active",
  paused: "Paused",
  finished: "Finished",
  closed: "Closed",
};

const ACTION_LABELS: Record<LifecycleAction, string> = {
  start: "Start",
  pause: "Pause",
  resume: "Resume",
  finish: "Finish",
  close: "Close",
};

const CONFIRM_ACTIONS: ReadonlySet<LifecycleAction> = new Set<LifecycleAction>(["finish", "close"]);

function allowedActions(status: string | undefined): LifecycleAction[] {
  switch (status) {
    case "lobby":
      return ["start"];
    case "active":
      return ["pause", "finish"];
    case "paused":
      return ["resume", "finish"];
    case "finished":
      return ["close"];
    default:
      return [];
  }
}

export default function AdminRoomDashboardPage() {
  const params = useParams<{ roomId: string }>();
  const roomId = params.roomId;

  const [room, setRoom] = useState<AdminRoomState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unauthorized, setUnauthorized] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState<LifecycleAction | null>(null);
  const [approving, setApproving] = useState<string | null>(null);
  const lastActionRef = useRef<LifecycleAction | null>(null);

  const load = useCallback(async (showSpinner = true) => {
    if (showSpinner) setLoading(true);
    setError(null);
    try {
      const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
      const res = await fetch(`${base}/admin/rooms/${roomId}`, {
        credentials: "include",
      });
      if (res.status === 401 || res.status === 403) {
        setUnauthorized(true);
        return;
      }
      if (res.status === 404) {
        let stateRes = await fetch(`${base}/rooms/${roomId}/state`, {
          credentials: "include",
        });
        if (!stateRes.ok) {
          setError("Room not found");
          return;
        }
        setRoom((await stateRes.json()) as AdminRoomState);
        return;
      }
      if (!res.ok) {
        setError(`Failed to load room (status ${res.status})`);
        return;
      }
      setRoom((await res.json()) as AdminRoomState);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      if (showSpinner) setLoading(false);
    }
  }, [roomId]);

  useEffect(() => {
    load();
  }, [load]);

  const triggerAction = useCallback(
    async (action: LifecycleAction) => {
      if (CONFIRM_ACTIONS.has(action)) {
        const confirmed = window.confirm(
          `Are you sure you want to ${action} this room? This action cannot be undone.`
        );
        if (!confirmed) return;
      }
      lastActionRef.current = action;
      setBusy(action);
      setActionError(null);
      try {
        const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
        const res = await fetch(`${base}/admin/rooms/${roomId}/${action}`, {
          method: "POST",
          credentials: "include",
        });
        if (res.ok) {
          await load();
        } else {
          setActionError(`Failed to ${action} room (status ${res.status})`);
        }
      } catch {
        setActionError("Network error. Please try again.");
      } finally {
        setBusy(null);
      }
    },
    [roomId, load]
  );

  const approveSubmission = useCallback(
    async (submission: PendingSubmission, index: number) => {
      if (!submission.clueId || !submission.answer) return;
      if (!room?.puzzleId) {
        setActionError("Room puzzle is unavailable");
        return;
      }

      const confirmed = window.confirm(
        `Approve clue ${submission.clueId} with answer "${submission.answer}"? This scores matching submissions and colors the clue for every player.`,
      );
      if (!confirmed) return;

      const key = `${submission.clueId}:${submission.playerId ?? "unknown"}:${index}`;
      setApproving(key);
      setActionError(null);
      try {
        const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
        const res = await fetch(
          `${base}/admin/puzzles/${room.puzzleId}/clues/${submission.clueId}/answer`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ answer: submission.answer }),
          },
        );
        if (!res.ok) {
          setActionError(`Failed to approve clue (status ${res.status})`);
          return;
        }
        await load();
      } catch {
        setActionError("Network error. Please try again.");
      } finally {
        setApproving(null);
      }
    },
    [room?.puzzleId, load],
  );

  const status = room?.status;
  const statusLabel = status ? (STATUS_LABELS[status] ?? status) : null;
  const players = room?.players ?? room?.participants ?? [];
  const pendingSubmissions = room?.pendingSubmissions ?? room?.pending ?? [];
  const scores = room?.scores ?? [];
  const publicScores = (room?.players ?? room?.participants ?? []).map((player) => {
    const id = player.playerId ?? player.id;
    const match = (room?.scores ?? []).find((entry) => entry.playerId === id);
    return {
      playerId: id,
      displayName: player.displayName,
      color: player.color,
      totalPoints: match?.score ?? 0,
    };
  });
  const actions = allowedActions(status);
  const solvedClues = (room?.solvedClues ?? []).reduce<Record<string, string>>(
    (acc, entry) => {
      acc[entry.clueId] = entry.firstSolverColor;
      return acc;
    },
    {},
  );
  const puzzle = room?.puzzle;
  const displayClues =
    puzzle?.displayClues && puzzle.displayClues.length > 0
      ? puzzle.displayClues
      : puzzle?.clues ?? [];
  const solvedClueIds = new Set(Object.keys(solvedClues));

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-6 p-6">
      {loading ? (
        <LoadingSpinner />
      ) : unauthorized ? (
        <section className="glass flex flex-col gap-3 px-6 py-8">
          <h1 className="text-2xl font-semibold text-blue-900">Admin sign-in required</h1>
          <p className="muted text-sm">
            This dashboard is only available to administrators. Sign in with the
            admin session token to continue.
          </p>
          <Link href="/admin/rooms" className="btn-primary w-fit text-sm">
            Go to admin entry
          </Link>
        </section>
      ) : error ? (
        <ErrorMessage message={error} onRetry={load} />
      ) : room ? (
        <>
          <header className="glass flex flex-wrap items-center justify-between gap-3 px-6 py-4">
            <div className="flex flex-col gap-2">
              <h1 className="brand text-2xl">{room.title ?? "Admin Dashboard"}</h1>
              {statusLabel ? (
                <span className="inline-flex w-fit items-center gap-2 rounded-full bg-blue-100/70 px-3 py-1 text-sm font-medium text-blue-700">
                  <span className="inline-block h-2 w-2 rounded-full bg-blue-500" />
                  {statusLabel}
                </span>
              ) : null}
            </div>
            <div className="flex shrink-0 gap-2">
              <button
                type="button"
                onClick={() => void load(false)}
                disabled={loading}
                className="btn-ghost text-sm"
              >
                Refresh
              </button>
              <Link href="/admin/rooms" className="btn-ghost text-sm">
                All rooms
              </Link>
              <Link href="/" className="btn-ghost text-sm">
                Home
              </Link>
            </div>
          </header>

          <section className="glass flex flex-col gap-3 px-6 py-4" aria-label="Room controls">
            <h2 className="text-lg font-semibold text-blue-800">Controls</h2>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(ACTION_LABELS) as LifecycleAction[]).map((action) => {
                const enabled = actions.includes(action);
                return (
                  <button
                    key={action}
                    type="button"
                    disabled={!enabled || busy !== null}
                    onClick={() => triggerAction(action)}
                    className="btn-ghost text-sm"
                  >
                    {ACTION_LABELS[action]}
                  </button>
                );
              })}
            </div>
            {actionError ? (
              <ErrorMessage
                title="Action failed"
                message={actionError}
                onRetry={() => triggerAction(lastActionRef.current ?? "start")}
                className="text-sm"
              />
            ) : null}
          </section>

          {room.puzzle ? (
            <section className="glass flex flex-col gap-3 px-6 py-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-lg font-semibold text-blue-800">Crossword</h2>
                  <p className="muted text-xs">
                    Admin draft. Approving an answer lets players solve it automatically.
                  </p>
                </div>
              </div>
              <AdminCrossword
                puzzle={room.puzzle}
                solvedClues={solvedClues}
                officialAnswers={room.officialAnswers}
                onApproved={() => load(false)}
              />
            </section>
          ) : null}

          {displayClues.length > 0 ? (
            <section className="glass flex flex-col gap-2 px-6 py-4">
              <h2 className="text-lg font-semibold text-blue-800">Clues</h2>
              <ClueList clues={displayClues} solvedClueIds={solvedClueIds} />
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
              <Scoreboard scores={publicScores} />
            </section>
          </div>

          <section className="glass flex flex-col gap-2 px-6 py-4">
            <h2 className="text-lg font-semibold text-blue-800">Pending Submissions</h2>
            {pendingSubmissions.length === 0 ? (
              <EmptyState
                title="No pending submissions"
                message="Submitted answers waiting for review will appear here."
              />
            ) : (
              <ul className="flex flex-col gap-1" aria-label="Pending submissions">
                {pendingSubmissions.map((submission, index) => {
                  const key = `${submission.clueId ?? "?"}:${submission.playerId ?? "unknown"}:${index}`;
                  const playerName =
                    players.find(
                      (player) =>
                        (player.playerId ?? player.id) === submission.playerId,
                    )?.displayName ??
                    submission.playerId ??
                    "Unknown player";
                  return (
                    <li
                      key={key}
                      className="glass-soft flex flex-wrap items-center gap-3 px-3 py-2 text-sm text-blue-900"
                    >
                      <span className="min-w-0 flex-1">
                        {playerName} - clue {submission.clueId ?? "?"}
                        {submission.answer ? `: ${submission.answer}` : ""}
                      </span>
                      <button
                        type="button"
                        onClick={() => void approveSubmission(submission, index)}
                        disabled={
                          approving !== null ||
                          !room.puzzleId ||
                          !submission.clueId ||
                          !submission.answer
                        }
                        className="btn-primary shrink-0 px-3 py-1 text-xs"
                        aria-label={`Approve clue ${submission.clueId ?? "unknown"} for ${playerName}`}
                      >
                        {approving === key ? "Approving..." : "Approve"}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section className="glass flex flex-col gap-2 px-6 py-4">
            <h2 className="text-lg font-semibold text-blue-800">Scores</h2>
            {scores.length === 0 ? (
              <EmptyState
                title="No scores yet"
                message="Scores will appear here once players solve clues."
              />
            ) : (
              <ul className="flex flex-col gap-1" aria-label="Scores">
                {scores.map((entry, index) => (
                  <li key={index} className="glass-soft px-3 py-2 text-sm text-blue-900">
                    {entry.playerId ?? "Unknown player"}: {entry.score ?? 0}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      ) : null}
    </main>
  );
}
