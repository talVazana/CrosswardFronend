"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import ParticipantList, { Participant } from "@/components/ParticipantList";

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
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState<LifecycleAction | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
      const res = await fetch(`${base}/admin/rooms/${roomId}`, {
        credentials: "include",
      });
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
      setLoading(false);
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

  const status = room?.status;
  const statusLabel = status ? (STATUS_LABELS[status] ?? status) : null;
  const players = room?.players ?? room?.participants ?? [];
  const pendingSubmissions = room?.pendingSubmissions ?? room?.pending ?? [];
  const scores = room?.scores ?? [];
  const actions = allowedActions(status);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-xl flex-col gap-6 p-6">
      {loading ? (
        <p role="status" className="text-gray-600">
          Loading...
        </p>
      ) : error ? (
        <p role="alert" className="text-red-600">
          {error}
        </p>
      ) : room ? (
        <>
          <header className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold">{room.title ?? "Admin Dashboard"}</h1>
            {statusLabel ? (
              <span className="inline-flex w-fit items-center gap-2 rounded-full bg-blue-50 px-3 py-1 text-sm font-medium text-blue-700">
                <span className="inline-block h-2 w-2 rounded-full bg-blue-500" />
                {statusLabel}
              </span>
            ) : null}
          </header>

          <section className="flex flex-col gap-3" aria-label="Room controls">
            <h2 className="text-lg font-medium">Controls</h2>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(ACTION_LABELS) as LifecycleAction[]).map((action) => {
                const enabled = actions.includes(action);
                return (
                  <button
                    key={action}
                    type="button"
                    disabled={!enabled || busy !== null}
                    onClick={() => triggerAction(action)}
                    className="rounded border border-gray-300 px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {ACTION_LABELS[action]}
                  </button>
                );
              })}
            </div>
            {actionError ? (
              <p role="alert" className="text-sm text-red-600">
                {actionError}
              </p>
            ) : null}
          </section>

          <section className="flex flex-col gap-2">
            <h2 className="text-lg font-medium">Participants</h2>
            <ParticipantList players={players} />
          </section>

          <section className="flex flex-col gap-2">
            <h2 className="text-lg font-medium">Pending Submissions</h2>
            {pendingSubmissions.length === 0 ? (
              <p className="text-sm text-gray-500">No pending submissions.</p>
            ) : (
              <ul className="flex flex-col gap-1" aria-label="Pending submissions">
                {pendingSubmissions.map((submission, index) => (
                  <li key={index} className="rounded border border-gray-200 px-3 py-2 text-sm">
                    {submission.playerId ?? "Unknown player"} — clue {submission.clueId ?? "?"}
                    {submission.answer ? `: ${submission.answer}` : ""}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="flex flex-col gap-2">
            <h2 className="text-lg font-medium">Scores</h2>
            {scores.length === 0 ? (
              <p className="text-sm text-gray-500">No scores yet.</p>
            ) : (
              <ul className="flex flex-col gap-1" aria-label="Scores">
                {scores.map((entry, index) => (
                  <li key={index} className="rounded border border-gray-200 px-3 py-2 text-sm">
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
