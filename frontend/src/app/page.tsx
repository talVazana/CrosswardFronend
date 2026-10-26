"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import EmptyState from "@/components/ui/EmptyState";
import ErrorMessage from "@/components/ui/ErrorMessage";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import { subscribeRooms } from "@/lib/roomsStore";
import {
  RoomSummary,
  isRoomActive,
  roomStatusLabel,
  roomStatusTone,
} from "@/utils/rooms";

function backendTone(status: "checking" | "connected" | "offline"): string {
  if (status === "connected") {
    return "border-emerald-300/70 bg-emerald-100/70 text-emerald-800";
  }
  if (status === "offline") {
    return "border-rose-300/70 bg-rose-100/70 text-rose-800";
  }
  return "border-blue-300/70 bg-blue-100/70 text-blue-800";
}

function RoomCard({
  room,
  canRemove,
  removing,
  onRemove,
}: {
  room: RoomSummary;
  canRemove: boolean;
  removing: boolean;
  onRemove: (roomId: string) => void;
}) {
  const status = room.status ?? "draft";
  const label = roomStatusLabel(status);
  const active = isRoomActive(status);

  return (
    <article
      className={`glass flex h-full flex-col gap-4 p-5 transition-transform duration-200 hover:-translate-y-0.5 ${
        active ? "ring-1 ring-emerald-300/60" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-lg font-semibold text-blue-900">{room.title}</h3>
          <p className="muted text-xs">Room {room.roomId}</p>
        </div>
        <span
          className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-semibold ${roomStatusTone(
            status,
          )}`}
        >
          {label}
        </span>
      </div>

      <dl className="grid grid-cols-2 gap-2 text-sm text-blue-900/80">
        <div>
          <dt className="muted text-xs">Players</dt>
          <dd className="font-medium text-blue-900">{room.playerCount ?? 0}</dd>
        </div>
        <div>
          <dt className="muted text-xs">Grid</dt>
          <dd className="font-medium text-blue-900">
            {room.width ?? "?"} × {room.height ?? "?"}
          </dd>
        </div>
        <div>
          <dt className="muted text-xs">Clues</dt>
          <dd className="font-medium text-blue-900">{room.clueCount ?? 0}</dd>
        </div>
        <div>
          <dt className="muted text-xs">Availability</dt>
          <dd className={`font-medium ${active ? "text-emerald-700" : "text-slate-500"}`}>
            {active ? "Active now" : "Not active"}
          </dd>
        </div>
      </dl>

      <div className="mt-auto flex gap-2">
        <Link href={`/rooms/${room.roomId}/join`} className="btn-primary flex-1 text-sm">
          Join room
        </Link>
        <Link href={`/rooms/${room.roomId}`} className="btn-ghost text-sm">
          View
        </Link>
        {canRemove ? (
          <button
            type="button"
            onClick={() => onRemove(room.roomId)}
            disabled={removing}
            className="rounded border border-rose-300 bg-white px-3 py-1 text-sm font-medium text-rose-700 hover:bg-rose-100 disabled:opacity-50"
          >
            Remove
          </button>
        ) : null}
      </div>
    </article>
  );
}

