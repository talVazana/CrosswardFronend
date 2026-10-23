"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import CrosswordGrid, { Puzzle } from "@/components/CrosswordGrid";
import ParticipantList, { Participant } from "@/components/ParticipantList";

interface RoomState {
  roomId?: string;
  id?: string;
  title?: string;
  status?: string;
  players?: Participant[];
  participants?: Participant[];
}

const SAMPLE_PUZZLE: Puzzle = {
  puzzleId: "sample-puzzle-001",
  title: "Sample Puzzle",
  width: 5,
  height: 5,
  cells: [
    { row: 0, col: 0, type: "white", number: 1, startsAcross: true, startsDown: true },
    { row: 0, col: 1, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 0, col: 2, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 0, col: 3, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 0, col: 4, type: "white", number: 2, startsAcross: false, startsDown: true },
    { row: 1, col: 0, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 1, col: 1, type: "black", number: null, startsAcross: false, startsDown: false },
    { row: 1, col: 2, type: "white", number: 3, startsAcross: true, startsDown: false },
    { row: 1, col: 3, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 1, col: 4, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 2, col: 0, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 2, col: 1, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 2, col: 2, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 2, col: 3, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 2, col: 4, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 3, col: 0, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 3, col: 1, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 3, col: 2, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 3, col: 3, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 3, col: 4, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 4, col: 0, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 4, col: 1, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 4, col: 2, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 4, col: 3, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 4, col: 4, type: "white", number: null, startsAcross: false, startsDown: false },
  ],
  clues: [
    { clueId: "A1", number: 1, direction: "across", text: "Feline pet", answerLength: 3 },
    { clueId: "D1", number: 1, direction: "down", text: "Capital of France", answerLength: 5 },
    { clueId: "D2", number: 2, direction: "down", text: "Opposite of off", answerLength: 2 },
    { clueId: "A3", number: 3, direction: "across", text: "Color of the sky", answerLength: 4 },
  ],
};

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

  const players = room?.players ?? room?.participants ?? [];
  const statusLabel = room?.status
    ? (STATUS_LABELS[room.status] ?? room.status)
    : null;

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
            <h1 className="text-2xl font-semibold">{room.title}</h1>
            {statusLabel ? (
              <span className="inline-flex w-fit items-center gap-2 rounded-full bg-blue-50 px-3 py-1 text-sm font-medium text-blue-700">
                <span className="inline-block h-2 w-2 rounded-full bg-blue-500" />
                {statusLabel}
              </span>
            ) : null}
          </header>
          <section className="flex flex-col gap-2">
            <h2 className="text-lg font-medium">Puzzle</h2>
            <CrosswordGrid roomId={roomId} puzzle={SAMPLE_PUZZLE} />
          </section>
          <section className="flex flex-col gap-2">
            <h2 className="text-lg font-medium">Participants</h2>
            <ParticipantList players={players} />
          </section>
        </>
      ) : null}
    </main>
  );
}