export default function Page() {
  const router = useRouter();
  const [backendStatus, setBackendStatus] = useState<
    "checking" | "connected" | "offline"
  >("checking");
  const [roomId, setRoomId] = useState("Room1");
  const [rooms, setRooms] = useState<RoomSummary[]>([]);
  const [roomsLoading, setRoomsLoading] = useState(true);
  const [roomsError, setRoomsError] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [removingRoomId, setRemovingRoomId] = useState<string | null>(null);

  const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

  useEffect(() => {
    let cancelled = false;
    fetch(`${base}/health`)
      .then(async (res) => {
        if (cancelled) return;
        if (!res.ok) {
          setBackendStatus("offline");
          return;
        }
        const body = await res.json();
        if (!cancelled) {
          setBackendStatus(body?.status === "ok" ? "connected" : "offline");
        }
      })
      .catch(() => {
        if (!cancelled) setBackendStatus("offline");
      });
    return () => {
      cancelled = true;
    };
  }, [base]);

  useEffect(() => {
    fetch(`${base}/admin/me`, { credentials: "include" })
      .then((res) => {
        if (res.ok) setIsAdmin(true);
      })
      .catch(() => {});
  }, [base]);

  const handleRemoveRoom = async (targetRoomId: string) => {
    const confirmed = window.confirm(`Remove room ${targetRoomId}?`);
    if (!confirmed) return;
    setRemovingRoomId(targetRoomId);
    try {
      await fetch(`${base}/admin/rooms/${targetRoomId}`, {
        method: "DELETE",
        credentials: "include",
      });
    } catch {
      // ignore; the gallery refreshes via Firestore once the room is gone
    } finally {
      setRemovingRoomId(null);
    }
  };

  useEffect(() => {
    const unsubscribe = subscribeRooms(
      (next) => {
        setRooms(next);
        setRoomsLoading(false);
        setRoomsError(null);
      },
      () => {
        setRoomsLoading(false);
        setRoomsError("Failed to load rooms from Firestore.");
      },
    );
    return unsubscribe;
  }, []);

  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const id = roomId.trim();
    if (id) router.push(`/rooms/${id}/join`);
  };

  const activeRooms = rooms.filter((room) => isRoomActive(room.status)).length;
  const backendLabel =
    backendStatus === "checking"
      ? "Checking backend..."
      : backendStatus === "connected"
        ? "Backend connected"
        : "Offline";

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-8 p-6">
      <header className="glass flex flex-wrap items-center justify-between gap-4 px-6 py-5">
        <div className="flex flex-col gap-1">
          <h1 className="brand text-4xl">Crossword Arena</h1>
          <p className="muted text-sm">
            Competitive crossword, solved together in real time.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${backendTone(
              backendStatus,
            )}`}
          >
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                backendStatus === "connected"
                  ? "bg-emerald-500"
                  : backendStatus === "offline"
                    ? "bg-rose-500"
                    : "bg-blue-500"
              }`}
            />
            {backendLabel}
          </span>
          <Link href="/admin/rooms" className="btn-ghost text-sm">
            Admin
          </Link>
        </div>
      </header>

      <section className="glass grid gap-6 px-6 py-8 md:grid-cols-[1.5fr_1fr]">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <h2 className="text-2xl font-semibold text-blue-900">Jump into a room</h2>
            <p className="muted text-sm">
              Enter a room ID or pick one from the gallery below. Solve clues
              together, earn points, and watch the board update live.
            </p>
          </div>
          <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row">
            <label className="flex flex-1 flex-col gap-1 text-start">
              <span className="text-sm font-medium">Room ID</span>
              <input
                type="text"
                value={roomId}
                onChange={(e) => setRoomId(e.target.value)}
                className="input"
                placeholder="Room1"
              />
            </label>
            <button type="submit" className="btn-primary sm:self-end">
              Join Room
            </button>
          </form>
        </div>
        <div className="glass-soft flex flex-col justify-center gap-2 p-5">
          <p className="text-sm font-medium text-blue-800">Rooms right now</p>
          <p className="text-4xl font-bold text-blue-900">{activeRooms}</p>
          <p className="muted text-sm">
            active · {rooms.length} total
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            <span className="rounded-full border border-blue-300/60 bg-white/60 px-2.5 py-1 text-xs font-medium text-blue-800">
              {rooms.reduce((total, room) => total + (room.playerCount ?? 0), 0)} players
            </span>
            <span className="rounded-full border border-blue-300/60 bg-white/60 px-2.5 py-1 text-xs font-medium text-blue-800">
              {rooms.length} rooms
            </span>
          </div>
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-blue-900">Room gallery</h2>
          <p className="muted text-sm">
            Every room on this server, updating live.
          </p>
        </div>

        {roomsLoading ? (
          <LoadingSpinner label="Loading rooms..." />
        ) : roomsError ? (
          <ErrorMessage
            title="Could not load rooms"
            message={roomsError}
          />
        ) : rooms.length === 0 ? (
          <EmptyState
            title="No rooms yet"
            message="Rooms will appear here as soon as they are created."
          />
        ) : (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {rooms.map((room) => (
              <RoomCard
                key={room.roomId}
                room={room}
                canRemove={isAdmin}
                removing={removingRoomId === room.roomId}
                onRemove={handleRemoveRoom}
              />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
